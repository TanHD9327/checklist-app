import sqlite3
import colorsys
import os
from datetime import datetime

os.environ['KIVY_NO_CONSOLELOG'] = '1'  
os.environ['KIVY_NO_ARGS'] = '1'

from kivy.config import Config
Config.set('kivy', 'animations', '0')
from kivy.core.window import Window
Window.opacity = 0 

from kivy.lang import Builder
from kivy.properties import DictProperty, NumericProperty, StringProperty, BooleanProperty
from kivy.utils import get_color_from_hex, get_hex_from_color
from kivy.graphics import RenderContext, Rectangle
from kivy.uix.widget import Widget
from kivy.clock import Clock

from kivymd.app import MDApp
from kivymd.uix.dialog import MDDialog
from kivymd.uix.button import MDFlatButton, MDRaisedButton
from kivymd.uix.list import (
    TwoLineAvatarIconListItem,
    IRightBodyTouch,
    ILeftBodyTouch,
    IconLeftWidget,
    OneLineAvatarIconListItem
)
from kivymd.uix.selectioncontrol import MDCheckbox
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.expansionpanel import MDExpansionPanel, MDExpansionPanelOneLine

KV = '''
<SettingListContent>:
    orientation: "vertical"
    adaptive_height: True
    MDList:
        id: list_container

<CustomColorContent>:
    orientation: 'vertical'
    spacing: '10dp'
    padding: '10dp'
    adaptive_height: True
    MDBoxLayout:
        id: color_area
        size_hint_y: None
        height: '200dp'
        ColorField:
            id: color_field
            size_hint_x: 0.9
        HueSlider:
            id: hue_slider
            size_hint_x: 0.1
    MDBoxLayout:
        id: color_preview
        size_hint_y: None
        height: '40dp'
        md_bg_color: app.current_color_list

<ItemConfirm>:
    orientation: "vertical"
    spacing: "15dp"         
    padding: [0, "25dp", 0, "15dp"] 
    adaptive_height: True   
    MDBoxLayout:
        orientation: "vertical"
        adaptive_height: True
        padding: [0, 0, 0, "10dp"] 
        MDTextField:
            id: task_input
            hint_text: app.lang_strings.get('hint_text', 'Task')
            mode: "rectangle"
    MDBoxLayout:
        adaptive_height: True
        spacing: "15dp"
        MDRaisedButton:
            text: app.lang_strings.get('pick_date', 'DATE')
            on_release: app.show_date_picker()
        MDLabel:
            id: date_label
            text: app.selected_date if app.selected_date else "DD/MM/YYYY"
            pos_hint: {"center_y": .5}
    MDBoxLayout:
        orientation: "horizontal"
        spacing: "10dp"
        adaptive_height: True
        MDTextField:
            id: hour_input
            hint_text: "HH"
        MDLabel:
            text: ":"
            adaptive_width: True
            pos_hint: {"center_y": .3}
        MDTextField:
            id: min_input
            hint_text: "MM"
        MDRaisedButton:
            id: am_pm_button
            text: "AM"
            opacity: 1 if not app.is_24h_mode else 0
            disabled: app.is_24h_mode
            on_release: self.text = "PM" if self.text == "AM" else "AM"

MDScreen:
    MDBoxLayout:
        orientation: 'vertical'
        md_bg_color: app.theme_cls.bg_normal
        MDTopAppBar:
            id: toolbar
            title: app.lang_strings.get('title', 'Checklist')
            elevation: 4
            right_action_items: [["cog", lambda x: app.show_settings_menu()]]
        
        ScrollView:
            MDList:
                id: container
                padding: "10dp"
                spacing: "5dp"

    MDFloatingActionButton:
        id: fab
        icon: "plus"
        pos_hint: {"center_x": .85, "center_y": .1}
        on_release: app.show_task_dialog()
'''

class ColorField(Widget):
    hue = NumericProperty(0)
    def __init__(self, **kwargs):
        self.canvas = RenderContext(use_parent_modelview=True, use_parent_projection=True)
        self.canvas.shader.fs = '''
            $HEADER$
            uniform float hue;
            void main(void) {
                float h = hue; float s = tex_coord0.x; float v = tex_coord0.y;
                float h6 = mod(h, 1.0) * 6.0; int i = int(h6); float f = h6 - float(i);
                float p = v * (1.0 - s); float q = v * (1.0 - s * f); float t = v * (1.0 - s * (1.0 - f));
                if (i == 0) gl_FragColor = vec4(v, t, p, 1.0);
                else if (i == 1) gl_FragColor = vec4(q, v, p, 1.0);
                else if (i == 2) gl_FragColor = vec4(p, v, t, 1.0);
                else if (i == 3) gl_FragColor = vec4(p, q, v, 1.0);
                else if (i == 4) gl_FragColor = vec4(t, p, v, 1.0);
                else gl_FragColor = vec4(v, p, q, 1.0);
            }
        '''
        with self.canvas: self.rect = Rectangle()
        super().__init__(**kwargs)
        self.bind(size=self._redraw, pos=self._redraw)
        self.bind(hue=self._update_shader_hue)
    def _redraw(self, *args): self.rect.size, self.rect.pos = self.size, self.pos
    def _update_shader_hue(self, *args): self.canvas['hue'] = float(self.hue)
    def on_touch_down(self, t):
        if self.collide_point(*t.pos): self.process_touch(t); return True
    def on_touch_move(self, t):
        if self.collide_point(*t.pos): self.process_touch(t); return True
    def process_touch(self, t):
        s = max(0.0, min(1.0, (t.x - self.x)/self.width)); v = max(0.0, min(1.0, 1.0 - (t.y - self.y)/self.height))
        rgb = list(colorsys.hsv_to_rgb(self.hue, s, v)) + [1.0]
        MDApp.get_running_app().current_color_list = get_hex_from_color(rgb)

class HueSlider(Widget):
    def __init__(self, **kwargs):
        self.canvas = RenderContext(use_parent_modelview=True, use_parent_projection=True)
        self.canvas.shader.fs = '''
            $HEADER$
            void main(void) {
                float h = 1.0 - tex_coord0.y;
                float r = clamp(abs(h*6.0-3.0)-1.0, 0.0, 1.0);
                float g = clamp(2.0-abs(h*6.0-2.0), 0.0, 1.0);
                float b = clamp(2.0-abs(h*6.0-4.0), 0.0, 1.0);
                gl_FragColor = vec4(r, g, b, 1.0);
            }
        '''
        with self.canvas: self.rect = Rectangle()
        super().__init__(**kwargs)
        self.bind(size=self._redraw, pos=self._redraw)
    def _redraw(self, *args): self.rect.size, self.rect.pos = self.size, self.pos
    def on_touch_down(self, t):
        if self.collide_point(*t.pos): self.process_hue(t); return True
    def on_touch_move(self, t):
        if self.collide_point(*t.pos): self.process_hue(t); return True
    def process_hue(self, t):
        h = max(0.0, min(1.0, (t.y - self.y)/self.height))
        MDApp.get_running_app().color_content.ids.color_field.hue = h

class RightCheckbox(IRightBodyTouch, MDCheckbox):
    task_id = NumericProperty(None)
    def on_release(self): MDApp.get_running_app().mark_task(self, self.active)

class ListItemWithCheckbox(TwoLineAvatarIconListItem): db_id = NumericProperty(None)
class LeftCheckbox(ILeftBodyTouch, MDCheckbox): pass
class SettingListContent(MDBoxLayout): pass
class CustomColorContent(MDBoxLayout): pass
class ItemConfirm(MDBoxLayout): pass

class ChecklistApp(MDApp):
    lang_strings = DictProperty()
    selected_date = StringProperty("")
    current_color_list = StringProperty("#3F51B5")
    is_24h_mode = BooleanProperty(True)
    settings_dialog = None
    sub_dialog = None
    color_dialog = None
    task_dialog = None
    finished_panel_opened = BooleanProperty(False)

    def build(self):
        self.init_db()
        return Builder.load_string(KV)

    def on_start(self):
        self.load_settings()
        self.load_tasks()
        Window.opacity = 1

    def init_db(self):
        db_path = os.path.join(self.user_data_dir, "checklist_final.db")
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.cursor = self.conn.cursor()
        self.cursor.execute("CREATE TABLE IF NOT EXISTS tasks (id INTEGER PRIMARY KEY AUTOINCREMENT, content TEXT, is_done INTEGER, task_time TEXT, task_date TEXT, done_timestamp TEXT)")
        self.cursor.execute('CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)')
        for k, v in [('lang', 'English'), ('theme', 'Light'), ('color', '#3F51B5'), ('format', '24')]:
            self.cursor.execute("INSERT OR IGNORE INTO settings VALUES (?, ?)", (k, v))
        self.conn.commit()

    def load_tasks(self, *args):
        self.root.ids.container.clear_widgets()
        self.cursor.execute("SELECT * FROM tasks")
        rows = self.cursor.fetchall()
        active = [r for r in rows if r[2] == 0]
        done = [r for r in rows if r[2] == 1]
        
        for r in active:
            self.add_item_ui(r, self.root.ids.container)
        
        if done:
            box = MDBoxLayout(orientation="vertical", adaptive_height=True)
            for r in done:
                self.add_item_ui(r, box)
            
            panel = MDExpansionPanel(
                icon="check-circle-outline", 
                content=box, 
                panel_cls=MDExpansionPanelOneLine(text=self.lang_strings.get('archive', '')),
                opening_time=0, 
                closing_time=0
            )
            
            def set_panel_state(state): self.finished_panel_opened = state
            panel.bind(on_open=lambda *x: set_panel_state(True))
            panel.bind(on_close=lambda *x: set_panel_state(False))
            
            self.root.ids.container.add_widget(panel)
            if self.finished_panel_opened:
                Clock.schedule_once(lambda dt: panel.check_open_panel(panel), 0)

    def mark_task(self, checkbox, active):
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S") if active else ""
        self.cursor.execute("UPDATE tasks SET is_done=?, done_timestamp=? WHERE id=?", (1 if active else 0, ts, checkbox.task_id))
        self.conn.commit()
        item = checkbox.parent.parent
        if active:
            item.text = f"[s]{item.text.replace('[s]', '').replace('[/s]', '')}[/s]"
            item.theme_text_color = "Hint"
        else:
            Clock.schedule_once(self.load_tasks, 0)

    def load_settings(self):
        lang = self.cursor.execute("SELECT value FROM settings WHERE key='lang'").fetchone()[0]
        LANG_DATA = {
            "English": {
                "title": "Checklist", "archive": "Finished Tasks", "hint_text": "Task...", "add": "SAVE", "cancel": "CANCEL", 
                "settings": "Settings", "lang_opt": "Language", "theme_opt": "Theme", "color_opt": "App Color", "format_opt": "Format", 
                "pick_date": "DATE", "back": "BACK", "close": "CLOSE", "exit": "EXIT",
                "Light": "Light", "Dark": "Dark", "12h": "12h", "24h": "24h"
            },
            "Vietnamese": {
                "title": "Ghi chú", "archive": "Nhiệm vụ đã hoàn thành", "hint_text": "Việc cần làm...", "add": "LƯU", "cancel": "HỦY", 
                "settings": "Cài đặt", "lang_opt": "Ngôn ngữ", "theme_opt": "Giao diện", "color_opt": "Màu ứng dụng", "format_opt": "Định dạng", 
                "pick_date": "CHỌN NGÀY", "back": "QUAY LẠI", "close": "ĐÓNG", "exit": "THOÁT",
                "Light": "Sáng", "Dark": "Tối", "12h": "12 giờ", "24h": "24 giờ"
            }
        }
        self.lang_strings = LANG_DATA.get(lang)
        self.theme_cls.theme_style = self.cursor.execute("SELECT value FROM settings WHERE key='theme'").fetchone()[0]
        c_hex = self.cursor.execute("SELECT value FROM settings WHERE key='color'").fetchone()[0]
        self.current_color_list = c_hex
        self.apply_ui_color(c_hex)
        self.is_24h_mode = (self.cursor.execute("SELECT value FROM settings WHERE key='format'").fetchone()[0] == "24")
        self.root.ids.toolbar.title = self.lang_strings['title']

    def apply_ui_color(self, hex_c):
        color = get_color_from_hex(hex_c)
        self.root.ids.toolbar.md_bg_color = color
        self.root.ids.fab.md_bg_color = color
        r, g, b, a = color
        brightness = (r * 299 + g * 587 + b * 114) / 1000
        text_color = [0, 0, 0, 1] if brightness > 0.85 else [1, 1, 1, 1]
        self.root.ids.toolbar.specific_text_color = text_color
        self.root.ids.fab.text_color = text_color

    def add_item_ui(self, row, container):
        clean_text = row[1].replace("[s]", "").replace("[/s]", "")
        item_text = f"[s]{clean_text}[/s]" if row[2] else clean_text
        item = ListItemWithCheckbox(text=item_text, secondary_text=f"{row[4]} {row[3]}".strip(), db_id=row[0])
        if row[2]: item.theme_text_color = "Hint"
        del_btn = IconLeftWidget(icon="delete-outline", theme_text_color="Custom", text_color=(1, 0, 0, 1))
        del_btn.bind(on_release=lambda x, i=row[0]: self.delete_task(i))
        item.add_widget(del_btn)
        item.add_widget(RightCheckbox(task_id=row[0], active=bool(row[2])))
        item.bind(on_release=lambda x, r=row: self.show_task_dialog(r[0], r[1], r[3], r[4]))
        container.add_widget(item)

    def close_all_dialogs(self):
        if self.settings_dialog: self.settings_dialog.dismiss()
        if self.sub_dialog: self.sub_dialog.dismiss()
        if self.color_dialog: self.color_dialog.dismiss()
        if self.task_dialog: self.task_dialog.dismiss()

    def show_settings_menu(self, *args):
        self.close_all_dialogs()
        opts = [(self.lang_strings['lang_opt'], "translate", "lang"), (self.lang_strings['theme_opt'], "theme-light-dark", "theme"), (self.lang_strings['format_opt'], "clock-outline", "format"), (self.lang_strings['color_opt'], "palette", "color_picker")]
        items = [OneLineAvatarIconListItem(text=t, on_release=lambda x, m=mode: self.open_setting_tab(m) if m != "color_picker" else self.open_pro_color_picker()) for t, i, mode in opts]
        for i, (t, icon, mode) in enumerate(opts): items[i].add_widget(IconLeftWidget(icon=icon))
        
        self.settings_dialog = MDDialog(
            title=self.lang_strings['settings'], type="simple", items=items, 
            buttons=[MDFlatButton(text=self.lang_strings['exit'], on_release=lambda x: self.settings_dialog.dismiss())],
            show_duration=0, hide_duration=0
        )
        self.settings_dialog.open()

    def open_setting_tab(self, mode):
        self.close_all_dialogs()
        self.setting_content = SettingListContent()
        self.sub_dialog = MDDialog(
            title=self.lang_strings.get(mode + "_opt", ""), type="custom", content_cls=self.setting_content, 
            buttons=[MDFlatButton(text=self.lang_strings['back'], on_release=self.show_settings_menu), MDFlatButton(text=self.lang_strings['close'], on_release=lambda x: self.sub_dialog.dismiss())],
            show_duration=0, hide_duration=0
        )
        self.refresh_sub_list(mode)
        self.sub_dialog.open()

    def refresh_sub_list(self, mode):
        container = self.setting_content.ids.list_container
        container.clear_widgets()
        db_k = 'lang' if mode == 'lang' else 'theme' if mode == 'theme' else 'format'
        cur = self.cursor.execute("SELECT value FROM settings WHERE key=?", (db_k,)).fetchone()[0]
        
        # Sử dụng lang_strings để dịch tên hiển thị
        if mode == "lang":
            opts = [("Tiếng Việt", "Vietnamese"), ("English", "English")]
        elif mode == "theme":
            opts = [(self.lang_strings['Light'], "Light"), (self.lang_strings['Dark'], "Dark")]
        else: # format
            opts = [(self.lang_strings['12h'], "12"), (self.lang_strings['24h'], "24")]

        for display_text, key in opts:
            item = OneLineAvatarIconListItem(text=display_text, on_release=lambda x, m=mode, v=key: self.update_setting(m, v))
            cb = LeftCheckbox(group="g", active=(cur == key))
            cb.bind(on_release=lambda x, m=mode, v=key: self.update_setting(m, v))
            item.add_widget(cb); container.add_widget(item)

    def update_setting(self, mode, val):
        self.cursor.execute("UPDATE settings SET value=? WHERE key=?", (val, 'lang' if mode == 'lang' else 'theme' if mode == 'theme' else 'format'))
        self.conn.commit()
        self.load_settings()
        self.load_tasks()
        
        if self.sub_dialog:
            self.sub_dialog.title = self.lang_strings.get(mode + "_opt", "")
            if len(self.sub_dialog.buttons) >= 2:
                self.sub_dialog.buttons[0].text = self.lang_strings['back']
                self.sub_dialog.buttons[1].text = self.lang_strings['close']
            self.refresh_sub_list(mode)

    def save_task(self, *args):
        c = self.dialog_content.ids.task_input.text.strip()
        if not c: return
        h, m = self.dialog_content.ids.hour_input.text.strip(), self.dialog_content.ids.min_input.text.strip()
        t_s = f"{h.zfill(2)}:{m.zfill(2)}" + (f" {self.dialog_content.ids.am_pm_button.text}" if not self.is_24h_mode else "") if h or m else ""
        if self.editing_id: self.cursor.execute("UPDATE tasks SET content=?, task_time=?, task_date=? WHERE id=?", (c, t_s, self.selected_date, self.editing_id))
        else: self.cursor.execute("INSERT INTO tasks (content, is_done, task_time, task_date, done_timestamp) VALUES (?, 0, ?, ?, '')", (c, t_s, self.selected_date))
        self.conn.commit(); self.load_tasks(); self.task_dialog.dismiss()

    def show_task_dialog(self, t_id=None, c_t="", c_time="", c_d=""):
        self.close_all_dialogs()
        self.editing_id, self.selected_date, self.dialog_content = t_id, c_d, ItemConfirm()
        self.dialog_content.ids.task_input.text = c_t
        if c_d: self.dialog_content.ids.date_label.text = c_d
        if c_time and ":" in c_time:
            p = c_time.replace(" AM", "").replace(" PM", "").split(":")
            self.dialog_content.ids.hour_input.text, self.dialog_content.ids.min_input.text = p[0], p[1]
            if "PM" in c_time: self.dialog_content.ids.am_pm_button.text = "PM"
        self.task_dialog = MDDialog(
            title=self.lang_strings['title'], type="custom", content_cls=self.dialog_content, 
            buttons=[MDFlatButton(text=self.lang_strings['cancel'], on_release=lambda x: self.task_dialog.dismiss()), MDRaisedButton(text=self.lang_strings['add'], on_release=self.save_task)],
            show_duration=0, hide_duration=0
        )
        self.task_dialog.open()

    def delete_task(self, i):
        self.cursor.execute("DELETE FROM tasks WHERE id=?", (i,)); self.conn.commit(); self.load_tasks()

    def open_pro_color_picker(self, *args):
        self.close_all_dialogs()
        self.color_content = CustomColorContent()
        self.color_dialog = MDDialog(
            title=self.lang_strings['color_opt'], type="custom", content_cls=self.color_content, 
            buttons=[MDFlatButton(text=self.lang_strings['back'], on_release=self.show_settings_menu), MDFlatButton(text="OK", on_release=self.save_color)],
            show_duration=0, hide_duration=0
        )
        self.color_dialog.open()

    def save_color(self, *args):
        hx = self.current_color_list
        self.cursor.execute("UPDATE settings SET value=? WHERE key='color'", (hx,))
        self.conn.commit(); self.apply_ui_color(hx); self.color_dialog.dismiss()

    def show_date_picker(self):
        try:
            from kivymd.uix.pickers import MDDatePicker
            d = MDDatePicker()
            d.bind(on_save=lambda x, v, dr: self.set_date(v))
            d.open()
        except ImportError: pass

    def set_date(self, d_obj):
        self.selected_date = d_obj.strftime("%d/%m/%Y")
        if hasattr(self, 'dialog_content'): self.dialog_content.ids.date_label.text = self.selected_date

if __name__ == "__main__":
    ChecklistApp().run()