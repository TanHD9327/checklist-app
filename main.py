import sqlite3
import colorsys
import os
from datetime import datetime

from kivy.lang import Builder
from kivy.properties import DictProperty, NumericProperty, StringProperty, BooleanProperty
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
            on_text: self.error = False
    
    MDBoxLayout:
        adaptive_height: True
        spacing: "15dp"
        MDRaisedButton:
            text: app.lang_strings.get('pick_date', 'DATE')
            on_release: app.show_date_picker()
        MDLabel:
            id: date_label
            text: app.selected_date if app.selected_date else "DD/MM/YYYY"
            theme_text_color: "Secondary"
            pos_hint: {"center_y": .5}

    MDBoxLayout:
        orientation: "horizontal"
        spacing: "10dp"
        adaptive_height: True
        
        MDTextField:
            id: hour_input
            hint_text: "HH"
            mode: "rectangle"
            input_filter: "int"
            max_text_length: 2
            helper_text_mode: "on_error"
            on_text: self.error = False
        
        MDLabel:
            text: ":"
            adaptive_width: True
            font_style: "H4"
            pos_hint: {"center_y": .4}

        MDTextField:
            id: min_input
            hint_text: "MM"
            mode: "rectangle"
            input_filter: "int"
            max_text_length: 2
            helper_text_mode: "on_error"
            on_text: self.error = False
            
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

    MDFloatingActionButton:
        id: fab
        icon: "plus"
        pos_hint: {"center_x": .85, "center_y": .1}
        on_release: app.show_task_dialog()
'''

class LeftCheckbox(ILeftBodyTouch, MDCheckbox): pass
class RightCheckbox(IRightBodyTouch, MDCheckbox):
    task_id = NumericProperty(None)
    def on_release(self):
        MDApp.get_running_app().mark_task(self.task_id, self.active)

class ListItemWithCheckbox(TwoLineAvatarIconListItem):
    db_id = NumericProperty(None)

class ColorField(Widget):
    hue = NumericProperty(0)
    def __init__(self, **kwargs):
        self.canvas = RenderContext(use_parent_modelview=True, use_parent_projection=True)
        self.canvas.shader.fs = '''
            $HEADER$
            uniform float hue;
            void main(void) {
                float h = hue; float s = tex_coord0.x; float v = tex_coord0.y;
                h = mod(h, 1.0) * 6.0; int i = int(h); float f = h - float(i);
                float p = v * (1.0 - s); float q = v * (1.0 - s * f); float t = v * (1.0 - s * (1.0 - f));
                vec3 rgb;
                if (i == 0) rgb = vec3(v, t, p); else if (i == 1) rgb = vec3(q, v, p);
                else if (i == 2) rgb = vec3(p, v, t); else if (i == 3) rgb = vec3(p, q, v);
                else if (i == 4) rgb = vec3(t, p, v); else rgb = vec3(v, p, q);
                gl_FragColor = vec4(rgb, 1.0);
            }
        '''
        with self.canvas: self.rect = Rectangle()
        super().__init__(**kwargs)
        self.bind(size=self._update, pos=self._update)
        self.bind(hue=self._update_shader_hue)
    def _update(self, *args): self.rect.size, self.rect.pos = self.size, self.pos
    def _update_shader_hue(self, *args): self.canvas['hue'] = float(self.hue)
    def on_touch_down(self, t):
        if self.collide_point(*t.pos): self.update_c(t); return True
    def on_touch_move(self, t):
        if self.collide_point(*t.pos): self.update_c(t); return True
    def update_c(self, t):
        s = (t.x - self.x)/self.width
        v = 1.0 - (t.y - self.y)/self.height
        rgb = list(colorsys.hsv_to_rgb(self.hue, max(0,min(1,s)), max(0,min(1,v)))) + [1]
        MDApp.get_running_app().update_live_ui(rgb)

class HueSlider(Widget):
    def __init__(self, **kwargs):
        self.canvas = RenderContext(use_parent_modelview=True, use_parent_projection=True)
        self.canvas.shader.fs = '''
            $HEADER$
            void main(void) {
                float h = 1.0 - tex_coord0.y;
                float r = clamp(abs(h*6.0-3.0)-1.0,0.0,1.0);
                float g = clamp(2.0-abs(h*6.0-2.0),0.0,1.0);
                float b = clamp(2.0-abs(h*6.0-4.0),0.0,1.0);
                gl_FragColor = vec4(r,g,b,1.0);
            }
        '''
        with self.canvas: self.rect = Rectangle()
        super().__init__(**kwargs)
        self.bind(size=self._update, pos=self._update)
    def _update(self, *args): self.rect.size, self.rect.pos = self.size, self.pos
    def on_touch_down(self, t):
        if self.collide_point(*t.pos): self.update_h(t); return True
    def on_touch_move(self, t):
        if self.collide_point(*t.pos): self.update_h(t); return True
    def update_h(self, t):
        h = max(0, min(1, (t.y - self.y)/self.height))
        MDApp.get_running_app().color_content.ids.color_field.hue = h

class CustomColorContent(MDBoxLayout): pass
class SettingListContent(MDBoxLayout): pass
class ItemConfirm(MDBoxLayout): pass

class ChecklistApp(MDApp):
    lang_strings = DictProperty()
    selected_date = StringProperty("")
    is_24h_mode = BooleanProperty(True)
    
    LANG_DATA = {
        "English": {
            "title": "Checklist", "hint_text": "Task...", "add": "SAVE", "cancel": "CANCEL", 
            "settings": "Settings", "lang_opt": "Language", "theme_opt": "Theme", 
            "color_opt": "App Color", "format_opt": "Time Format", "pick_date": "DATE",
            "err_empty": "Content cannot be empty", "err_past": "Time has passed"
        },
        "Vietnamese": {
            "title": "Ghi chú", "hint_text": "Việc cần làm...", "add": "LƯU", "cancel": "HỦY", 
            "settings": "Cài đặt", "lang_opt": "Ngôn ngữ", "theme_opt": "Giao diện", 
            "color_opt": "Màu ứng dụng", "format_opt": "Định dạng giờ", "pick_date": "CHỌN NGÀY",
            "err_empty": "Vui lòng nhập nội dung", "err_past": "Thời gian đã trôi qua"
        }
    }

    def build(self):
        self.settings_dialog = None
        self.sub_dialog = None
        self.task_dialog = None
        self.color_dialog = None
        self.init_db()
        return Builder.load_string(KV)

    def on_start(self):
        self.load_settings()
        self.load_tasks()

    def init_db(self):
        db_path = os.path.join(self.user_data_dir, "checklist_final_v9.db")
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.cursor = self.conn.cursor()
        self.cursor.execute('CREATE TABLE IF NOT EXISTS tasks (id INTEGER PRIMARY KEY AUTOINCREMENT, content TEXT, is_done INTEGER, task_time TEXT, task_date TEXT)')
        self.cursor.execute('CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)')
        # ĐẶT MẶC ĐỊNH LÀ ENGLISH Ở ĐÂY
        for k, v in [('lang', 'English'), ('theme', 'Light'), ('color', '#3F51B5'), ('format', '24')]:
            self.cursor.execute("INSERT OR IGNORE INTO settings VALUES (?, ?)", (k, v))
        self.conn.commit()

    def load_settings(self):
        self.cursor.execute("SELECT value FROM settings WHERE key='lang'")
        lang_val = self.cursor.fetchone()[0]
        self.lang_strings = self.LANG_DATA.get(lang_val, self.LANG_DATA["English"])
        
        self.cursor.execute("SELECT value FROM settings WHERE key='theme'")
        self.theme_cls.theme_style = self.cursor.fetchone()[0]
        
        self.cursor.execute("SELECT value FROM settings WHERE key='color'")
        self.apply_ui_color(self.cursor.fetchone()[0])
        
        self.cursor.execute("SELECT value FROM settings WHERE key='format'")
        self.is_24h_mode = (self.cursor.fetchone()[0] == "24")

    def apply_ui_color(self, hex_c):
        c = get_color_from_hex(hex_c)
        if self.root:
            self.root.ids.toolbar.md_bg_color = c
            self.root.ids.fab.md_bg_color = c
            lum = colorsys.rgb_to_hls(*c[:3])[1]
            self.root.ids.toolbar.specific_text_color = [1,1,1,1] if lum < 0.6 else [0,0,0,1]

    def load_tasks(self, *args):
        self.root.ids.container.clear_widgets()
        self.cursor.execute("SELECT id, content, is_done, task_time, task_date FROM tasks ORDER BY is_done ASC, id DESC")
        for row in self.cursor.fetchall():
            t_id, content, is_done, t_time, t_date = row
            item = ListItemWithCheckbox(text=content, secondary_text=f"{t_date} {t_time}".strip(), db_id=t_id)
            del_btn = IconLeftWidget(icon="delete-outline", theme_text_color="Custom", text_color=(1,0,0,1))
            del_btn.bind(on_release=lambda x, i=t_id: self.delete_task(i))
            item.add_widget(del_btn)
            cb = RightCheckbox(task_id=t_id, active=bool(is_done))
            item.add_widget(cb)
            item.bind(on_release=lambda x, i=t_id, c=content, ti=t_time, da=t_date: self.show_task_dialog(i, c, ti, da))
            self.root.ids.container.add_widget(item)

    def show_task_dialog(self, task_id=None, current_text="", current_time="", current_date=""):
        self.editing_id = task_id
        self.selected_date = current_date
        self.dialog_content = ItemConfirm()
        self.dialog_content.ids.task_input.text = current_text
        if current_date: self.dialog_content.ids.date_label.text = current_date
        
        if ":" in current_time:
            h, m = current_time.split(":")
            self.dialog_content.ids.hour_input.text = h.replace("PM","").replace("AM","").strip()
            self.dialog_content.ids.min_input.text = m[:2]
            if "PM" in current_time: self.dialog_content.ids.am_pm_button.text = "PM"

        self.task_dialog = MDDialog(
            title=self.lang_strings['title'], type="custom", content_cls=self.dialog_content,
            buttons=[
                MDFlatButton(text=self.lang_strings['cancel'], on_release=lambda x: self.task_dialog.dismiss()),
                MDRaisedButton(text=self.lang_strings['add'], on_release=self.save_task)
            ]
        )
        self.task_dialog.open()

    def save_task(self, *args):
        task_f = self.dialog_content.ids.task_input
        hour_f = self.dialog_content.ids.hour_input
        min_f = self.dialog_content.ids.min_input
        task_f.error = hour_f.error = min_f.error = False
        content = task_f.text.strip()
        h_text, m_text = hour_f.text.strip(), min_f.text.strip()
        
        if not content:
            task_f.helper_text = self.lang_strings['err_empty']
            task_f.error = True; return

        time_str, final_date = "", self.selected_date
        if h_text or m_text:
            try:
                h = int(h_text) if h_text else 0
                m = int(m_text) if m_text else 0
                has_error = False
                if self.is_24h_mode:
                    if not (0 <= h <= 23): hour_f.helper_text = "0-23"; hour_f.error = has_error = True
                else:
                    if not (1 <= h <= 12): hour_f.helper_text = "1-12"; hour_f.error = has_error = True
                if not (0 <= m <= 59): min_f.helper_text = "0-59"; min_f.error = has_error = True
                
                if not has_error:
                    if not final_date: final_date = datetime.now().strftime("%d/%m/%Y")
                    if final_date == datetime.now().strftime("%d/%m/%Y"):
                        h_24 = h
                        if not self.is_24h_mode:
                            ap = self.dialog_content.ids.am_pm_button.text
                            if ap == "PM" and h < 12: h_24 += 12
                            if ap == "AM" and h == 12: h_24 = 0
                        now = datetime.now()
                        if h_24 < now.hour or (h_24 == now.hour and m < now.minute):
                            hour_f.helper_text = self.lang_strings['err_past']
                            hour_f.error = min_f.error = has_error = True
                if has_error: return
                time_str = f"{str(h).zfill(2)}:{str(m).zfill(2)}"
                if not self.is_24h_mode: time_str += f" {self.dialog_content.ids.am_pm_button.text}"
            except ValueError:
                hour_f.error = True; return

        if self.editing_id:
            self.cursor.execute("UPDATE tasks SET content=?, task_time=?, task_date=? WHERE id=?", (content, time_str, final_date, self.editing_id))
        else:
            self.cursor.execute("INSERT INTO tasks (content, is_done, task_time, task_date) VALUES (?, 0, ?, ?)", (content, time_str, final_date))
        self.conn.commit(); self.load_tasks(); self.task_dialog.dismiss(); self.selected_date = ""

    def show_settings_menu(self, *args):
        if getattr(self, 'sub_dialog', None): self.sub_dialog.dismiss()
        if getattr(self, 'settings_dialog', None): self.settings_dialog.dismiss()
        opts = [(self.lang_strings['lang_opt'], "translate", "lang"), (self.lang_strings['theme_opt'], "theme-light-dark", "theme"), (self.lang_strings['format_opt'], "clock-outline", "format"), (self.lang_strings['color_opt'], "palette", "color_picker")]
        items = [OneLineAvatarIconListItem(text=t, on_release=self.open_pro_color_picker if m=="color_picker" else lambda x, mo=m: self.open_setting_tab(mo)) for t, i, m in opts]
        for i, item in enumerate(items): item.add_widget(IconLeftWidget(icon=opts[i][1]))
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
        
        # Tên hiển thị ngôn ngữ chuẩn
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
        self.color_dialog = MDDialog(title=self.lang_strings['color_opt'], type="custom", content_cls=self.color_content, buttons=[MDFlatButton(text="OK", on_release=self.save_color)])
        self.color_dialog.open()

    def update_live_ui(self, color): self.color_content.ids.color_preview.md_bg_color = color

    def save_color(self, *args):
        hex_val = get_hex_from_color(self.color_content.ids.color_preview.md_bg_color)
        self.cursor.execute("UPDATE settings SET value=? WHERE key='color'", (hex_val,)); self.conn.commit()
        self.apply_ui_color(hex_val); self.color_dialog.dismiss(); self.show_settings_menu()

    def show_date_picker(self):
        try:
            from kivymd.uix.pickers import MDDatePicker
            d = MDDatePicker()
            d.bind(on_save=lambda x, v, dr: self.set_date(v))
            d.open()
        except: pass

    def set_date(self, v):
        self.selected_date = v.strftime("%d/%m/%Y")
        if hasattr(self, 'dialog_content'): self.dialog_content.ids.date_label.text = self.selected_date

    def delete_task(self, i): self.cursor.execute("DELETE FROM tasks WHERE id=?", (i,)); self.conn.commit(); self.load_tasks()
    def mark_task(self, i, a): self.cursor.execute("UPDATE tasks SET is_done=? WHERE id=?", (1 if a else 0, i)); self.conn.commit(); self.load_tasks()

if __name__ == "__main__":
    ChecklistApp().run()
