import sqlite3
import colorsys
import os
from datetime import datetime

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

# --- GIAO DIỆN KV ---
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
        md_bg_color: [1, 1, 1, 1]

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
            helper_text_mode: "on_error"
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
            input_filter: "int"
            max_text_length: 2
            helper_text_mode: "on_error"
        MDLabel:
            text: ":"
            adaptive_width: True
            pos_hint: {"center_y": .3}
        MDTextField:
            id: min_input
            hint_text: "MM"
            input_filter: "int"
            max_text_length: 2
            helper_text_mode: "on_error"
        MDRaisedButton:
            id: am_pm_button
            text: "AM"
            opacity: 1 if not app.is_24h_mode else 0
            disabled: app.is_24h_mode
            size_hint_x: None
            width: "60dp" if not app.is_24h_mode else 0
            on_release: self.text = "PM" if self.text == "AM" else "AM"

MDScreen:
    MDBoxLayout:
        orientation: 'vertical'
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
        rgb = list(colorsys.hsv_to_rgb(self.hue, s, v)) + [1.0]; MDApp.get_running_app().update_live_ui(rgb)

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
        h = max(0.0, min(1.0, (t.y - self.y)/self.height)); MDApp.get_running_app().color_content.ids.color_field.hue = h

class RightCheckbox(IRightBodyTouch, MDCheckbox):
    task_id = NumericProperty(None)
    def on_release(self): MDApp.get_running_app().mark_task(self, self.active)

class ListItemWithCheckbox(TwoLineAvatarIconListItem): db_id = NumericProperty(None)
class LeftCheckbox(ILeftBodyTouch, MDCheckbox): pass
class SettingListContent(MDBoxLayout): pass
class CustomColorContent(MDBoxLayout): pass
class ItemConfirm(MDBoxLayout): pass

# --- APP CLASS ---
class ChecklistApp(MDApp):
    lang_strings = DictProperty()
    selected_date = StringProperty("")
    is_24h_mode = BooleanProperty(True)
    settings_dialog = None
    sub_dialog = None

    def build(self):
        self.init_db()
        return Builder.load_string(KV)

    def on_start(self): Clock.schedule_once(self.deferred_load, 0.1)
    def deferred_load(self, dt): self.load_settings(); self.load_tasks()

    def init_db(self):
        db_path = os.path.join(self.user_data_dir, "checklist_v52.db")
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.cursor = self.conn.cursor()
        self.cursor.execute('CREATE TABLE IF NOT EXISTS tasks (id INTEGER PRIMARY KEY AUTOINCREMENT, content TEXT, is_done INTEGER, task_time TEXT, task_date TEXT, done_timestamp TEXT)')
        self.cursor.execute('CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)')
        for k, v in [('lang', 'English'), ('theme', 'Light'), ('color', '#3F51B5'), ('format', '24')]:
            self.cursor.execute("INSERT OR IGNORE INTO settings VALUES (?, ?)", (k, v))
        self.conn.commit()

    # --- HỆ THỐNG MENU CẢI TIẾN ---
    def show_settings_menu(self, *args):
        if self.sub_dialog: self.sub_dialog.dismiss()
        if self.settings_dialog: self.settings_dialog.dismiss()
        
        opts = [
            (self.lang_strings['lang_opt'], "translate", "lang"),
            (self.lang_strings['theme_opt'], "theme-light-dark", "theme"),
            (self.lang_strings['format_opt'], "clock-outline", "format"),
            (self.lang_strings['color_opt'], "palette", "color_picker")
        ]
        items = []
        for t, i, m in opts:
            item = OneLineAvatarIconListItem(text=t, on_release=lambda x, mo=m: self.open_setting_tab(mo) if mo!="color_picker" else self.open_pro_color_picker())
            item.add_widget(IconLeftWidget(icon=i))
            items.append(item)

        self.settings_dialog = MDDialog(
            title=self.lang_strings['settings'], 
            type="simple", 
            items=items,
            buttons=[MDFlatButton(text="EXIT", on_release=lambda x: self.settings_dialog.dismiss())]
        )
        self.settings_dialog.open()

    def open_setting_tab(self, mode):
        if self.settings_dialog: self.settings_dialog.dismiss()
        self.setting_content = SettingListContent()
        
        self.sub_dialog = MDDialog(
            title="", 
            type="custom", 
            content_cls=self.setting_content,
            buttons=[
                MDFlatButton(text="BACK", on_release=self.show_settings_menu),
                MDFlatButton(text="CLOSE", on_release=lambda x: self.sub_dialog.dismiss())
            ]
        )
        self.refresh_sub_list(mode)
        self.sub_dialog.open()

    def refresh_sub_list(self, mode):
        container = self.setting_content.ids.list_container
        container.clear_widgets()
        db_k = 'lang' if mode=='lang' else 'theme' if mode=='theme' else 'format'
        self.cursor.execute("SELECT value FROM settings WHERE key=?", (db_k,))
        curr = self.cursor.fetchone()[0]
        
        opts = [("Tiếng Việt", "Vietnamese"), ("English", "English")] if mode=="lang" else \
               [("Light", "Light"), ("Dark", "Dark")] if mode=="theme" else \
               [("12h", "12"), ("24h", "24")]
        
        for txt, k in opts:
            # Gán hàm update cho cả Item và Checkbox
            callback = lambda x, m=mode, v=k: self.update_setting(m, v)
            item = OneLineAvatarIconListItem(text=txt, on_release=callback)
            
            chk = LeftCheckbox(group="g", active=(curr == k))
            chk.bind(on_release=callback) # Đảm bảo bấm vào ô tick cũng ăn lệnh
            
            item.add_widget(chk)
            container.add_widget(item)

    def update_setting(self, mode, val):
        db_k = 'lang' if mode=='lang' else 'theme' if mode=='theme' else 'format'
        self.cursor.execute("UPDATE settings SET value=? WHERE key=?", (val, db_k))
        self.conn.commit()
        
        # Áp dụng thay đổi ngay lập tức
        self.load_settings()
        self.load_tasks()
        
        # Làm mới lại giao diện menu phụ để dấu tick cập nhật
        if self.sub_dialog:
            self.refresh_sub_list(mode)

    # --- CÁC HÀM CỨNG ---
    def save_task(self, *args):
        self.dialog_content.ids.task_input.error = False
        self.dialog_content.ids.hour_input.error = False
        self.dialog_content.ids.min_input.error = False
        content = self.dialog_content.ids.task_input.text.strip()
        if not content:
            self.dialog_content.ids.task_input.error = True
            return
        h_val, m_val = self.dialog_content.ids.hour_input.text.strip(), self.dialog_content.ids.min_input.text.strip()
        t_str = ""
        if h_val or m_val:
            try:
                h, m = (int(h_val) if h_val else 0), (int(m_val) if m_val else 0)
                valid = True
                if self.is_24h_mode:
                    if h < 0 or h > 23: self.dialog_content.ids.hour_input.error = True; valid = False
                else:
                    if h < 1 or h > 12: self.dialog_content.ids.hour_input.error = True; valid = False
                if m < 0 or m > 59: self.dialog_content.ids.min_input.error = True; valid = False
                if not valid: return
                t_str = f"{str(h).zfill(2)}:{str(m).zfill(2)}"
                if not self.is_24h_mode: t_str += f" {self.dialog_content.ids.am_pm_button.text}"
            except: return
        if self.editing_id: self.cursor.execute("UPDATE tasks SET content=?, task_time=?, task_date=? WHERE id=?", (content, t_str, self.selected_date, self.editing_id))
        else: self.cursor.execute("INSERT INTO tasks (content, is_done, task_time, task_date, done_timestamp) VALUES (?, 0, ?, ?, '')", (content, t_str, self.selected_date))
        self.conn.commit(); self.load_tasks(); self.task_dialog.dismiss()

    def show_task_dialog(self, task_id=None, current_text="", current_time="", current_date=""):
        self.editing_id = task_id; self.selected_date = current_date
        self.dialog_content = ItemConfirm(); self.dialog_content.ids.task_input.text = current_text
        if current_date: self.dialog_content.ids.date_label.text = current_date
        if current_time and ":" in current_time:
            p = current_time.replace(" AM","").replace(" PM","").split(":")
            self.dialog_content.ids.hour_input.text, self.dialog_content.ids.min_input.text = p[0], p[1]
            if "PM" in current_time: self.dialog_content.ids.am_pm_button.text = "PM"
        self.task_dialog = MDDialog(title=self.lang_strings['title'], type="custom", content_cls=self.dialog_content,
            buttons=[MDFlatButton(text=self.lang_strings['cancel'], on_release=lambda x: self.task_dialog.dismiss()),
                     MDRaisedButton(text=self.lang_strings['add'], on_release=self.save_task)])
        self.task_dialog.open()

    def load_settings(self):
        self.cursor.execute("SELECT value FROM settings WHERE key='lang'")
        lang = self.cursor.fetchone()[0]
        LANG_DATA = {
            "English": {"title": "Checklist", "archive": "Archive Box", "hint_text": "Task...", "add": "SAVE", "cancel": "CANCEL", "settings": "Settings", "lang_opt": "Language", "theme_opt": "Theme", "color_opt": "App Color", "format_opt": "Format", "pick_date": "DATE"},
            "Vietnamese": {"title": "Ghi chú", "archive": "Hòm lưu trữ", "hint_text": "Việc cần làm...", "add": "LƯU", "cancel": "HỦY", "settings": "Cài đặt", "lang_opt": "Ngôn ngữ", "theme_opt": "Giao diện", "color_opt": "Màu ứng dụng", "format_opt": "Định dạng", "pick_date": "CHỌN NGÀY"}
        }
        self.lang_strings = LANG_DATA.get(lang); self.root.ids.toolbar.title = self.lang_strings.get('title')
        self.cursor.execute("SELECT value FROM settings WHERE key='theme'"); self.theme_cls.theme_style = self.cursor.fetchone()[0]
        self.cursor.execute("SELECT value FROM settings WHERE key='color'"); self.apply_ui_color(self.cursor.fetchone()[0])
        self.cursor.execute("SELECT value FROM settings WHERE key='format'"); self.is_24h_mode = (self.cursor.fetchone()[0] == "24")

    def load_tasks(self, *args):
        container = self.root.ids.container; container.clear_widgets()
        self.cursor.execute("SELECT * FROM tasks"); rows = self.cursor.fetchall()
        for r in [x for x in rows if x[2] == 0]: self.add_item_ui(r, container)
        arch = [x for x in rows if x[2] == 1]
        if arch:
            cb = MDBoxLayout(orientation="vertical", adaptive_height=True)
            for r in arch: self.add_item_ui(r, cb)
            container.add_widget(MDExpansionPanel(icon="archive-outline", content=cb, panel_cls=MDExpansionPanelOneLine(text=self.lang_strings['archive'])))

    def add_item_ui(self, row, container):
        item = ListItemWithCheckbox(text=f"[s]{row[1]}[/s]" if row[2] else row[1], secondary_text=f"{row[4]} {row[3]}".strip(), db_id=row[0])
        if row[2]: item.theme_text_color = "Hint"
        del_btn = IconLeftWidget(icon="delete-outline", theme_text_color="Custom", text_color=(1,0,0,1))
        del_btn.bind(on_release=lambda x, i=row[0]: self.delete_task(i))
        item.add_widget(del_btn); item.add_widget(RightCheckbox(task_id=row[0], active=bool(row[2])))
        item.bind(on_release=lambda x, r=row: self.show_task_dialog(r[0], r[1], r[3], r[4])); container.add_widget(item)

    def mark_task(self, checkbox, active):
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S") if active else ""
        self.cursor.execute("UPDATE tasks SET is_done=?, done_timestamp=? WHERE id=?", (1 if active else 0, ts, checkbox.task_id))
        self.conn.commit(); self.load_tasks()

    def delete_task(self, i): self.cursor.execute("DELETE FROM tasks WHERE id=?", (i,)); self.conn.commit(); self.load_tasks()
    def apply_ui_color(self, hex_c):
        c = get_color_from_hex(hex_c); self.root.ids.toolbar.md_bg_color = c; self.root.ids.fab.md_bg_color = c

    def open_pro_color_picker(self, *args):
        if self.settings_dialog: self.settings_dialog.dismiss()
        self.color_content = CustomColorContent()
        self.color_dialog = MDDialog(title=self.lang_strings['color_opt'], type="custom", content_cls=self.color_content, 
            buttons=[MDFlatButton(text="BACK", on_release=self.show_settings_menu), MDFlatButton(text="OK", on_release=self.save_color)])
        self.color_dialog.open()

    def update_live_ui(self, color): self.color_content.ids.color_preview.md_bg_color = color
    def save_color(self, *args):
        hex_val = get_hex_from_color(self.color_content.ids.color_preview.md_bg_color)
        self.cursor.execute("UPDATE settings SET value=? WHERE key='color'", (hex_val,)); self.conn.commit(); self.apply_ui_color(hex_val); self.color_dialog.dismiss()

    def show_date_picker(self):
        try:
            from kivymd.uix.pickers import MDDatePicker
            d = MDDatePicker(); d.bind(on_save=lambda x, v, dr: self.set_date(v)); d.open()
        except: pass
    def set_date(self, v):
        self.selected_date = v.strftime("%d/%m/%Y")
        if hasattr(self, 'dialog_content'): self.dialog_content.ids.date_label.text = self.selected_date

if __name__ == "__main__":
    ChecklistApp().run()