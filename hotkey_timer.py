"""HotkeyTimer - looping countdown timers triggered by global hotkeys

Features:
- Multiple timers, each with its own name, countdown seconds and trigger key (single key)
- Pressing the trigger key (works in any window) starts counting down from the target
- After reaching 0 the timer automatically restarts from the target
- Pressing the trigger key again while running restarts from the target
- Voice reminder at a configurable number of seconds left
- Stop / delete are mouse-only; deleting asks for confirmation
- Settings are saved to config.json automatically
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
WARN_SECONDS = 10    # show yellow when this many seconds or fewer remain
DEFAULT_NOTIFY = 10  # default seconds-left for the voice reminder
DANGER_SECONDS = 5   # show red when this many seconds or fewer remain
TICK_MS = 50

# Appearance
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

FONT_UI = "Segoe UI"
FONT_NUM = "Segoe UI"

# Cards are designed at width 200 and scaled proportionally to the window
BASE_W = 200
CARD_RATIO = 1.07  # height / width
CARD_GAP = 10
MIN_CARD_W = 60

MIN_ALPHA = 20  # minimum window opacity (%)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def key_to_name(key):
    """Convert a pynput key into a stable string name (e.g. 'f1', 'a', 'num5')."""
    if isinstance(key, keyboard.Key):
        return key.name
    vk = getattr(key, "vk", None)
    if vk is not None:
        if 96 <= vk <= 105:
            return f"num{vk - 96}"
        # Use the virtual-key code for letters/digits so Ctrl/Shift don't change the name
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
        return "Not set"
    return name.replace("_", " ").upper()


def format_seconds(total):
    """Always display plain seconds (e.g. 600, never 10:00)."""
    return str(int(total))


def truncate(text, limit=12):
    return text if len(text) <= limit else text[: limit - 1] + "…"


class Speaker:
    """Speak reminders with the built-in Windows voice (SAPI), preferring a Chinese voice."""

    SVSF_ASYNC = 1

    def __init__(self):
        self.voice = None
        try:
            import win32com.client
            self.voice = win32com.client.Dispatch("SAPI.SpVoice")
            voices = list(self.voice.GetVoices())
            for lang in ("404", "804", "C04"):  # zh-TW, zh-CN, zh-HK
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
        # Fall back to a system sound when speech is unavailable
        winsound.PlaySound("SystemExclamation", winsound.SND_ALIAS | winsound.SND_ASYNC)


def round_rect(canvas, x1, y1, x2, y2, r, **kw):
    pts = [
        x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r,
        x2, y2 - r, x2, y2, x2 - r, y2, x1 + r, y2,
        x1, y2, x1, y2 - r, x1, y1 + r, x1, y1,
    ]
    return canvas.create_polygon(pts, smooth=True, **kw)


def font(family, px, weight="normal"):
    """Font sized in pixels (negative size) so it scales with the card."""
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
# Timer card
# ---------------------------------------------------------------------------

class TimerCard:
    def __init__(self, app, data):
        self.app = app
        self.id = data.get("id") or uuid.uuid4().hex
        self.name = data.get("name", "Timer")
        self.seconds = int(data.get("seconds", 60))
        self.key = data.get("key")
        self.sound = bool(data.get("sound", True))
        self.notify = int(data.get("notify", DEFAULT_NOTIFY))  # seconds left for voice reminder
        # Runtime state
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
        """Redraw every element for the given card width."""
        if w == self.width:
            return
        self.width = w
        s = w / BASE_W
        h = int(w * CARD_RATIO)
        c = self.canvas
        c.delete("all")
        c.configure(width=w, height=h)

        round_rect(c, 1, 1, w - 1, h - 1, 18 * s, fill=CARD_BG, outline=CARD_BORDER, width=1)
        # Big number
        self.num = c.create_text(w / 2, 82 * s, text="--", fill=COLOR_IDLE)
        # Thin progress bar
        self.bar_x1, self.bar_x2 = 22 * s, w - 22 * s
        bar_y1, bar_y2 = 142 * s, 142 * s + max(2, 3 * s)
        c.create_rectangle(self.bar_x1, bar_y1, self.bar_x2, bar_y2, fill=RING_TRACK, width=0)
        self.bar = c.create_rectangle(self.bar_x1, bar_y1, self.bar_x1, bar_y2,
                                      fill=COLOR_RUN, width=0)
        # Name and key
        self.title = c.create_text(w / 2, 170 * s, fill=TEXT_MAIN,
                                   font=font(FONT_UI, 27 * s, "bold"))
        self.key_text = c.create_text(w / 2, 199 * s, fill=TEXT_SUB, font=font(FONT_UI, 15 * s))
        # Icon buttons (mouse only)
        make_icon(c, 18 * s, 18 * s, "■", self.stop, px=13 * s)
        make_icon(c, w - 18 * s, 18 * s, "⚙", lambda: SettingsDialog(self.app, self), px=17 * s)

        self.refresh_labels()
        self.tick(time.monotonic())

    def refresh_labels(self):
        self.canvas.itemconfigure(self.title, text=truncate(self.name))
        sound = "" if self.sound else "  🔇"
        self.canvas.itemconfigure(
            self.key_text, text=f"Key {key_display(self.key)} · {self.seconds}s{sound}"
        )

    def to_dict(self):
        return {"id": self.id, "name": self.name, "seconds": self.seconds,
                "key": self.key, "sound": self.sound, "notify": self.notify}

    # --- Timing -------------------------------------------------------------

    def trigger(self):
        """Every press of the trigger key restarts the countdown from the target."""
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
        # Restart automatically after reaching 0
        cycle = int(elapsed // self.run_seconds)
        left = self.run_seconds - (elapsed - cycle * self.run_seconds)
        # Round half up: one cycle equals exactly the target, displayed as target -> 0
        shown = math.floor(left + 0.5)

        # Voice reminder once per cycle (target must be longer than the reminder time)
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
# Settings dialog
# ---------------------------------------------------------------------------

class SettingsDialog(tk.Toplevel):
    def __init__(self, app, card):
        super().__init__(app.root)
        self.app = app
        self.card = card
        self.new_key = card.key

        self.title("Timer Settings")
        self.resizable(False, False)
        self.transient(app.root)

        body = ttk.Frame(self, padding=18)
        body.pack(fill="both", expand=True)

        self.name_var = tk.StringVar(value=card.name)
        self.seconds_var = tk.StringVar(value=str(card.seconds))
        self.sound_var = tk.BooleanVar(value=card.sound)
        self.notify_var = tk.StringVar(value=str(card.notify))

        ttk.Label(body, text="Name").grid(row=0, column=0, sticky="w", pady=6, padx=(0, 10))
        name_entry = ttk.Entry(body, textvariable=self.name_var, width=22)
        name_entry.grid(row=0, column=1, sticky="we", pady=6)

        ttk.Label(body, text="Seconds").grid(row=1, column=0, sticky="w", pady=6, padx=(0, 10))
        ttk.Spinbox(body, from_=MIN_SECONDS, to=MAX_SECONDS, textvariable=self.seconds_var,
                    width=10).grid(row=1, column=1, sticky="w", pady=6)

        ttk.Label(body, text="Trigger key").grid(row=2, column=0, sticky="w", pady=6, padx=(0, 10))
        self.key_btn = ttk.Button(body, text=key_display(self.new_key), width=22,
                                  command=self.capture_key)
        self.key_btn.grid(row=2, column=1, sticky="w", pady=6)

        ttk.Label(body, text="Voice alert").grid(row=3, column=0, sticky="w", pady=6, padx=(0, 10))
        ttk.Checkbutton(body, text="On (says \"注意 <name>\")", variable=self.sound_var,
                        command=self.update_notify_state).grid(row=3, column=1, sticky="w", pady=6)

        ttk.Label(body, text="Alert at").grid(row=4, column=0, sticky="w", pady=6, padx=(0, 10))
        notify_row = ttk.Frame(body)
        notify_row.grid(row=4, column=1, sticky="w", pady=6)
        self.notify_spin = ttk.Spinbox(notify_row, from_=0, to=MAX_SECONDS,
                                       textvariable=self.notify_var, width=6)
        self.notify_spin.pack(side="left")
        ttk.Label(notify_row, text="seconds left").pack(side="left", padx=4)
        self.update_notify_state()

        btns = ttk.Frame(body)
        btns.grid(row=5, column=0, columnspan=2, sticky="we", pady=(14, 0))
        ttk.Button(btns, text="Delete timer", command=self.delete).pack(side="left")
        ttk.Button(btns, text="Save", command=self.save).pack(side="right")
        ttk.Button(btns, text="Cancel", command=self.close).pack(side="right", padx=6)

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
        self.key_btn.configure(text="Press any key… (Esc to cancel)")
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
            messagebox.showerror("Invalid seconds",
                                 f"Please enter a whole number from {MIN_SECONDS} to {MAX_SECONDS}.",
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
                messagebox.showerror("Invalid alert time",
                                     f"Alert time must be a whole number from 0 to {seconds - 1}\n"
                                     f"(less than the countdown of {seconds} seconds).",
                                     parent=self)
                return
        card.name = self.name_var.get().strip() or "Timer"
        card.seconds = seconds
        card.key = self.new_key
        card.sound = self.sound_var.get()
        card.notify = notify
        card.refresh_labels()
        self.app.save()
        self.close()

    def delete(self):
        if messagebox.askyesno("Delete timer", f"Delete \"{self.card.name}\"?", parent=self):
            self.app.remove_timer(self.card)
            self.close()

    def close(self):
        self.app.cancel_capture()
        self.grab_release()
        self.destroy()


# ---------------------------------------------------------------------------
# Main application
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

        root.title("HotkeyTimer (right-click to add)")
        root.geometry("460x220")
        root.minsize(160, 120)
        root.configure(bg=BG)

        # Card area: all cards in one row, scaled with the window
        self.view = tk.Frame(root, bg=BG)
        self.view.pack(fill="both", expand=True)
        self.view.bind("<Configure>", lambda e: self.layout())
        self.view.bind("<Button-3>", lambda e: self.show_menu(e))
        self.empty = tk.Label(self.view, text="Right-click to add a timer",
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
            self.add_timer({"name": "Timer 1", "seconds": 60, "key": "f1"}, open_settings=False)
        self._loading = False
        self.save()

        self.listener = keyboard.Listener(on_press=self._on_press, on_release=self._on_release)
        self.listener.daemon = True
        self.listener.start()

        root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.loop()

    # --- Layout -------------------------------------------------------------

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

    # --- Config file --------------------------------------------------------

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

    # --- Timer management ---------------------------------------------------

    def add_timer(self, data=None, open_settings=True):
        if data is None:
            data = {"name": f"Timer {len(self.timers) + 1}", "seconds": 60, "key": None}
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
            menu.add_command(label=f"Settings: {truncate(card.name)}",
                             command=lambda: SettingsDialog(self, card))
            menu.add_command(label="Stop", command=card.stop)
            menu.add_separator()
        menu.add_command(label="+ Add timer", command=self.add_timer)
        menu.add_separator()
        menu.add_checkbutton(label="Always on top", variable=self.topmost_var,
                             command=self.on_window_option)
        menu.add_command(label=f"Opacity… ({self.alpha_var.get()}%)",
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
        """Opacity slider: applied live while dragging, saved on release or close."""
        if self.alpha_win is not None and self.alpha_win.winfo_exists():
            self.alpha_win.lift()
            return
        win = self.alpha_win = tk.Toplevel(self.root)
        win.title("Opacity")
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

    # --- Keyboard events (pynput thread -> main thread) ---------------------

    def _on_press(self, key):
        name = key_to_name(key)
        if name is None or name in self.pressed:
            return  # ignore auto-repeat while a key is held down
        self.pressed.add(name)
        self.events.put(name)

    def _on_release(self, key):
        self.pressed.discard(key_to_name(key))

    def handle_key(self, name):
        if self.capture_cb is not None:
            cb, self.capture_cb = self.capture_cb, None
            cb(None if name == "esc" else name)
            return
        # Don't trigger timers while typing in this app's input fields
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
