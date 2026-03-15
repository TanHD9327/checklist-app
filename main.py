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
            hint_text: app.lang_strings.get('hint_text', 'Việc cần làm...')
            mode: "rectangle"
            # helper_text chỉ hiện khi error=True
            helper_text: "Yêu cầu nội dung"
            helper_text_mode: "on_error"
            # Tự động tắt lỗi khi người dùng bắt đầu gõ lại
            on_text: self.error = False
    MDBoxLayout:
        adaptive_height: True
        spacing: "15dp"
        MDRaisedButton:
            text: app.lang_strings.get('pick_date', 'CHỌN NGÀY')
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
            on_text: self.error = False
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
            title: app.lang_strings.get('title', 'Ghi chú')
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

# --- CLASSES HỖ TRỢ ---
class RightCheckbox(IRightBodyTouch, MDCheckbox):
    task_id = NumericProperty(None)
    def on_release(self): MDApp.get_running_app().mark_task(self, self.active)

class ListItemWithCheckbox(TwoLineAvatarIconListItem):
    db_id = NumericProperty(None)

class LeftCheckbox(ILeftBodyTouch, MDCheckbox): pass

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

class SettingListContent(MDBoxLayout): pass
class CustomColorContent(MDBoxLayout): pass
class ItemConfirm(MDBoxLayout): pass

# --- MAIN APP ---
class ChecklistApp(MDApp):
    lang_strings = DictProperty()
    selected_date = StringProperty("")
    is_24h_mode = BooleanProperty(True)

    def build(self):
        self.init_db()
        return Builder.load_string(KV)

    def on_start(self):
        self.load_settings()
        self.load_tasks()

    def init_db(self):
        db_path = os.path.join(self.user_data_dir, "checklist_pro.db")
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.cursor = self.conn.cursor()
        
        # Tạo bảng nếu chưa có
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS tasks 
            (id INTEGER PRIMARY KEY AUTOINCREMENT, 
             content TEXT, 
             is_done INTEGER, 
             task_time TEXT, 
             task_date TEXT, 
             done_timestamp TEXT)''')

        # KIỂM TRA VÀ THÊM CỘT done_timestamp NẾU THIẾU (Dành cho DB cũ)
        self.cursor.execute("PRAGMA table_info(tasks)")
        columns = [column[1] for column in self.cursor.fetchall()]
        if 'done_timestamp' not in columns:
            self.cursor.execute("ALTER TABLE tasks ADD COLUMN done_timestamp TEXT DEFAULT ''")
            
        # Các cài đặt khác giữ nguyên...
        self.cursor.execute('CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)')
        self.conn.commit()

    def get_sort_time(self, t_time):
        if not t_time: return "99:99"
        try:
            if "AM" in t_time or "PM" in t_time:
                return datetime.strptime(t_time, "%I:%M %p").strftime("%H:%M")
            return t_time
        except: return "99:99"

    def load_tasks(self, *args):
        container = self.root.ids.container
        container.clear_widgets()
        
        # Sắp xếp theo thứ tự ưu tiên: 1.Trống, 2.Giờ, 3.Ngày, 4.Cả hai
        g1, g2, g3, g4, g_arch = [], [], [], [], []

        self.cursor.execute("SELECT * FROM tasks")
        for row in self.cursor.fetchall():
            _, _, is_done, t_time, t_date, _ = row
            if is_done == 1: g_arch.append(row)
            elif not t_date and not t_time: g1.append(row)
            elif not t_date and t_time: g2.append(row)
            elif t_date and not t_time: g3.append(row)
            else: g4.append(row)

        g2.sort(key=lambda x: self.get_sort_time(x[3]))
        g3.sort(key=lambda x: datetime.strptime(x[4], "%d/%m/%Y"))
        g4.sort(key=lambda x: (datetime.strptime(x[4], "%d/%m/%Y"), self.get_sort_time(x[3])))

        for r in g1 + g2 + g3 + g4:
            self.add_item_ui(r, container)

        if g_arch:
            content_box = MDBoxLayout(orientation="vertical", adaptive_height=True)
            for r in g_arch: self.add_item_ui(r, content_box)
            header = MDExpansionPanelOneLine(text=self.lang_strings.get('archive'))
            container.add_widget(MDExpansionPanel(icon="archive-outline", content=content_box, panel_cls=header))

    def add_item_ui(self, row, container):
        t_id, content, is_done, t_time, t_date, _ = row
        text_disp = f"[s]{content}[/s]" if is_done else content
        item = ListItemWithCheckbox(text=text_disp, secondary_text=f"{t_date} {t_time}".strip(), db_id=t_id)
        if is_done: item.theme_text_color = "Hint"
        del_btn = IconLeftWidget(icon="delete-outline", theme_text_color="Custom", text_color=(1,0,0,1))
        del_btn.bind(on_release=lambda x, i=t_id: self.delete_task(i))
        item.add_widget(del_btn)
        item.add_widget(RightCheckbox(task_id=t_id, active=bool(is_done)))
        item.bind(on_release=lambda x, i=t_id, c=content, ti=t_time, da=t_date: self.show_task_dialog(i, c, ti, da))
        container.add_widget(item)

    def save_task(self, *args):
        # Kiểm tra nội dung
        content = self.dialog_content.ids.task_input.text.strip()
        if not content:
            self.dialog_content.ids.task_input.error = True
            return

        # Kiểm tra thời gian
        h_val = self.dialog_content.ids.hour_input.text.strip()
        m_val = self.dialog_content.ids.min_input.text.strip()
        t_str = ""

        if h_val or m_val:
            try:
                h, m = int(h_val or 0), int(m_val or 0)
                is_valid = True
                if self.is_24h_mode and (h < 0 or h > 23):
                    self.dialog_content.ids.hour_input.error = True
                    self.dialog_content.ids.hour_input.helper_text = "0 - 23"
                    is_valid = False
                elif not self.is_24h_mode and (h < 1 or h > 12):
                    self.dialog_content.ids.hour_input.error = True
                    self.dialog_content.ids.hour_input.helper_text = "1 - 12"
                    is_valid = False
                if m < 0 or m > 59:
                    self.dialog_content.ids.min_input.error = True
                    self.dialog_content.ids.min_input.helper_text = "0 - 59"
                    is_valid = False
                
                if not is_valid: return
                t_str = f"{str(h).zfill(2)}:{str(m).zfill(2)}"
                if not self.is_24h_mode: t_str += f" {self.dialog_content.ids.am_pm_button.text}"
            except: return

        if self.editing_id:
            self.cursor.execute("UPDATE tasks SET content=?, task_time=?, task_date=? WHERE id=?", (content, t_str, self.selected_date, self.editing_id))
        else:
            self.cursor.execute("INSERT INTO tasks (content, is_done, task_time, task_date, done_timestamp) VALUES (?, 0, ?, ?, '')", (content, t_str, self.selected_date))
        self.conn.commit()
        self.load_tasks()
        self.task_dialog.dismiss()

    def mark_task(self, checkbox, active):
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S") if active else ""
        self.cursor.execute("UPDATE tasks SET is_done=?, done_timestamp=? WHERE id=?", (1 if active else 0, ts, checkbox.task_id))
        self.conn.commit()
        list_item = checkbox.parent.parent
        content = list_item.text.replace("[s]", "").replace("[/s]", "")
        list_item.text = f"[s]{content}[/s]" if active else content
        list_item.theme_text_color = "Hint" if active else "Primary"

    def delete_task(self, i):
        self.cursor.execute("DELETE FROM tasks WHERE id=?", (i,))
        self.conn.commit()
        self.load_tasks()

    def load_settings(self):
        self.cursor.execute("SELECT value FROM settings WHERE key='lang'")
        res = self.cursor.fetchone()
        lang = res[0] if res else "Vietnamese"
        LANG_DATA = {
            "English": {"title": "Checklist", "archive": "Archive Box", "hint_text": "Task...", "add": "SAVE", "cancel": "CANCEL", "settings": "Settings", "lang_opt": "Language", "theme_opt": "Theme", "color_opt": "App Color", "format_opt": "Format", "pick_date": "DATE"},
            "Vietnamese": {"title": "Ghi chú", "archive": "Hòm lưu trữ", "hint_text": "Việc cần làm...", "add": "LƯU", "cancel": "HỦY", "settings": "Cài đặt", "lang_opt": "Ngôn ngữ", "theme_opt": "Giao diện", "color_opt": "Màu ứng dụng", "format_opt": "Định dạng", "pick_date": "CHỌN NGÀY"}
        }
        self.lang_strings = LANG_DATA.get(lang)
        self.root.ids.toolbar.title = self.lang_strings.get('title')
        self.cursor.execute("SELECT value FROM settings WHERE key='theme'")
        res = self.cursor.fetchone()
        if res: self.theme_cls.theme_style = res[0]
        self.cursor.execute("SELECT value FROM settings WHERE key='color'")
        res = self.cursor.fetchone()
        if res: self.apply_ui_color(res[0])
        self.cursor.execute("SELECT value FROM settings WHERE key='format'")
        res = self.cursor.fetchone()
        self.is_24h_mode = (res[0] == "24") if res else True

    def apply_ui_color(self, hex_c):
        c = get_color_from_hex(hex_c)
        if self.root:
            self.root.ids.toolbar.md_bg_color = c
            self.root.ids.fab.md_bg_color = c

    def show_task_dialog(self, task_id=None, current_text="", current_time="", current_date=""):
        self.editing_id = task_id; self.selected_date = current_date
        self.dialog_content = ItemConfirm()
        self.dialog_content.ids.task_input.text = current_text
        if current_date: self.dialog_content.ids.date_label.text = current_date
        if current_time and ":" in current_time:
            p = current_time.replace(" AM","").replace(" PM","").split(":")
            self.dialog_content.ids.hour_input.text, self.dialog_content.ids.min_input.text = p[0], p[1]
            if "PM" in current_time: self.dialog_content.ids.am_pm_button.text = "PM"
        self.task_dialog = MDDialog(
            title=self.lang_strings['title'], type="custom", content_cls=self.dialog_content,
            buttons=[MDFlatButton(text=self.lang_strings['cancel'], on_release=lambda x: self.task_dialog.dismiss()),
                     MDRaisedButton(text=self.lang_strings['add'], on_release=self.save_task)])
        self.task_dialog.open()

    def show_settings_menu(self, *args):
        opts = [(self.lang_strings['lang_opt'], "translate", "lang"), (self.lang_strings['theme_opt'], "theme-light-dark", "theme"), (self.lang_strings['format_opt'], "clock-outline", "format"), (self.lang_strings['color_opt'], "palette", "color_picker")]
        items = [OneLineAvatarIconListItem(text=t, on_release=self.open_pro_color_picker if m=="color_picker" else lambda x, mo=m: self.open_setting_tab(mo)) for t, i, m in opts]
        for i, item in enumerate(items): item.add_widget(IconLeftWidget(icon=opts[i][1]))
        self.settings_dialog = MDDialog(title=self.lang_strings['settings'], type="simple", items=items); self.settings_dialog.open()

    def open_setting_tab(self, mode):
        self.settings_dialog.dismiss(); self.setting_content = SettingListContent()
        self.sub_dialog = MDDialog(title="", type="custom", content_cls=self.setting_content); self.refresh_sub_list(mode); self.sub_dialog.open()

    def refresh_sub_list(self, mode):
        container = self.setting_content.ids.list_container; container.clear_widgets()
        db_k = 'lang' if mode=='lang' else 'theme' if mode=='theme' else 'format'
        self.cursor.execute("SELECT value FROM settings WHERE key=?", (db_k,)); res = self.cursor.fetchone()
        curr = res[0] if res else ""
        opts = [("Tiếng Việt", "Vietnamese"), ("English", "English")] if mode=="lang" else [("Light", "Light"), ("Dark", "Dark")] if mode=="theme" else [("12h", "12"), ("24h", "24")]
        for txt, k in opts:
            item = OneLineAvatarIconListItem(text=txt, on_release=lambda x, m=mode, val=k: self.update_setting(m, val))
            item.add_widget(LeftCheckbox(group="g", active=(curr == k))); container.add_widget(item)

    def update_setting(self, mode, val):
        db_k = 'lang' if mode=='lang' else 'theme' if mode=='theme' else 'format'
        self.cursor.execute(f"UPDATE settings SET value='{val}' WHERE key='{db_k}'"); self.conn.commit()
        self.sub_dialog.dismiss(); self.load_settings(); self.load_tasks()

    def open_pro_color_picker(self, *args):
        self.settings_dialog.dismiss(); self.color_content = CustomColorContent()
        self.color_dialog = MDDialog(title=self.lang_strings['color_opt'], type="custom", content_cls=self.color_content, buttons=[MDFlatButton(text="OK", on_release=self.save_color)])
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
