"""Small native UI components with bounded, cancellable animations."""
import time
import tkinter as tk

BG = "#F3F7FD"
PANEL = "#FFFFFF"
EDGE = "#DFE8F5"
FG = "#111E32"
MUTED = "#526581"
ACCENT = "#0877F9"
CYAN = "#08B9E9"
NAVY = "#101C2F"
SOFT = "#EAF3FF"
RED = "#BF3549"


def blend(a, b, amount):
    a = [int(a[i:i+2], 16) for i in (1, 3, 5)]
    b = [int(b[i:i+2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y-x)*amount):02x}" for x, y in zip(a, b))


class MotionButton(tk.Button):
    def __init__(self, parent, *, motion=lambda: True, **kwargs):
        super().__init__(parent, **kwargs)
        self.motion = motion
        self.job = None
        self.rest_color = self.cget("bg")
        self.bind("<Enter>", self.enter, add="+")
        self.bind("<Leave>", self.leave, add="+")
        self.bind("<FocusIn>", lambda _: self.configure(highlightbackground=ACCENT), add="+")
        self.bind("<FocusOut>", lambda _: self.configure(highlightbackground=self.master.cget("bg")), add="+")
        self.bind("<Destroy>", self.cancel, add="+")

    def cancel(self, _=None):
        if self.job:
            self.after_cancel(self.job)
            self.job = None

    def enter(self, _):
        self.rest_color = self.cget("bg")
        self.animate(blend(self.rest_color, CYAN, .22))

    def leave(self, _):
        self.animate(self.rest_color)

    def animate(self, target):
        self.cancel()
        source = self.cget("bg")
        started = time.monotonic()
        def frame():
            if not self.winfo_exists():
                return
            t = min(1, (time.monotonic()-started)/.14) if self.motion() else 1
            self.configure(bg=blend(source, target, 1-(1-t)**3))
            self.job = self.after(16, frame) if t < 1 else None
        frame()


class ProgressTrack(tk.Canvas):
    def __init__(self, parent, motion=lambda: True):
        super().__init__(parent, height=8, bg=PANEL, highlightthickness=0)
        self.value = self.target = 0
        self.motion = motion
        self.job = None
        self.bind("<Configure>", lambda _: self.draw())
        self.bind("<Destroy>", self.cancel)

    def cancel(self, _=None):
        if self.job:
            self.after_cancel(self.job)
            self.job = None

    def draw(self):
        self.delete("all")
        width = self.winfo_width()
        self.create_line(4, 4, max(4, width-4), 4, width=8, fill=EDGE, capstyle="round")
        if self.value > .001:
            self.create_line(4, 4, max(4, (width-8)*self.value+4), 4, width=8, fill=ACCENT, capstyle="round")

    def set(self, value):
        self.target = max(0, min(1, value))
        if self.job:
            return
        def frame():
            delta = self.target-self.value
            self.value = self.target if abs(delta) < .002 or not self.motion() else self.value+delta*.2
            self.draw()
            self.job = self.after(16, frame) if self.value != self.target else None
        frame()
