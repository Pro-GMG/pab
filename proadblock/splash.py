import queue
import threading
import tkinter as tk
from tkinter import font as tkfont

from . import config

BG = "#0d0f12"
PANEL = "#16191d"
BORDER = "#2a2f36"
TEXT = "#eef1f4"
MUTED = "#8b95a1"
RED = "#e0262b"
GREEN = "#29c46a"

WIDTH, HEIGHT = 380, 260


class Splash:
    """Small always-on-top boot window shown immediately on launch, while the
    DNS proxy / web panel / tray icon are still starting up in the background."""

    def __init__(self):
        self._queue: queue.Queue = queue.Queue()
        self._done = threading.Event()
        self._error: str | None = None
        self.root: tk.Tk | None = None

    def set_status(self, text: str) -> None:
        self._queue.put(("status", text))

    def fail(self, text: str) -> None:
        self._queue.put(("error", text))

    def close(self) -> None:
        self._queue.put(("done", None))

    def finish(self, text: str) -> None:
        """Shows a final 'setup complete' screen with an OK button; the window
        stays open until the user dismisses it."""
        self._queue.put(("finish", text))

    def _build(self) -> None:
        root = tk.Tk()
        self.root = root
        root.title("ProAdBlock")
        root.configure(bg=BG)
        root.overrideredirect(True)
        root.attributes("-topmost", True)
        root.resizable(False, False)

        sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
        x, y = (sw - WIDTH) // 2, (sh - HEIGHT) // 2
        root.geometry(f"{WIDTH}x{HEIGHT}+{x}+{y}")

        card = tk.Frame(root, bg=PANEL, highlightbackground=BORDER, highlightthickness=1)
        card.place(x=0, y=0, width=WIDTH, height=HEIGHT)

        try:
            from PIL import Image, ImageTk
            img = Image.open(config.ICON_FILE).resize((64, 64))
            self._logo = ImageTk.PhotoImage(img)
            tk.Label(card, image=self._logo, bg=PANEL).pack(pady=(28, 10))
        except Exception:
            tk.Label(card, text="🛡", font=("Segoe UI", 32), bg=PANEL, fg=RED).pack(pady=(28, 10))

        title_font = tkfont.Font(family="Segoe UI", size=13, weight="bold")
        tk.Label(card, text="ProAdBlock", font=title_font, bg=PANEL, fg=TEXT).pack()

        self._status_var = tk.StringVar(value="Başlatılıyor...")
        tk.Label(card, textvariable=self._status_var, font=("Segoe UI", 9), bg=PANEL, fg=MUTED).pack(pady=(6, 14))

        bar_track = tk.Frame(card, bg=BORDER, height=4, width=WIDTH - 80)
        bar_track.pack()
        bar_track.pack_propagate(False)
        self._bar = tk.Frame(bar_track, bg=RED, height=4, width=0)
        self._bar.place(x=0, y=0)
        self._bar_x = 0
        self._bar_dir = 1

        self._animate_bar()
        self._poll()
        root.mainloop()

    def _animate_bar(self) -> None:
        if not self.root or not self._bar.winfo_exists():
            return
        track_w = WIDTH - 80
        seg_w = 90
        self._bar_x += 6 * self._bar_dir
        if self._bar_x <= 0 or self._bar_x >= track_w - seg_w:
            self._bar_dir *= -1
        self._bar.place(x=self._bar_x, y=0, width=seg_w)
        self.root.after(20, self._animate_bar)

    def _poll(self) -> None:
        if not self.root:
            return
        try:
            while True:
                kind, payload = self._queue.get_nowait()
                if kind == "status":
                    self._status_var.set(payload)
                elif kind == "error":
                    self._status_var.set(payload)
                    close_btn = tk.Button(
                        self.root, text="Kapat", command=self.root.destroy,
                        bg=RED, fg="white", relief="flat", activebackground="#b81e22", cursor="hand2",
                    )
                    close_btn.place(x=WIDTH // 2 - 40, y=HEIGHT - 44, width=80, height=28)
                elif kind == "finish":
                    self._show_finish(payload)
                elif kind == "done":
                    self.root.destroy()
                    return
        except queue.Empty:
            pass
        self.root.after(80, self._poll)

    def _show_finish(self, message: str) -> None:
        root = self.root
        for w in root.winfo_children():
            w.destroy()

        card = tk.Frame(root, bg=PANEL, highlightbackground=GREEN, highlightthickness=1)
        card.place(x=0, y=0, width=WIDTH, height=HEIGHT)

        tk.Label(card, text="✅", font=("Segoe UI Emoji", 34), bg=PANEL, fg=GREEN).pack(pady=(24, 6))

        title_font = tkfont.Font(family="Segoe UI", size=14, weight="bold")
        tk.Label(card, text="Kurulum bitti!", font=title_font, bg=PANEL, fg=TEXT).pack()

        tk.Label(
            card, text=message, font=("Segoe UI", 9), bg=PANEL, fg=MUTED,
            wraplength=WIDTH - 60, justify="center",
        ).pack(pady=(8, 4), padx=20)

        self._arrow_var = tk.StringVar(value="⌄")
        arrow = tk.Label(card, textvariable=self._arrow_var, font=("Segoe UI", 16), bg=PANEL, fg=GREEN)
        arrow.pack(pady=(2, 8))
        self._arrow_step = 0
        self._animate_arrow(arrow)

        ok_btn = tk.Button(
            card, text="Tamam", command=root.destroy,
            bg=GREEN, fg="#04140a", relief="flat", activebackground="#22a85c",
            font=("Segoe UI", 9, "bold"), cursor="hand2",
        )
        ok_btn.place(x=WIDTH // 2 - 45, y=HEIGHT - 42, width=90, height=28)

    def _animate_arrow(self, widget: tk.Label) -> None:
        if not self.root or not widget.winfo_exists():
            return
        self._arrow_step = (self._arrow_step + 1) % 20
        offset = abs(10 - self._arrow_step)
        widget.pack_configure(pady=(2 + offset // 3, 8))
        self.root.after(60, lambda: self._animate_arrow(widget))

    def run_blocking(self) -> None:
        """Call from the main thread; blocks until close()/fail()+user-close."""
        self._build()
