from __future__ import annotations

import copy
import ctypes
import os
import queue
import subprocess
import sys
import tempfile
import threading
import time
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import messagebox, ttk

from core import (HostsFile, decision, domain,
                  load_config, next_transition, save_config, validate, hard_block_domains, is_youtube, browser_policy)
from bridge import StatusBridge
from branding import application_icon, VERSION
from theme import BG, PANEL, EDGE, FG, MUTED, ACCENT, CYAN, NAVY, SOFT, RED, MotionButton, ProgressTrack, SelectionRail, SmoothScroll

LIME = ACCENT
BLUE = ACCENT
DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def app_command(*args):
    if getattr(sys, "frozen", False):
        return [sys.executable, *args]
    return [sys.executable, str(Path(__file__).resolve()), *args]


def hidden_run(args):
    return subprocess.run(args, capture_output=True, text=True, timeout=15,
                          creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


def flush_dns():
    try:
        result = hidden_run([str(Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "ipconfig.exe"), "/flushdns"])
        return None if result.returncode == 0 else "Windows could not flush DNS. Restart your browsers."
    except (OSError, subprocess.TimeoutExpired):
        return "DNS cache refresh did not complete. Restart your browsers."


class App:
    def __init__(self, root, config_path, hosts, demo=False, signals=None):
        self.signals = signals
        self.root, self.config_path, self.hosts, self.demo = root, config_path, hosts, demo
        self.config = load_config(config_path)
        self.actions = queue.Queue()
        self.tray = None
        self.tray_ready = False
        self.last_signature = None
        self.last_check = 0
        self.error = None
        self.cache_note = None
        self.busy = False
        self.closed = False
        self.exit_requested = False
        self.exit_running = False
        self.motion_job = None
        self.duration = tk.StringVar(value="25")
        self.reduced_motion = tk.BooleanVar(value=self.config.get("reduced_motion", False))
        self.bridge = None
        self.bridge_error = None
        if not demo:
            try:
                self.bridge = StatusBridge(lambda: browser_policy(self.config, datetime.now()))
            except OSError:
                self.bridge_error = "Browser companion connection unavailable. Only Windows hosts rules can be applied."
        self.page = "Overview"
        root.title("Blacklist" + (" — Preview" if demo else ""))
        root.geometry("1120x850")
        root.minsize(1000, 720)
        root.configure(bg=BG)
        root.protocol("WM_DELETE_WINDOW", self.close)
        from PIL import ImageTk
        self.window_icon = ImageTk.PhotoImage(application_icon(128))
        root.iconphoto(True, self.window_icon)
        self.style()
        self.layout()
        self.show_page("Overview")
        self.start_tray()
        self.tick()

    def style(self):
        self.root.option_add("*Font", ("Segoe UI", 10))
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview", background=PANEL, fieldbackground=PANEL, foreground=FG,
                        rowheight=40, borderwidth=0, font=("Segoe UI", 10))
        style.configure("Treeview.Heading", background=EDGE, foreground=MUTED,
                        font=("Segoe UI", 10, "bold"), relief="flat")
        style.map("Treeview", background=[("selected", SOFT)], foreground=[("selected", ACCENT)])
        style.configure("Vertical.TScrollbar", background=EDGE, troughcolor=BG, borderwidth=0, arrowsize=12)

    def label(self, parent, text, size=10, color=FG, bold=False, **kw):
        return tk.Label(parent, text=text, bg=parent["bg"], fg=color,
                        font=("Segoe UI", size, "bold" if bold else "normal"), anchor="w", **kw)

    def button(self, parent, text, action, primary=False, **kw):
        return MotionButton(parent, text=text, command=action, bg=ACCENT if primary else SOFT,
                         fg=NAVY if primary else FG, activebackground=CYAN,
                         activeforeground=NAVY, relief="flat", borderwidth=0,
                         motion=lambda: not self.reduced_motion.get(), takefocus=True,
                         highlightthickness=2, highlightbackground=parent["bg"], highlightcolor=ACCENT,
                         padx=17, pady=11, cursor="hand2", font=("Segoe UI", 10, "bold"), **kw)

    def card(self, parent):
        return tk.Frame(parent, bg=PANEL, padx=24, pady=21,
                        highlightthickness=1, highlightbackground=EDGE)

    def entry(self, parent, variable=None):
        return tk.Entry(parent, textvariable=variable, bg=BG, fg=FG, insertbackground=LIME,
                        relief="flat", highlightthickness=1, highlightbackground=EDGE,
                        highlightcolor=LIME, font=("Segoe UI", 12))

    def layout(self):
        sidebar = tk.Frame(self.root, bg=NAVY, width=218)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)
        self.label(sidebar, "BLACKLIST", 18, ACCENT, True).pack(anchor="w", padx=22, pady=(32, 8))
        self.label(sidebar, "Protect your attention.", 9, MUTED, wraplength=174, justify="left").pack(anchor="w", padx=22, pady=(0, 28))
        self.nav = {}
        self.nav_area = tk.Frame(sidebar, bg=NAVY)
        self.nav_area.pack(fill="x", padx=14)
        self.selection = SelectionRail(self.nav_area, motion=lambda: not self.reduced_motion.get())
        self.selection.place(x=0, y=0, width=6, relheight=1)
        for name in ("Overview", "Websites", "Schedules", "How it works"):
            b = self.button(self.nav_area, name, lambda n=name: self.show_page(n), anchor="w")
            b.pack(fill="x", padx=(12, 0), pady=4)
            self.nav[name] = b
        self.nav_area.bind("<Configure>", lambda _: self.move_selection(False))
        bottom = tk.Frame(sidebar, bg=NAVY)
        bottom.pack(side="bottom", fill="x", padx=22, pady=25)
        self.label(bottom, "LOCAL & PRIVATE", 9, ACCENT, True).pack(anchor="w")
        self.label(bottom, "No account. No browsing log.\nWindows 10 / 11 · " + VERSION, 9, MUTED, justify="left", wraplength=174).pack(anchor="w", pady=(8, 14))
        tk.Checkbutton(bottom, text="Reduce motion", variable=self.reduced_motion, command=self.save_motion,
                       bg=NAVY, fg=MUTED, selectcolor=NAVY, activebackground=NAVY,
                       activeforeground=FG, relief="flat").pack(anchor="w", pady=(0, 14))
        self.button(bottom, "Unblock & quit", self.quit).pack(fill="x")
        outer = tk.Frame(self.root, bg=BG)
        outer.pack(side="left", fill="both", expand=True, padx=32, pady=25)
        top = tk.Frame(outer, bg=BG)
        top.pack(fill="x", pady=(0, 18))
        self.label(top, "YOUR TIME, ON YOUR TERMS", 9, MUTED, True).pack(side="left")
        self.badge = self.label(top, "●  Ready", 10, LIME, True)
        self.badge.pack(side="right")
        viewport = tk.Frame(outer, bg=BG)
        viewport.pack(fill="both", expand=True)
        self.canvas = tk.Canvas(viewport, bg=BG, highlightthickness=0)
        self.scroller = SmoothScroll(self.canvas, motion=lambda: not self.reduced_motion.get())
        scroll = ttk.Scrollbar(viewport, command=self.scroller.command)
        scroll.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.canvas.configure(yscrollcommand=scroll.set)
        self.body = tk.Frame(self.canvas, bg=BG)
        content_id = self.canvas.create_window((0, 0), window=self.body, anchor="nw")
        self.content_id = content_id
        self.body.bind("<Configure>", lambda _: self.canvas.configure(scrollregion=(0, 0, self.canvas.winfo_width(), self.body.winfo_reqheight())))
        def resize(event):
            self.canvas.itemconfigure(content_id, width=event.width)
            if hasattr(self, "heading") and self.heading.winfo_exists():
                self.heading.configure(wraplength=max(300, event.width-12))
        self.canvas.bind("<Configure>", resize)
        def wheel(event):
            if event.widget.winfo_toplevel() == self.root and not isinstance(event.widget, (tk.Listbox, ttk.Treeview)):
                self.scroller.by(-event.delta / 120 * 90)
                return "break"
        self.root.bind_all("<MouseWheel>", wheel, add="+")
        self.footer = self.label(outer, "", 9, MUTED, wraplength=740, justify="left")
        self.footer.pack(fill="x", pady=(14, 0))

    def move_selection(self, animate=True):
        button = self.nav.get(self.page)
        if button and button.winfo_height() > 1:
            self.selection.select(button.winfo_y(), button.winfo_height(), animate)

    def save_motion(self):
        if self.reduced_motion.get():
            self.scroller.stop()
            self.move_selection(False)
            if self.motion_job:
                self.root.after_cancel(self.motion_job)
                self.motion_job = None
                self.canvas.coords(self.content_id, 0, 0)
        self.config["reduced_motion"] = self.reduced_motion.get()
        try:
            save_config(self.config_path, self.config)
        except OSError as exc:
            messagebox.showerror("Could not save preference", str(exc), parent=self.root)

    def show_page(self, page, animate=True):
        previous = self.page
        self.scroller.reset()
        if self.motion_job:
            self.root.after_cancel(self.motion_job)
            self.motion_job = None
        self.page = page
        for child in self.body.winfo_children():
            child.destroy()
        for name, button in self.nav.items():
            button.cancel()
            button.configure(fg=ACCENT if name == page else MUTED)
            button.rest_color = SOFT if name == page else NAVY
            button.animate(button.rest_color)
        self.move_selection(animate)
        getattr(self, {"Overview": "overview", "Websites": "websites", "Schedules": "schedules", "How it works": "help_page"}[page])()
        self.canvas.yview_moveto(0)
        self.refresh_status()
        self.canvas.coords(self.content_id, 0, 0)
        if animate and not self.reduced_motion.get():
            started = time.monotonic()
            pages = list(self.nav)
            direction = 1 if pages.index(page) >= pages.index(previous) else -1
            def enter():
                t = min(1, (time.monotonic()-started)/.28)
                self.canvas.coords(self.content_id, direction*22*(1-t)**3, 10*(1-t)**3)
                self.motion_job = self.root.after(16, enter) if t < 1 else None
            enter()

    def title(self, title, subtitle):
        self.heading = self.label(self.body, title, 29, bold=True, wraplength=max(600, self.canvas.winfo_width()-12), justify="left")
        self.heading.pack(anchor="w")
        self.label(self.body, subtitle, 11, MUTED, wraplength=740, justify="left").pack(anchor="w", pady=(8, 23))

    def overview(self):
        self.title("A clear mind. A focused day.", "Less distraction. More time for the things you choose.")
        hero = self.card(self.body)
        hero.pack(fill="x", pady=(0, 16))
        self.status_label = self.label(hero, "", 24, LIME, True)
        self.status_label.pack(anchor="w")
        self.reason_label = self.label(hero, "", 11, MUTED, wraplength=680, justify="left")
        self.reason_label.pack(anchor="w", pady=(8, 19))
        controls = tk.Frame(hero, bg=PANEL)
        controls.pack(fill="x")
        self.button(controls, "Block now", lambda: self.set_mode("blocked"), True).pack(side="left", padx=(0, 8))
        self.button(controls, "Unblock now", lambda: self.set_mode("open")).pack(side="left", padx=(0, 8))
        self.button(controls, "Use schedules", lambda: self.set_mode("auto")).pack(side="left")
        self.label(hero, "Manual controls cancel timers and stay in effect until you change mode.", 9, MUTED).pack(anchor="w", pady=(14, 0))
        timer = self.card(self.body)
        timer.pack(fill="x", pady=(0, 16))
        self.label(timer, "Find your focus rhythm", 18, bold=True).pack(anchor="w")
        self.timer_label = self.label(timer, "", 11, BLUE)
        self.timer_label.pack(anchor="w", pady=(6, 13))
        self.progress = ProgressTrack(timer, motion=lambda: not self.reduced_motion.get())
        self.progress.pack(fill="x", pady=(0, 18))
        line = tk.Frame(timer, bg=PANEL)
        line.pack(fill="x")
        e = self.entry(line, self.duration)
        e.configure(width=5)
        e.pack(side="left", ipady=9)
        self.label(line, " minutes", 10, MUTED).pack(side="left", padx=(3, 17))
        self.button(line, "Start focus", lambda: self.start_timer(True), True).pack(side="left", padx=(0, 8))
        self.button(line, "Take a break", lambda: self.start_timer(False)).pack(side="left")
        self.button(line, "Cancel", self.cancel_timer).pack(side="right")
        self.label(timer, "When the countdown ends, your selected mode resumes.", 9, MUTED).pack(anchor="w", pady=(13, 0))
        row = tk.Frame(self.body, bg=BG)
        row.pack(fill="x")
        for heading, value, detail, page in [
            ("YOUR WEBSITE LIST", str(len(self.config["domains"])), "Domains on your list", "Websites"),
            ("YOUR WEEKLY RHYTHM", str(len(self.config["schedules"])), "Recurring schedules", "Schedules"),
        ]:
            c = self.card(row)
            c.pack(side="left", fill="both", expand=True, padx=(0, 12))
            self.label(c, heading, 9, MUTED, True).pack(anchor="w")
            self.label(c, value, 26, bold=True).pack(anchor="w", pady=3)
            self.button(c, detail + "  →", lambda p=page: self.show_page(p)).pack(anchor="w")

    def websites(self):
        self.title("Choose your distractions.", "Your websites, your choice. Add a domain or full link; www aliases are included automatically.")
        c = self.card(self.body)
        c.pack(fill="both", expand=True)
        if not self.config["domains"]:
            self.label(c, "No websites added yet. You choose what to block.", 11, MUTED).pack(anchor="w", pady=(0, 16))
        self.site_input = tk.StringVar()
        line = tk.Frame(c, bg=PANEL)
        line.pack(fill="x")
        e = self.entry(line, self.site_input)
        e.pack(side="left", fill="x", expand=True, ipady=9, padx=(0, 10))
        e.bind("<Return>", lambda _: self.add_domain())
        self.button(line, "Add website", self.add_domain, True).pack(side="right")
        self.label(c, "Add example.com, www.example.com, or https://www.example.com/ - all block the same website.", 9, MUTED, wraplength=650, justify="left").pack(anchor="w", pady=(8, 17))
        area = tk.Frame(c, bg=PANEL)
        area.pack(fill="both", expand=True)
        self.site_list = tk.Listbox(area, bg=BG, fg=FG, selectbackground=EDGE,
                                   selectforeground=LIME, relief="flat", highlightthickness=0,
                                   selectmode="extended", font=("Consolas", 12), activestyle="none", height=10)
        scroll = ttk.Scrollbar(area, command=self.site_list.yview)
        self.site_list.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.site_list.pack(fill="both", expand=True)
        for name in self.config["domains"]:
            self.site_list.insert("end", name)
        controls = tk.Frame(c, bg=PANEL)
        controls.pack(fill="x", pady=(14, 0))
        self.button(controls, "Remove selected", self.remove_domains).pack(side="left", padx=(0, 8))
        self.button(controls, "Remove all", self.remove_all_domains).pack(side="left")
        self.label(c, "YouTube uses a study prompt, not a hard block: install the included Chrome/Edge extension.\nThe browser companion blocks subdomains too. Hosts-only blocking needs other subdomains added explicitly.", 9, MUTED, wraplength=670, justify="left").pack(anchor="w", pady=(12, 0))

    def schedules(self):
        self.title("Give your week a rhythm.", "Schedules use this PC’s local time. Overlapping schedules keep blocking until all have ended.")
        c = self.card(self.body)
        c.pack(fill="both", expand=True)
        self.button(c, "+ New schedule", lambda: self.edit_schedule(), True).pack(anchor="w", pady=(0, 17))
        self.schedule_list = ttk.Treeview(c, columns=("name", "days", "hours", "state"), show="headings", selectmode="browse", height=8)
        for key, label, width in [("name", "Name", 170), ("days", "Days", 190), ("hours", "Hours", 145), ("state", "State", 65)]:
            self.schedule_list.heading(key, text=label)
            self.schedule_list.column(key, width=width, minwidth=50)
        self.schedule_list.pack(fill="both", expand=True)
        self.schedule_list.bind("<Double-1>", lambda _: self.edit_selected())
        for i, rule in enumerate(self.config["schedules"]):
            self.schedule_list.insert("", "end", iid=str(i), values=(rule["name"], " ".join(DAYS[d] for d in rule["days"]), rule["start"] + "–" + rule["end"], "On" if rule.get("enabled", True) else "Off"))
        controls = tk.Frame(c, bg=PANEL)
        controls.pack(fill="x", pady=(17, 0))
        self.button(controls, "Edit", self.edit_selected).pack(side="left", padx=(0, 8))
        self.button(controls, "Enable / disable", self.toggle_schedule).pack(side="left", padx=(0, 8))
        self.button(controls, "Delete", self.delete_schedule).pack(side="left")
        self.label(c, "For 22:00–07:00, select the day the overnight block starts.\nChoose “Use schedules” on Overview to activate your weekly rhythm.", 10, MUTED, justify="left").pack(anchor="w", pady=(17, 0))

    def help_page(self):
        self.title("A quieter browser, on your terms.", "A personal focus tool for Windows. You stay in control.")
        c = self.card(self.body)
        c.pack(fill="both", expand=True)
        actions = tk.Frame(c, bg=PANEL)
        actions.pack(fill="x", pady=(0, 18))
        self.button(actions, "Browser companion folder", lambda: self.open_support("youtube-extension"), True).pack(side="left", padx=(0, 8))
        self.button(actions, "Setup instructions", lambda: self.open_support("INSTALL-NOTES.txt")).pack(side="left")
        for title, detail in [
            ("Browser companion · Chrome / Edge", "Load the youtube-extension folder using Extensions → Developer mode → Load unpacked. It blocks listed websites and replaces already-open tabs, usually within 30 seconds. Reload it after app upgrades. YouTube asks: Are you sure it’s about studies? Install separately in every browser you use."),
            ("01   Pick sites, then pick your time", "Your list starts empty. Add any website address; the URL path is ignored. Use a countdown, a weekly schedule, or the manual block and unblock buttons."),
            ("02   Keep Blacklist running", "Closing the window minimizes it to the system tray. Schedules and timer expiry need the app running. After sleep, the app catches up with the current time. Reopen it after signing in; this version does not start automatically."),
            ("03   Know what gets blocked", "Windows hosts rules affect browsers using normal Windows name resolution. Hosts rules do not support wildcards. Restart browsers after changes if a page still loads. VPNs, proxies, custom DNS, cached sessions, and unlisted subdomains can bypass blocking."),
            ("04   Leave whenever you need", "Unblock now overrides schedules until you select Use schedules again. Unblock & quit removes this app’s hosts rules. If the app crashes, rules can remain: reopen it and unblock, or use the recovery launcher supplied with the app."),
        ]:
            self.label(c, title, 13, LIME, True).pack(anchor="w", pady=(4, 7))
            self.label(c, detail, 10, MUTED, wraplength=660, justify="left").pack(anchor="w", pady=(0, 17))
        self.label(c, "Administrator access is used only for local website rules. No browsing history is collected.", 10, BLUE, wraplength=660, justify="left").pack(anchor="w")

    def open_support(self, name):
        base = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
        try:
            os.startfile(base / name)
        except OSError as exc:
            messagebox.showerror("Could not open help", str(exc), parent=self.root)

    def change(self, update):
        if self.exit_requested:
            return False
        candidate = copy.deepcopy(self.config)
        try:
            update(candidate)
            validate(candidate)
            save_config(self.config_path, candidate)
        except (OSError, ValueError) as exc:
            messagebox.showerror("Could not save", str(exc), parent=self.root)
            return False
        self.config = candidate
        self.last_signature = None
        if self.page == "Overview":
            self.refresh_status()
        else:
            position = self.canvas.yview()[0]
            self.show_page(self.page, animate=False)
            self.root.update_idletasks()
            self.canvas.yview_moveto(position)
        return True

    def set_mode(self, mode):
        if mode == "blocked" and not self.config["domains"]:
            messagebox.showinfo("Add a website first", "Your website list is empty.", parent=self.root)
            return
        self.change(lambda c: c.update(mode=mode, timer=None))

    def start_timer(self, block):
        try:
            duration = int(self.duration.get())
            if not 1 <= duration <= 1440:
                raise ValueError()
        except ValueError:
            messagebox.showerror("Choose a duration", "Enter a whole number from 1 to 1440 minutes.", parent=self.root)
            return
        if block and not self.config["domains"]:
            messagebox.showinfo("Add a website first", "Your website list is empty.", parent=self.root)
            return
        self.change(lambda c: c.update(timer={"block": block, "started": time.time(), "until": time.time() + duration * 60}))

    def cancel_timer(self):
        self.change(lambda c: c.update(timer=None))

    def add_domain(self):
        try:
            name = domain(self.site_input.get())
        except ValueError as exc:
            messagebox.showerror("Check the website", str(exc), parent=self.root)
            return
        self.change(lambda c: c.update(domains=sorted(set(c["domains"] + [name]))))

    def remove_domains(self):
        selected = {self.site_list.get(i) for i in self.site_list.curselection()}
        if selected:
            # Remove paired www aliases together so removal actually unblocks them.
            paired = {n[4:] if n.startswith("www.") else n for n in selected}
            self.change(lambda c: c.update(domains=[n for n in c["domains"] if (n[4:] if n.startswith("www.") else n) not in paired]))

    def remove_all_domains(self):
        if self.config["domains"] and messagebox.askyesno("Remove all websites?", "Clear your website list? Blocking will stop for these websites.", parent=self.root):
            self.change(lambda c: c.update(domains=[]))

    def selected_schedule(self):
        selection = self.schedule_list.selection()
        return int(selection[0]) if selection else None

    def edit_selected(self):
        index = self.selected_schedule()
        if index is not None:
            self.edit_schedule(index)

    def toggle_schedule(self):
        index = self.selected_schedule()
        if index is not None:
            self.change(lambda c: c["schedules"][index].update(enabled=not c["schedules"][index].get("enabled", True)))

    def delete_schedule(self):
        index = self.selected_schedule()
        if index is not None and messagebox.askyesno("Delete schedule?", "Remove this recurring block?", parent=self.root):
            self.change(lambda c: c["schedules"].pop(index))

    def edit_schedule(self, index=None):
        rule = self.config["schedules"][index] if index is not None else {"name": "Deep work", "start": "09:00", "end": "17:00", "days": [0, 1, 2, 3, 4], "enabled": True}
        dialog = tk.Toplevel(self.root)
        dialog.title("Edit schedule" if index is not None else "New schedule")
        dialog.configure(bg=PANEL)
        dialog.geometry(f"490x370+{max(0, self.root.winfo_rootx() + (self.root.winfo_width() - 490) // 2)}+{max(0, self.root.winfo_rooty() + (self.root.winfo_height() - 370) // 2)}")
        dialog.resizable(False, False)
        dialog.transient(self.root)
        dialog.grab_set()
        form = tk.Frame(dialog, bg=PANEL, padx=25, pady=23)
        form.pack(fill="both", expand=True)
        fields = {}
        for label, key in [("Name", "name"), ("Starts · 24-hour time", "start"), ("Ends · 24-hour time", "end")]:
            row = tk.Frame(form, bg=PANEL)
            row.pack(fill="x", pady=6)
            self.label(row, label, 10, MUTED, width=22).pack(side="left")
            fields[key] = tk.StringVar(value=rule[key])
            self.entry(row, fields[key]).pack(side="right", fill="x", expand=True, ipady=7)
        days = tk.Frame(form, bg=PANEL)
        days.pack(fill="x", pady=16)
        flags = []
        for i, name in enumerate(DAYS):
            flag = tk.BooleanVar(value=i in rule["days"])
            flags.append(flag)
            tk.Checkbutton(days, text=name, variable=flag, bg=PANEL, fg=FG,
                           selectcolor=BG, activebackground=PANEL, activeforeground=LIME).pack(side="left")
        self.label(form, "Overnight blocks continue into the following day.", 9, MUTED).pack(anchor="w")
        def save():
            new = {key: value.get().strip() for key, value in fields.items()}
            new.update(days=[i for i, flag in enumerate(flags) if flag.get()], enabled=rule.get("enabled", True))
            def update(c):
                if index is None:
                    c["schedules"].append(new)
                else:
                    c["schedules"][index] = new
            if self.change(update):
                dialog.destroy()
        self.button(form, "Save schedule", save, True).pack(anchor="e", pady=(20, 0))

    def refresh_status(self):
        now = datetime.now()
        blocked, reason = decision(self.config, now)
        blocked = blocked and bool(self.config["domains"])
        if self.exit_requested:
            title, color = "Restoring access…", BLUE
        elif self.error:
            title, color = "Needs attention", RED
        elif self.busy:
            title, color = "Applying changes…", BLUE
        else:
            title, color = ("Windows rules active", LIME) if blocked else ("You’re free to browse", BLUE)
        self.badge.configure(text=("PREVIEW  ·  " if self.demo else "") + "●  " + title, fg=color)
        if self.page == "Overview":
            self.status_label.configure(text=title, fg=color)
            mode = {"auto": "Schedules", "blocked": "Manual block", "open": "Manual unblock"}[self.config["mode"]]
            self.reason_label.configure(text=f"{reason}  ·  Selected mode: {mode}" if not self.error else self.error)
            timer = self.config.get("timer")
            if timer and timer["until"] > now.timestamp():
                remaining = max(0, int(timer["until"] - now.timestamp()))
                h, r = divmod(remaining, 3600)
                m, s = divmod(r, 60)
                self.timer_label.configure(text=f"{'Focus' if timer['block'] else 'Break'} ends in {h:02}:{m:02}:{s:02}")
                total = max(1, timer["until"] - timer.get("started", timer["until"]-1500))
                self.progress.set(1-remaining/total)
            else:
                self.timer_label.configure(text="No countdown running. Start with 25 minutes.")
                self.progress.set(0)
        browser_connected = self.bridge and time.monotonic() - self.bridge.last_browser_seen < 65
        if self.demo:
            text = "Preview mode: no system settings are changed."
        elif browser_connected:
            text = "Browser companion connected. Open blocked tabs are replaced at its next check (usually within 30 seconds)."
        else:
            text = "Browser companion not connected. Install/reload it in each browser to stop already-open sites. Windows rules alone may need a full browser restart."
        self.footer.configure(text=self.error or self.bridge_error or self.cache_note or text, fg=RED if self.error else MUTED)
        if self.tray:
            self.tray.title = "Blacklist — " + title

    def apply_async(self, entries, signature):
        self.busy = True
        def worker():
            try:
                changed = self.hosts.apply(entries)
                warning = flush_dns() if changed and not self.demo else None
                self.actions.put(("applied", (signature, warning, None)))
            except (OSError, ValueError) as exc:
                self.actions.put(("applied", (None, None, f"Could not update website rules: {exc}")))
        threading.Thread(target=worker, daemon=True).start()

    def tick(self):
        if self.signals:
            for action in self.signals.pending():
                self.actions.put((action, None))
        while not self.actions.empty():
            action, data = self.actions.get_nowait()
            if action == "show":
                self.root.deiconify()
                self.root.lift()
            elif action == "unblock":
                self.set_mode("open")
            elif action == "quit":
                self.quit()
                if self.closed:
                    return
            elif action == "tray_ready":
                self.tray_ready = True
            elif action == "tray_failed":
                self.tray_ready = False
            elif action == "applied":
                self.last_signature, self.cache_note, self.error = data
                self.busy = False
                self.last_check = time.monotonic()
            elif action == "exit_done":
                self.closed = True
                self.root.destroy()
                return
            elif action == "exit_error":
                self.exit_requested = self.exit_running = False
                self.error = data
                messagebox.showerror("Could not remove blocking", data, parent=self.root)
        if self.exit_requested:
            if not self.busy and not self.exit_running:
                self.finish_exit()
            self.refresh_status()
            self.root.after(100, self.tick)
            return
        now = datetime.now()
        block = decision(self.config, now)[0]
        entries = hard_block_domains(self.config["domains"]) if block else []
        signature = tuple(entries)
        # Retry failures and detect externally changed hosts contents every 15 s.
        if not self.busy and ((self.error is None and signature != self.last_signature) or time.monotonic() - self.last_check >= 15):
            self.apply_async(entries, signature)
        self.refresh_status()
        self.root.after(500, self.tick)

    def start_tray(self):
        def tray_worker():
            try:
                import pystray
                image = application_icon()
                self.tray = pystray.Icon("FocusHarbor", image, "Blacklist", pystray.Menu(
                    pystray.MenuItem("Open Blacklist", lambda: self.actions.put(("show", None)), default=True),
                    pystray.MenuItem("Unblock now", lambda: self.actions.put(("unblock", None))),
                    pystray.MenuItem("Unblock & quit", lambda: self.actions.put(("quit", None)))))
                def ready(icon):
                    icon.visible = True
                    self.actions.put(("tray_ready", None))
                self.tray.run(setup=ready)
            except Exception:
                self.actions.put(("tray_failed", None))
        threading.Thread(target=tray_worker, daemon=True).start()

    def close(self):
        if self.tray_ready:
            self.root.withdraw()
        elif messagebox.askyesno("Exit Blacklist?", "The tray icon is unavailable. Unblock websites and quit?", parent=self.root):
            self.quit()

    def quit(self):
        self.exit_requested = True
        self.root.deiconify()
        self.refresh_status()

    def finish_exit(self):
        self.exit_running = True
        def worker():
            try:
                changed = self.hosts.apply([])
                if changed and not self.demo:
                    flush_dns()
                if self.tray:
                    self.tray.stop()
                if self.bridge:
                    self.bridge.close()
                self.actions.put(("exit_done", None))
            except (OSError, ValueError) as exc:
                self.actions.put(("exit_error", f"The app is still open so you can retry.\n\n{exc}"))
        threading.Thread(target=worker, daemon=True).start()


def main():
    if "--uninstall-cleanup" in sys.argv:
        from installer_cleanup import run
        raise SystemExit(run())
    demo = "--demo" in sys.argv
    recover = "--unblock" in sys.argv
    if os.name != "nt" and not demo:
        raise SystemExit("Blacklist requires Windows.")
    if not demo and not ctypes.windll.shell32.IsUserAnAdmin():
        command = app_command(*sys.argv[1:])
        result = ctypes.windll.shell32.ShellExecuteW(None, "runas", command[0], subprocess.list2cmdline(command[1:]), None, 1)
        if result <= 32:
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror("Administrator permission needed", "Blacklist needs administrator permission to update Windows website rules. Nothing was changed.")
            root.destroy()
        return
    mutex = None
    if os.name == "nt":
        from ctypes import wintypes
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
        kernel.CreateMutexW.restype = wintypes.HANDLE
        mutex = kernel.CreateMutexW(None, False, "Global\\FocusHarbor" + ("Preview" if demo else ""))
        if not mutex or ctypes.get_last_error() == 183:
            from app_signals import send_signal
            if mutex:
                kernel.CloseHandle.argtypes = [wintypes.HANDLE]
                kernel.CloseHandle(mutex)
            if not recover and send_signal("show", demo):
                return
            root = tk.Tk()
            root.withdraw()
            messagebox.showinfo("Blacklist is already running", "Use the list icon in the system tray to open it or unblock websites.")
            root.destroy()
            return
    temp = tempfile.TemporaryDirectory(prefix="focustracker-preview-") if demo else None
    data = Path(temp.name) if demo else Path(os.environ["LOCALAPPDATA"]) / "FocusHarbor"
    data.mkdir(parents=True, exist_ok=True)
    path = data / "hosts-preview" if demo else Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32/drivers/etc/hosts"
    if demo:
        path.write_bytes(b"# Preview hosts file\r\n127.0.0.1 localhost\r\n")
    hosts = HostsFile(path, data / "hosts-before-last-change.bak")
    config_path = data / "settings.json"
    root = tk.Tk()
    root.withdraw()
    signals = None
    try:
        if recover:
            hosts.apply([])
            if not demo:
                flush_dns()
            if config_path.exists():
                try:
                    config = load_config(config_path)
                    config.update(mode="open", timer=None)
                    save_config(config_path, config)
                except ValueError:
                    pass  # Preserve corrupt settings; hosts recovery still succeeds.
            messagebox.showinfo("Websites unblocked", "Blacklist’s website rules have been removed.")
            root.destroy()
        else:
            if os.name == "nt":
                from app_signals import AppSignals
                signals = AppSignals(demo)
            App(root, config_path, hosts, demo, signals)
            root.deiconify()
            root.mainloop()
    except Exception as exc:
        messagebox.showerror("Blacklist could not start", f"{exc}\n\nIf sites remain blocked, run Recover websites.cmd.")
        root.destroy()
    finally:
        if signals:
            signals.close()
        if mutex:
            kernel.CloseHandle.argtypes = [ctypes.c_void_p]
            kernel.CloseHandle(mutex)
        if temp:
            temp.cleanup()


if __name__ == "__main__":
    main()
