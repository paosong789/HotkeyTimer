"""HotkeyTimer - 全域快捷鍵循環倒數計時器

功能：
- 可新增多個計時器，每個計時器可設定名稱、倒數秒數、觸發按鍵（單一按鍵）
- 按下觸發按鍵（任何視窗下皆有效）即從目標秒數開始倒數
- 倒數到 0 後自動從目標秒數重新開始，並播放提示音
- 倒數中再按一次觸發按鍵，會從目標秒數重新開始
- 停止 / 刪除只能用滑鼠操作，刪除前會再次確認
- 設定自動儲存於 config.json
"""

import json
import math
import os
import queue
import time
import tkinter as tk
import uuid
import winsound
from tkinter import messagebox, ttk

from pynput import keyboard

APP_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(APP_DIR, "config.json")

MIN_SECONDS = 1
MAX_SECONDS = 86400
WARN_SECONDS = 10   # 剩餘秒數小於等於此值時以黃色顯示
DEFAULT_NOTIFY = 10  # 預設剩幾秒時語音提醒
DANGER_SECONDS = 5  # 剩餘秒數小於等於此值時以紅色顯示
TICK_MS = 50

# 外觀
BG = "#1b1d2a"
CARD_BG = "#272a3b"
CARD_BORDER = "#363a52"
RING_TRACK = "#3a3e55"
COLOR_IDLE = "#7c8099"
COLOR_RUN = "#3ddc84"
COLOR_WARN = "#ffc83d"
COLOR_DANGER = "#ff4d5e"
TEXT_MAIN = "#f2f3f8"
TEXT_SUB = "#8e93ad"
ICON = "#8e93ad"
ICON_HOVER = "#ffffff"

FONT_UI = "Microsoft JhengHei UI"
FONT_NUM = "Segoe UI"

# 卡片以寬 200 為基準設計，實際大小依視窗等比例縮放
BASE_W = 200
CARD_RATIO = 1.07  # 高 / 寬
CARD_GAP = 10
MIN_CARD_W = 60

MIN_ALPHA = 20  # 透明度下限（%）


# ---------------------------------------------------------------------------
# 工具函式
# ---------------------------------------------------------------------------

def key_to_name(key):
    """將 pynput 的按鍵物件轉成穩定的字串名稱（例如 'f1'、'a'、'num5'）。"""
    if isinstance(key, keyboard.Key):
        return key.name
    vk = getattr(key, "vk", None)
    if vk is not None:
        if 96 <= vk <= 105:
            return f"num{vk - 96}"
        # 以虛擬鍵碼判斷英數字，避免按住 Ctrl/Shift 時字元改變
        if 65 <= vk <= 90 or 48 <= vk <= 57:
            return chr(vk).lower()
    char = getattr(key, "char", None)
    if char and char.isprintable():
        return char.lower()
    if vk is not None:
        return f"vk{vk}"
    return None


def key_display(name):
    if not name:
        return "未設定"
    return name.replace("_", " ").upper()


def format_seconds(total):
    """一律以秒數顯示（例如 600，不轉成 10:00）。"""
    return str(int(total))


def truncate(text, limit=12):
    return text if len(text) <= limit else text[: limit - 1] + "…"


class Speaker:
    """使用 Windows 內建語音（SAPI）朗讀提醒，優先選用中文語音。"""

    SVSF_ASYNC = 1

    def __init__(self):
        self.voice = None
        try:
            import win32com.client
            self.voice = win32com.client.Dispatch("SAPI.SpVoice")
            voices = list(self.voice.GetVoices())
            for lang in ("404", "804", "C04"):  # 繁中（台灣）、簡中、繁中（香港）
                match = [v for v in voices if lang in v.GetAttribute("Language").split(";")]
                if match:
                    self.voice.Voice = match[0]
                    break
        except Exception:
            self.voice = None

    def say(self, text):
        if self.voice is not None:
            try:
                self.voice.Speak(text, self.SVSF_ASYNC)
                return
            except Exception:
                pass
        # 無法使用語音時改用系統提示音
        winsound.PlaySound("SystemExclamation", winsound.SND_ALIAS | winsound.SND_ASYNC)


def round_rect(canvas, x1, y1, x2, y2, r, **kw):
    pts = [
        x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r,
        x2, y2 - r, x2, y2, x2 - r, y2, x1 + r, y2,
        x1, y2, x1, y2 - r, x1, y1 + r, x1, y1,
    ]
    return canvas.create_polygon(pts, smooth=True, **kw)


def font(family, px, weight="normal"):
    """以像素指定字型大小（負值），方便隨卡片等比例縮放。"""
    return (family, -max(7, int(px)), weight)


def make_icon(canvas, x, y, text, command, px):
    item = canvas.create_text(x, y, text=text, fill=ICON, font=font(FONT_UI, px))
    canvas.tag_bind(item, "<Enter>", lambda e: (canvas.itemconfigure(item, fill=ICON_HOVER),
                                               canvas.configure(cursor="hand2")))
    canvas.tag_bind(item, "<Leave>", lambda e: (canvas.itemconfigure(item, fill=ICON),
                                               canvas.configure(cursor="")))
    canvas.tag_bind(item, "<Button-1>", lambda e: command())
    return item


# ---------------------------------------------------------------------------
# 計時器卡片
# ---------------------------------------------------------------------------

class TimerCard:
    def __init__(self, app, data):
        self.app = app
        self.id = data.get("id") or uuid.uuid4().hex
        self.name = data.get("name", "計時器")
        self.seconds = int(data.get("seconds", 60))
        self.key = data.get("key")
        self.sound = bool(data.get("sound", True))
        self.notify = int(data.get("notify", DEFAULT_NOTIFY))  # 剩幾秒時語音提醒
        # 執行狀態
        self.start = None
        self.run_seconds = self.seconds
        self.cycle = 0
        self.announced = -1

        self.canvas = tk.Canvas(app.view, bg=BG, highlightthickness=0)
        self.canvas.bind("<Double-Button-1>", lambda e: SettingsDialog(app, self))
        self.canvas.bind("<Button-3>", lambda e: app.show_menu(e, self))
        self.width = 0
        self.resize(BASE_W)

    def resize(self, w):
        """依卡片寬度重新繪製所有元素。"""
        if w == self.width:
            return
        self.width = w
        s = w / BASE_W
        h = int(w * CARD_RATIO)
        c = self.canvas
        c.delete("all")
        c.configure(width=w, height=h)

        round_rect(c, 1, 1, w - 1, h - 1, 18 * s, fill=CARD_BG, outline=CARD_BORDER, width=1)
        # 大數字
        self.num = c.create_text(w / 2, 82 * s, text="--", fill=COLOR_IDLE)
        # 細進度條
        self.bar_x1, self.bar_x2 = 22 * s, w - 22 * s
        bar_y1, bar_y2 = 142 * s, 142 * s + max(2, 3 * s)
        c.create_rectangle(self.bar_x1, bar_y1, self.bar_x2, bar_y2, fill=RING_TRACK, width=0)
        self.bar = c.create_rectangle(self.bar_x1, bar_y1, self.bar_x1, bar_y2,
                                      fill=COLOR_RUN, width=0)
        # 名稱與按鍵
        self.title = c.create_text(w / 2, 170 * s, fill=TEXT_MAIN,
                                   font=font(FONT_UI, 27 * s, "bold"))
        self.key_text = c.create_text(w / 2, 199 * s, fill=TEXT_SUB, font=font(FONT_UI, 15 * s))
        # 圖示按鈕（只能用滑鼠操作）
        make_icon(c, 18 * s, 18 * s, "■", self.stop, px=13 * s)
        make_icon(c, w - 18 * s, 18 * s, "⚙", lambda: SettingsDialog(self.app, self), px=17 * s)

        self.refresh_labels()
        self.tick(time.monotonic())

    def refresh_labels(self):
        self.canvas.itemconfigure(self.title, text=truncate(self.name))
        sound = "" if self.sound else "  🔇"
        self.canvas.itemconfigure(
            self.key_text, text=f"按鍵 {key_display(self.key)} ・ {self.seconds} 秒{sound}"
        )

    def to_dict(self):
        return {"id": self.id, "name": self.name, "seconds": self.seconds,
                "key": self.key, "sound": self.sound, "notify": self.notify}

    # --- 計時 ---------------------------------------------------------------

    def trigger(self):
        """每次按下觸發按鍵，都從目標秒數重新開始倒數。"""
        self.run_seconds = self.seconds
        self.start = time.monotonic()
        self.cycle = 0
        self.announced = -1

    def stop(self):
        self.start = None

    def _set_number(self, text, color):
        s = self.width / BASE_W
        px = 92 if len(text) <= 3 else 72 if len(text) <= 4 else 58 if len(text) <= 5 else 42
        self.canvas.itemconfigure(self.num, text=text, fill=color,
                                  font=font(FONT_NUM, px * s, "bold"))

    def _set_bar(self, fraction, color):
        x = self.bar_x1 + (self.bar_x2 - self.bar_x1) * fraction
        y1, y2 = self.canvas.coords(self.bar)[1::2]
        self.canvas.coords(self.bar, self.bar_x1, y1, x, y2)
        self.canvas.itemconfigure(self.bar, fill=color)

    def tick(self, now):
        if self.start is None:
            self._set_number("--", COLOR_IDLE)
            self._set_bar(0, COLOR_IDLE)
            return

        elapsed = now - self.start
        # 倒數到 0 後自動重新開始
        cycle = int(elapsed // self.run_seconds)
        left = self.run_seconds - (elapsed - cycle * self.run_seconds)
        # 四捨五入：一輪剛好等於目標秒數，會顯示目標秒數 → 0
        shown = math.floor(left + 0.5)

        # 剩 10 秒時語音提醒（每輪一次；目標秒數需大於 10 秒）
        if (self.sound and self.run_seconds > self.notify
                and shown <= self.notify and self.announced != cycle):
            self.announced = cycle
            self.app.speaker.say(f"注意 {self.name}")

        if shown <= DANGER_SECONDS:
            color = COLOR_DANGER
        elif shown <= WARN_SECONDS:
            color = COLOR_WARN
        else:
            color = COLOR_RUN
        self._set_number(format_seconds(shown), color)
        self._set_bar(left / self.run_seconds, color)


# ---------------------------------------------------------------------------
# 設定視窗
# ---------------------------------------------------------------------------

class SettingsDialog(tk.Toplevel):
    def __init__(self, app, card):
        super().__init__(app.root)
        self.app = app
        self.card = card
        self.new_key = card.key

        self.title("計時器設定")
        self.resizable(False, False)
        self.transient(app.root)

        body = ttk.Frame(self, padding=18)
        body.pack(fill="both", expand=True)

        self.name_var = tk.StringVar(value=card.name)
        self.seconds_var = tk.StringVar(value=str(card.seconds))
        self.sound_var = tk.BooleanVar(value=card.sound)
        self.notify_var = tk.StringVar(value=str(card.notify))

        ttk.Label(body, text="名稱").grid(row=0, column=0, sticky="w", pady=6)
        name_entry = ttk.Entry(body, textvariable=self.name_var, width=22)
        name_entry.grid(row=0, column=1, sticky="we", pady=6)

        ttk.Label(body, text="倒數秒數").grid(row=1, column=0, sticky="w", pady=6)
        ttk.Spinbox(body, from_=MIN_SECONDS, to=MAX_SECONDS, textvariable=self.seconds_var,
                    width=10).grid(row=1, column=1, sticky="w", pady=6)

        ttk.Label(body, text="觸發按鍵").grid(row=2, column=0, sticky="w", pady=6)
        self.key_btn = ttk.Button(body, text=key_display(self.new_key), width=16,
                                  command=self.capture_key)
        self.key_btn.grid(row=2, column=1, sticky="w", pady=6)

        ttk.Label(body, text="語音提醒").grid(row=3, column=0, sticky="w", pady=6)
        ttk.Checkbutton(body, text="開啟（唸「注意 名稱」）", variable=self.sound_var,
                        command=self.update_notify_state).grid(row=3, column=1, sticky="w", pady=6)

        ttk.Label(body, text="提醒時間").grid(row=4, column=0, sticky="w", pady=6)
        notify_row = ttk.Frame(body)
        notify_row.grid(row=4, column=1, sticky="w", pady=6)
        ttk.Label(notify_row, text="剩").pack(side="left")
        self.notify_spin = ttk.Spinbox(notify_row, from_=0, to=MAX_SECONDS,
                                       textvariable=self.notify_var, width=6)
        self.notify_spin.pack(side="left", padx=4)
        ttk.Label(notify_row, text="秒時提醒").pack(side="left")
        self.update_notify_state()

        btns = ttk.Frame(body)
        btns.grid(row=5, column=0, columnspan=2, sticky="we", pady=(14, 0))
        ttk.Button(btns, text="刪除計時器", command=self.delete).pack(side="left")
        ttk.Button(btns, text="儲存", command=self.save).pack(side="right")
        ttk.Button(btns, text="取消", command=self.close).pack(side="right", padx=6)

        self.protocol("WM_DELETE_WINDOW", self.close)
        self.bind("<Return>", lambda e: self.save())

        self.update_idletasks()
        x = app.root.winfo_rootx() + (app.root.winfo_width() - self.winfo_width()) // 2
        y = app.root.winfo_rooty() + (app.root.winfo_height() - self.winfo_height()) // 3
        self.geometry(f"+{max(x, 0)}+{max(y, 0)}")
        self.grab_set()
        name_entry.focus_set()

    def update_notify_state(self):
        self.notify_spin.configure(state="normal" if self.sound_var.get() else "disabled")

    def capture_key(self):
        self.key_btn.configure(text="請按任意鍵…（Esc 取消）")
        self.app.begin_capture(self.on_key_captured)

    def on_key_captured(self, name):
        if name is not None:
            self.new_key = name
        self.key_btn.configure(text=key_display(self.new_key))

    def save(self):
        try:
            seconds = int(self.seconds_var.get())
        except ValueError:
            seconds = 0
        if not MIN_SECONDS <= seconds <= MAX_SECONDS:
            messagebox.showerror("秒數錯誤", f"請輸入 {MIN_SECONDS} ~ {MAX_SECONDS} 之間的整數",
                                 parent=self)
            return
        card = self.card
        notify = card.notify
        if self.sound_var.get():
            try:
                notify = int(self.notify_var.get())
            except ValueError:
                notify = -1
            if not 0 <= notify < seconds:
                messagebox.showerror("提醒時間錯誤",
                                     f"提醒時間請輸入 0 ~ {seconds - 1} 之間的整數\n"
                                     f"（需小於倒數秒數 {seconds} 秒）", parent=self)
                return
        card.name = self.name_var.get().strip() or "計時器"
        card.seconds = seconds
        card.key = self.new_key
        card.sound = self.sound_var.get()
        card.notify = notify
        card.refresh_labels()
        self.app.save()
        self.close()

    def delete(self):
        if messagebox.askyesno("刪除計時器", f"確定要刪除「{self.card.name}」嗎？", parent=self):
            self.app.remove_timer(self.card)
            self.close()

    def close(self):
        self.app.cancel_capture()
        self.grab_release()
        self.destroy()


# ---------------------------------------------------------------------------
# 主程式
# ---------------------------------------------------------------------------

class App:
    def __init__(self, root):
        self.root = root
        self.timers = []
        self.capture_cb = None
        self.events = queue.Queue()
        self.pressed = set()
        self._loading = True

        self.speaker = Speaker()

        root.title("HotkeyTimer（右鍵新增）")
        root.geometry("460x220")
        root.minsize(160, 120)
        root.configure(bg=BG)

        # 卡片區：所有卡片排成一列，隨視窗大小等比例縮放
        self.view = tk.Frame(root, bg=BG)
        self.view.pack(fill="both", expand=True)
        self.view.bind("<Configure>", lambda e: self.layout())
        self.view.bind("<Button-3>", lambda e: self.show_menu(e))
        self.empty = tk.Label(self.view, text="按滑鼠右鍵新增計時器",
                              bg=BG, fg=TEXT_SUB, font=(FONT_UI, 10))
        self.empty.bind("<Button-3>", lambda e: self.show_menu(e))

        config = self.load()
        window = config.get("window", {})
        self.topmost_var = tk.BooleanVar(value=window.get("topmost", True))
        self.alpha_var = tk.IntVar(value=max(MIN_ALPHA, min(100, int(window.get("alpha", 100)))))
        self.alpha_win = None
        self.apply_window_options()

        for data in config.get("timers", []):
            self.add_timer(data, open_settings=False)
        if not self.timers:
            self.add_timer({"name": "計時器 1", "seconds": 60, "key": "f1"}, open_settings=False)
        self._loading = False
        self.save()

        self.listener = keyboard.Listener(on_press=self._on_press, on_release=self._on_release)
        self.listener.daemon = True
        self.listener.start()

        root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.loop()

    # --- 版面 ---------------------------------------------------------------

    def layout(self):
        n = len(self.timers)
        if n == 0:
            self.empty.place(relx=0.5, rely=0.5, anchor="center")
            return
        self.empty.place_forget()
        vw, vh = self.view.winfo_width(), self.view.winfo_height()
        w = min((vw - CARD_GAP * (n + 1)) / n, (vh - CARD_GAP * 2) / CARD_RATIO)
        w = max(MIN_CARD_W, int(w))
        h = int(w * CARD_RATIO)
        x0 = (vw - (n * w + (n - 1) * CARD_GAP)) // 2
        y0 = max(0, (vh - h) // 2)
        for i, t in enumerate(self.timers):
            t.resize(w)
            t.canvas.place(x=x0 + i * (w + CARD_GAP), y=y0, width=w, height=h)

    # --- 設定檔 -------------------------------------------------------------

    def load(self):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError):
            return {}

    def save(self):
        if self._loading:
            return
        data = {
            "window": {"topmost": self.topmost_var.get(), "alpha": self.alpha_var.get()},
            "timers": [t.to_dict() for t in self.timers],
        }
        tmp = CONFIG_PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, CONFIG_PATH)

    # --- 計時器管理 ---------------------------------------------------------

    def add_timer(self, data=None, open_settings=True):
        if data is None:
            data = {"name": f"計時器 {len(self.timers) + 1}", "seconds": 60, "key": None}
        card = TimerCard(self, data)
        self.timers.append(card)
        self.layout()
        self.save()
        if open_settings and not self._loading:
            SettingsDialog(self, card)
        return card

    def remove_timer(self, card):
        card.canvas.destroy()
        self.timers.remove(card)
        self.layout()
        self.save()

    def show_menu(self, event, card=None):
        menu = tk.Menu(self.root, tearoff=0)
        if card is not None:
            menu.add_command(label=f"設定「{truncate(card.name)}」",
                             command=lambda: SettingsDialog(self, card))
            menu.add_command(label="停止", command=card.stop)
            menu.add_separator()
        menu.add_command(label="＋ 新增計時器", command=self.add_timer)
        menu.add_separator()
        menu.add_checkbutton(label="視窗置頂", variable=self.topmost_var,
                             command=self.on_window_option)
        menu.add_command(label=f"透明度…（{self.alpha_var.get()}%）",
                         command=lambda: self.open_alpha_window(event.x_root, event.y_root))
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def apply_window_options(self):
        self.root.attributes("-topmost", self.topmost_var.get())
        self.root.attributes("-alpha", self.alpha_var.get() / 100)

    def on_window_option(self):
        self.apply_window_options()
        self.save()

    def open_alpha_window(self, x, y):
        """透明度滑桿：拖動時即時套用，放開或關閉時儲存。"""
        if self.alpha_win is not None and self.alpha_win.winfo_exists():
            self.alpha_win.lift()
            return
        win = self.alpha_win = tk.Toplevel(self.root)
        win.title("透明度")
        win.resizable(False, False)
        win.transient(self.root)
        win.attributes("-topmost", True)

        frame = ttk.Frame(win, padding=14)
        frame.pack(fill="both", expand=True)
        label = ttk.Label(frame, text=f"{self.alpha_var.get()}%", width=5, anchor="e")

        def on_slide(value):
            self.alpha_var.set(int(float(value)))
            label.configure(text=f"{self.alpha_var.get()}%")
            self.apply_window_options()

        scale = ttk.Scale(frame, from_=MIN_ALPHA, to=100, length=220, command=on_slide)
        scale.set(self.alpha_var.get())
        scale.pack(side="left")
        label.pack(side="left", padx=(8, 0))
        scale.bind("<ButtonRelease-1>", lambda e: self.save())

        def close():
            self.save()
            win.destroy()

        win.protocol("WM_DELETE_WINDOW", close)
        win.bind("<Escape>", lambda e: close())
        win.geometry(f"+{x}+{y}")
        scale.focus_set()

    def begin_capture(self, callback):
        self.capture_cb = callback

    def cancel_capture(self):
        self.capture_cb = None

    # --- 鍵盤事件（pynput 執行緒 → 主執行緒）---------------------------------

    def _on_press(self, key):
        name = key_to_name(key)
        if name is None or name in self.pressed:
            return  # 忽略按住不放時的自動重複
        self.pressed.add(name)
        self.events.put(name)

    def _on_release(self, key):
        self.pressed.discard(key_to_name(key))

    def handle_key(self, name):
        if self.capture_cb is not None:
            cb, self.capture_cb = self.capture_cb, None
            cb(None if name == "esc" else name)
            return
        # 在本程式的輸入框打字時不觸發計時器
        if isinstance(self.root.focus_get(), (tk.Entry, ttk.Entry, ttk.Spinbox, tk.Spinbox)):
            return
        for t in self.timers:
            if t.key == name:
                t.trigger()

    def loop(self):
        while True:
            try:
                name = self.events.get_nowait()
            except queue.Empty:
                break
            self.handle_key(name)
        now = time.monotonic()
        for t in self.timers:
            t.tick(now)
        self._after_id = self.root.after(TICK_MS, self.loop)

    def on_close(self):
        self.save()
        self.root.after_cancel(self._after_id)
        self.listener.stop()
        self.root.destroy()


def main():
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
