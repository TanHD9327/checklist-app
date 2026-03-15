import sqlite3
import colorsys
from datetime import datetime

from kivy.lang import Builder
from kivy.properties import DictProperty, ListProperty, NumericProperty, StringProperty, BooleanProperty
from kivy.utils import get_color_from_hex, get_hex_from_color
from kivy.graphics import RenderContext, Rectangle
from kivy.uix.widget import Widget

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
from kivymd.uix.pickers import MDDatePicker
# FIX: Import Snackbar bản cũ
from kivymd.uix.snackbar import Snackbar

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
        spacing: '10dp'
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
    spacing: "20dp"
    padding: [0, "10dp", 0, "10dp"]
    size_hint_y: None
    height: "320dp"
    
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
            text: app.selected_date
            theme_text_color: "Secondary"

    MDBoxLayout:
        orientation: "horizontal"
        spacing: "10dp"
        adaptive_height: True
        
        MDTextField:
            id: hour_input
            hint_text: "HH"
            input_filter: "int"
        
        MDLabel:
            text: ":"
            adaptive_width: True
            font_style: "H4"
            pos_hint: {"center_y": .4}

        MDTextField:
            id: min_input
            hint_text: "MM"
            input_filter: "int"
            
        MDRaisedButton:
            id: am_pm_button
            text: "AM"
            opacity: 1 if app.is_24h_mode == False else 0
            disabled: app.is_24h_mode
            on_release: self.text = "PM" if self.text == "AM" else "AM"

MDScreen:
    MDBoxLayout:
        orientation: 'vertical'
        MDTopAppBar:
            id: toolbar
            title: app.lang_strings.get('title', 'Checklist')
            right_action_items: [["cog", lambda x: app.show_settings_menu()]]
        ScrollView:
            MDList:
                id: container
    MDFloatingActionButton:
        id: fab
        icon: "plus"
        pos_hint: {"center_x": .85, "center_y": .1}
        on_release: app.show_task_dialog()
'''

class LeftCheckbox(ILeftBodyTouch, MDCheckbox): pass
class RightCheckbox(IRightBodyTouch, MDCheckbox):
    task_id = None
    def on_release(self): MDApp.get_running_app().mark_task(self.task_id, self.active)

class ListItemWithCheckbox(TwoLineAvatarIconListItem):
    def __init__(self, db_id=None, **kwargs):
        super().__init__(**kwargs); self.db_id = db_id

class ColorField(Widget):
    hue = NumericProperty(0)
    def __init__(self, **kwargs):
        self.canvas = RenderContext(use_parent_modelview=True, use_parent_projection=True)
        self.canvas.shader.fs = '$HEADER$\nuniform float hue;\nvoid main(void) { float h = hue; float s = tex_coord0.x; float v = tex_coord0.y; h = mod(h, 1.0) * 6.0; int i = int(h); float f = h - float(i); float p = v * (1.0 - s); float q = v * (1.0 - s * f); float t = v * (1.0 - s * (1.0 - f)); vec3 rgb; if (i == 0) rgb = vec3(v, t, p); else if (i == 1) rgb = vec3(q, v, p); else if (i == 2) rgb = vec3(p, v, t); else if (i == 3) rgb = vec3(p, q, v); else if (i == 4) rgb = vec3(t, p, v); else rgb = vec3(v, p, q); gl_FragColor = vec4(rgb, 1.0); }'
        with self.canvas: self.rect = Rectangle()
        super().__init__(**kwargs)
        self.bind(size=self._update, pos=self._update, hue=lambda *a: setattr(self.canvas, 'hue', float(self.hue)))
    def _update(self, *args): self.rect.size, self.rect.pos = self.size, self.pos
    def on_touch_down(self, t): 
        if self.collide_point(*t.pos): self.update_c(t); return True
    def on_touch_move(self, t): 
        if self.collide_point(*t.pos): self.update_c(t); return True
    def update_c(self, t):
        s = (t.x - self.x)/self.width; v = 1.0 - (t.y - self.y)/self.height
        rgb = list(colorsys.hsv_to_rgb(self.hue, max(0,min(1,s)), max(0,min(1,v)))) + [1]
        MDApp.get_running_app().update_live_ui(rgb)

class HueSlider(Widget):
    def __init__(self, **kwargs):
        self.canvas = RenderContext(use_parent_modelview=True, use_parent_projection=True)
        self.canvas.shader.fs = '$HEADER$\nvoid main(void) { float h = 1.0 - tex_coord0.y; float r = clamp(abs(h*6.0-3.0)-1.0,0.0,1.0); float g = clamp(2.0-abs(h*6.0-2.0),0.0,1.0); float b = clamp(2.0-abs(h*6.0-4.0),0.0,1.0); gl_FragColor = vec4(r,g,b,1.0); }'
        with self.canvas: self.rect = Rectangle()
        super().__init__(**kwargs)
        self.bind(size=self._update, pos=self._update)
    def _update(self, *args): self.rect.size, self.rect.pos = self.size, self.pos
    def on_touch_down(self, t): 
        if self.collide_point(*t.pos): self.update_h(t); return True
    def on_touch_move(self, t): 
        if self.collide_point(*t.pos): self.update_h(t); return True
    def update_h(self, t): MDApp.get_running_app().color_content.ids.color_field.hue = (t.y - self.y)/self.height

class CustomColorContent(MDBoxLayout): pass
class SettingListContent(MDBoxLayout): pass
class ItemConfirm(MDBoxLayout): pass

class ChecklistApp(MDApp):
    lang_strings = DictProperty()
    selected_date = StringProperty("")
    is_24h_mode = BooleanProperty(True)
    task_dialog = settings_dialog = sub_dialog = color_dialog = None

    LANG_DATA = {
        "English": {"title": "Checklist", "hint_text": "Task...", "add": "SAVE", "cancel": "CANCEL", "settings": "Settings", "lang_opt": "Language", "theme_opt": "Theme", "color_opt": "App Color", "format_opt": "Format", "pick_date": "DATE", "err_empty": "Empty content!", "err_conflict": "Date is required with Time!"},
        "Vietnamese": {"title": "Ghi chú", "hint_text": "Việc cần làm...", "add": "LƯU", "cancel": "HỦY", "settings": "Cài đặt", "lang_opt": "Ngôn ngữ", "theme_opt": "Giao diện", "color_opt": "Màu ứng dụng", "format_opt": "Định dạng", "pick_date": "CHỌN NGÀY", "err_empty": "Chưa nhập nội dung!", "err_conflict": "Có giờ thì phải có ngày!"}
    }

    def build(self):
        self.init_db()
        return Builder.load_string(KV)

    def on_start(self):
        self.load_settings()
        self.load_tasks()

    def init_db(self):
        self.conn = sqlite3.connect("checklist_pro.db")
        self.cursor = self.conn.cursor()
        self.cursor.execute('CREATE TABLE IF NOT EXISTS tasks (id INTEGER PRIMARY KEY AUTOINCREMENT, content TEXT, is_done INTEGER, task_time TEXT, task_date TEXT)')
        self.cursor.execute('CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)')
        for k, v in [('lang', 'Vietnamese'), ('theme', 'Light'), ('color', '#3F51B5'), ('format', '24')]:
            self.cursor.execute("INSERT OR IGNORE INTO settings VALUES (?, ?)", (k, v))
        self.conn.commit()

    # FIX: Hàm hiện thông báo theo chuẩn cũ
    def show_msg(self, text):
        Snackbar(text=text).open()

    def load_settings(self):
        self.cursor.execute("SELECT value FROM settings WHERE key='lang'"); self.lang_strings = self.LANG_DATA[self.cursor.fetchone()[0]]
        self.cursor.execute("SELECT value FROM settings WHERE key='theme'"); self.theme_cls.theme_style = self.cursor.fetchone()[0]
        self.cursor.execute("SELECT value FROM settings WHERE key='color'"); c = self.cursor.fetchone()[0]; self.apply_ui_color(c)
        self.cursor.execute("SELECT value FROM settings WHERE key='format'"); self.is_24h_mode = (self.cursor.fetchone()[0] == "24")

    def apply_ui_color(self, hex_c):
        c = get_color_from_hex(hex_c)
        if self.root:
            self.root.ids.toolbar.md_bg_color = c
            self.root.ids.fab.md_bg_color = c

    def load_tasks(self, *args):
        self.root.ids.container.clear_widgets()
        self.cursor.execute("SELECT id, content, is_done, task_time, task_date FROM tasks ORDER BY is_done ASC, id DESC")
        for row in self.cursor.fetchall():
            t_id, content, is_done, t_time, t_date = row
            time_info = f"{t_date} {t_time}".strip()
            item = ListItemWithCheckbox(text=content, secondary_text=time_info, db_id=t_id)
            li = IconLeftWidget(icon="delete-outline", theme_text_color="Custom", text_color=(1,0,0,1))
            li.bind(on_release=lambda x, i=t_id: self.delete_task(i))
            item.add_widget(li)
            cb = RightCheckbox(); cb.task_id = t_id; cb.active = bool(is_done); item.add_widget(cb)
            item.bind(on_release=lambda x, i=t_id, c=content, ti=t_time, da=t_date: self.show_task_dialog(i, c, ti, da))
            self.root.ids.container.add_widget(item)

    def show_task_dialog(self, task_id=None, current_text="", current_time="", current_date=""):
        self.editing_id = task_id; self.selected_date = current_date
        self.dialog_content = ItemConfirm()
        self.dialog_content.ids.task_input.text = current_text
        if ":" in current_time:
            h, m = current_time.split(":")
            self.dialog_content.ids.hour_input.text = h; self.dialog_content.ids.min_input.text = m[:2]
        
        self.task_dialog = MDDialog(
            title=self.lang_strings['title'], type="custom", content_cls=self.dialog_content,
            buttons=[MDFlatButton(text=self.lang_strings['cancel'], on_release=lambda x: self.task_dialog.dismiss()),
                     MDRaisedButton(text=self.lang_strings['add'], on_release=self.save_task)]
        )
        self.task_dialog.open()

    def save_task(self, *args):
        tf, hf, mf = self.dialog_content.ids.task_input, self.dialog_content.ids.hour_input, self.dialog_content.ids.min_input
        if not tf.text.strip():
            self.show_msg(self.lang_strings['err_empty']); return
        
        h_s, m_s = hf.text.strip(), mf.text.strip()
        time_str = ""
        
        if h_s or m_s:
            if not self.selected_date:
                self.selected_date = datetime.now().strftime("%d/%m/%Y")
            
            h_val = h_s.zfill(2) if h_s else "00"
            m_val = m_s.zfill(2) if m_s else "00"
            time_str = f"{h_val}:{m_val}"
            if not self.is_24h_mode:
                time_str += f" {self.dialog_content.ids.am_pm_button.text}"

        if self.editing_id: self.cursor.execute("UPDATE tasks SET content=?, task_time=?, task_date=? WHERE id=?", (tf.text, time_str, self.selected_date, self.editing_id))
        else: self.cursor.execute("INSERT INTO tasks (content, is_done, task_time, task_date) VALUES (?, 0, ?, ?)", (tf.text, time_str, self.selected_date))
        
        self.conn.commit(); self.load_tasks(); self.task_dialog.dismiss()
        self.selected_date = ""

    def show_settings_menu(self, *args):
        if self.sub_dialog: self.sub_dialog.dismiss()
        configs = [(self.lang_strings['lang_opt'], "translate", "lang"), (self.lang_strings['theme_opt'], "theme-light-dark", "theme"), (self.lang_strings['format_opt'], "clock-outline", "format"), (self.lang_strings['color_opt'], "palette", "color_picker")]
        items = []
        for text, icon, mode in configs:
            cb = self.open_pro_color_picker if mode == "color_picker" else lambda x, m=mode: self.open_setting_tab(m)
            item = OneLineAvatarIconListItem(text=text, on_release=cb)
            item.add_widget(IconLeftWidget(icon=icon)); items.append(item)
        self.settings_dialog = MDDialog(title=self.lang_strings['settings'], type="simple", items=items)
        self.settings_dialog.open()

    def open_setting_tab(self, mode):
        self.settings_dialog.dismiss(); self.setting_content = SettingListContent()
        self.sub_dialog = MDDialog(title="", type="custom", content_cls=self.setting_content, buttons=[MDFlatButton(text="OK", on_release=self.show_settings_menu)])
        self.refresh_sub_list(mode); self.sub_dialog.open()

    def refresh_sub_list(self, mode):
        container = self.setting_content.ids.list_container; container.clear_widgets()
        db_k = 'lang' if mode=='lang' else 'theme' if mode=='theme' else 'format'
        self.cursor.execute("SELECT value FROM settings WHERE key=?", (db_k,)); curr = self.cursor.fetchone()[0]
        opts = [("Tiếng Việt", "Vietnamese"), ("English", "English")] if mode=="lang" else [("Light", "Light"), ("Dark", "Dark")] if mode=="theme" else [("12h", "12"), ("24h", "24")]
        for txt, k in opts:
            item = OneLineAvatarIconListItem(text=txt, on_release=lambda x, m=mode, val=k: self.update_setting(m, val))
            item.add_widget(LeftCheckbox(group="g", active=(curr == k), on_release=lambda x, m=mode, val=k: self.update_setting(m, val)))
            container.add_widget(item)

    def update_setting(self, mode, val):
        db_k = 'lang' if mode=='lang' else 'theme' if mode=='theme' else 'format'
        self.cursor.execute("UPDATE settings SET value=? WHERE key=?", (val, db_k)); self.conn.commit()
        self.load_settings(); self.refresh_sub_list(mode); self.load_tasks()

    def open_pro_color_picker(self, *args):
        self.settings_dialog.dismiss(); self.color_content = CustomColorContent()
        self.color_dialog = MDDialog(title=self.lang_strings['color_opt'], type="custom", content_cls=self.color_content, 
                                    buttons=[MDFlatButton(text="OK", on_release=self.save_color)])
        self.color_dialog.open()

    def update_live_ui(self, color): self.color_content.ids.color_preview.md_bg_color = color

    def save_color(self, *args):
        hex_val = get_hex_from_color(self.color_content.ids.color_preview.md_bg_color)
        self.cursor.execute("UPDATE settings SET value=? WHERE key='color'", (hex_val,)); self.conn.commit()
        self.apply_ui_color(hex_val); self.color_dialog.dismiss(); self.show_settings_menu()

    def show_date_picker(self):
        d = MDDatePicker(); d.bind(on_save=lambda x, v, dr: self.set_date(v)); d.open()
    def set_date(self, v): self.selected_date = v.strftime("%d/%m/%Y"); self.dialog_content.ids.date_label.text = self.selected_date
    def delete_task(self, i): self.cursor.execute("DELETE FROM tasks WHERE id=?", (i,)); self.conn.commit(); self.load_tasks()
    def mark_task(self, i, a): self.cursor.execute("UPDATE tasks SET is_done=? WHERE id=?", (1 if a else 0, i)); self.conn.commit(); self.load_tasks()

if __name__ == "__main__":
    ChecklistApp().run()