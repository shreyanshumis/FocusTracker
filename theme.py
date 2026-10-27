"""Small native UI components with bounded, cancellable animations."""
import time
import tkinter as tk

BG = "#191919"
PANEL = "#242424"
EDGE = "#3C3C3C"
FG = "#F3F0E7"
MUTED = "#B5B3AC"
ACCENT = "#F5CD47"
CYAN = "#FFE27B"
NAVY = "#141414"
SOFT = "#333126"
RED = "#FF8585"


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


class SelectionRail(tk.Canvas):
    """A single indicator that glides between native, keyboard-accessible buttons."""
    def __init__(self, parent, motion=lambda: True):
        super().__init__(parent, width=6, bg=NAVY, highlightthickness=0)
        self.motion = motion
        self.position = None
        self.job = None
        self.bind("<Destroy>", self.cancel)

    def cancel(self, _=None):
        if self.job:
            self.after_cancel(self.job)
            self.job = None

    def select(self, top, height, animate=True):
        self.cancel()
        target = (float(top + 12), float(top + height - 12))
        source = self.position or target
        started = time.monotonic()
        def frame():
            t = min(1, (time.monotonic()-started)/.28) if animate and self.motion() else 1
            eased = 1-(1-t)**3
            self.position = tuple(a+(b-a)*eased for a, b in zip(source, target))
            self.delete("all")
            self.create_line(3, self.position[0], 3, self.position[1], width=6, fill="#5B4C21", capstyle="round")
            self.create_line(3, self.position[0], 3, self.position[1], width=3, fill=CYAN, capstyle="round")
            self.job = self.after(16, frame) if t < 1 else None
        frame()


class SmoothScroll:
    """Pixel-based wheel scrolling with accumulated input and bounded easing."""
    def __init__(self, canvas, motion=lambda: True):
        self.canvas, self.motion = canvas, motion
        self.target = 0
        self.job = None
        canvas.bind("<Destroy>", self.stop, add="+")

    def stop(self, _=None):
        if self.job:
            self.canvas.after_cancel(self.job)
            self.job = None

    def extent(self):
        region = self.canvas.cget("scrollregion").split()
        total = float(region[3])-float(region[1]) if len(region) == 4 else 0
        return max(1, total), max(0, total-self.canvas.winfo_height())

    def reset(self):
        self.stop()
        self.target = 0
        self.canvas.yview_moveto(0)

    def by(self, pixels):
        total, limit = self.extent()
        current = self.canvas.yview()[0]*total
        self.target = max(0, min(limit, (self.target if self.job else current)+pixels))
        self.stop()
        started = time.monotonic()
        def frame():
            total, limit = self.extent()
            self.target = min(self.target, limit)
            t = min(1, (time.monotonic()-started)/.24) if self.motion() else 1
            position = current+(self.target-current)*(1-(1-t)**3)
            self.canvas.yview_moveto(max(0, min(limit, position))/total)
            self.job = self.canvas.after(16, frame) if t < 1 else None
        frame()

    def command(self, action, amount, unit=None):
        if action == "moveto":
            self.stop()
            self.canvas.yview_moveto(float(amount))
        else:
            self.by(float(amount)*(self.canvas.winfo_height()*.85 if unit == "pages" else 50))


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
