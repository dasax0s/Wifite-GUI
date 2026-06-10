#!/usr/bin/env python3
"""
Wifite GUI — graphical front-end for wifite.
Created by dasax0s.
For authorized penetration testing only.
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
import subprocess, threading, queue, os, sys, re, json, datetime

# ── colours ──────────────────────────────────────────────────────────────
BG     = "#1e1e2e"
PANEL  = "#2a2a3e"
ENTRY  = "#313244"
SEL    = "#45475a"
FG     = "#cdd6f4"
DIM    = "#6c7086"
ACCENT = "#89b4fa"
GREEN  = "#a6e3a1"
ORANGE = "#fab387"
RED    = "#f38ba8"

FONTB = ("Consolas", 10, "bold")
FONTS = ("Consolas", 9)

# ── system helpers ────────────────────────────────────────────────────────

def on_linux() -> bool:
    return sys.platform.startswith("linux")


def detect_interfaces() -> list[str]:
    try:
        out = subprocess.check_output(["iwconfig"], stderr=subprocess.DEVNULL, text=True)
        return re.findall(r"^(\w+)\s+IEEE", out, re.MULTILINE)
    except Exception:
        return []


def detect_wordlist() -> str:
    for p in [
        "/usr/share/wordlists/rockyou.txt",
        "/usr/share/wordlists/fasttrack.txt",
        "/opt/wordlists/rockyou.txt",
        os.path.expanduser("~/wordlists/rockyou.txt"),
    ]:
        if os.path.isfile(p):
            return p
    return ""


_ANSI = re.compile(r"\x1b\[[0-9;]*m")
strip_ansi = lambda s: _ANSI.sub("", s)


def require_root():
    if not on_linux() or os.geteuid() == 0:
        return
    print("[*] Root required — re-launching with sudo...")
    os.execvp("sudo", ["sudo", sys.executable] + sys.argv)


# ── scrollable network list ───────────────────────────────────────────────

class NetRow(tk.Frame):
    """One network row with checkbox + info labels + Attack button."""

    def __init__(self, parent, num, essid, ch, enc, pwr, wps, on_attack):
        super().__init__(parent, bg=PANEL, pady=2)

        self._sel = tk.BooleanVar()
        tk.Checkbutton(self, variable=self._sel, bg=PANEL,
                       activebackground=PANEL, selectcolor=ENTRY,
                       cursor="hand2").pack(side=tk.LEFT, padx=(4, 0))

        # signal strength colour
        try:
            db = int(pwr.replace("db", ""))
            pwr_fg = GREEN if db >= 40 else (ORANGE if db >= 20 else RED)
        except ValueError:
            pwr_fg = FG

        wps_fg = GREEN if wps.strip().lower() == "yes" else DIM

        for text, width, fg, anchor in [
            (num,   3,  DIM,    tk.CENTER),
            (essid, 18, FG,     tk.W),
            (ch,    3,  DIM,    tk.CENTER),
            (enc,   7,  ORANGE, tk.CENTER),
            (pwr,   5,  pwr_fg, tk.CENTER),
            (wps,   3,  wps_fg, tk.CENTER),
        ]:
            tk.Label(self, text=text, bg=PANEL, fg=fg, font=FONTS,
                     width=width, anchor=anchor).pack(side=tk.LEFT, padx=2)

        tk.Button(self, text="Attack", command=on_attack,
                  bg=ENTRY, fg=ORANGE, relief=tk.FLAT, font=FONTS,
                  cursor="hand2", padx=6).pack(side=tk.RIGHT, padx=6)

        # separator line
        tk.Frame(self, bg=ENTRY, height=1).pack(side=tk.BOTTOM, fill=tk.X)

    @property
    def selected(self) -> bool:
        return self._sel.get()

    def set_selected(self, val: bool):
        self._sel.set(val)


class NetList(tk.Frame):
    """Scrollable container for NetRow items."""

    def __init__(self, parent, **kw):
        super().__init__(parent, bg=PANEL, **kw)

        # header row
        hdr = tk.Frame(self, bg=ENTRY)
        hdr.pack(fill=tk.X)
        tk.Label(hdr, text=" ", bg=ENTRY, fg=DIM, font=FONTS, width=2).pack(side=tk.LEFT)
        for text, width in [("#",3), ("ESSID",18), ("CH",3),
                             ("ENC",7), ("PWR",5), ("WPS",3)]:
            tk.Label(hdr, text=text, bg=ENTRY, fg=ACCENT, font=FONTS,
                     width=width, anchor=tk.CENTER).pack(side=tk.LEFT, padx=2)
        tk.Label(hdr, text="", bg=ENTRY, width=8).pack(side=tk.RIGHT)

        # scrollable canvas
        self._canvas = tk.Canvas(self, bg=PANEL, highlightthickness=0)
        vsb = ttk.Scrollbar(self, orient=tk.VERTICAL, command=self._canvas.yview)
        self._canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        self._canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self._inner = tk.Frame(self._canvas, bg=PANEL)
        self._win = self._canvas.create_window((0, 0), window=self._inner, anchor=tk.NW)

        self._inner.bind("<Configure>", self._on_configure)
        self._canvas.bind("<Configure>", self._on_canvas_resize)
        self._canvas.bind_all("<MouseWheel>",
            lambda e: self._canvas.yview_scroll(-1 * (e.delta // 120), "units"))

        self._rows: list[NetRow] = []

    def _on_configure(self, _):
        self._canvas.configure(scrollregion=self._canvas.bbox("all"))

    def _on_canvas_resize(self, e):
        self._canvas.itemconfig(self._win, width=e.width)

    def add(self, num, essid, ch, enc, pwr, wps, on_attack):
        row = NetRow(self._inner, num, essid, ch, enc, pwr, wps, on_attack)
        row.pack(fill=tk.X)
        self._rows.append(row)

    def clear(self):
        for r in self._rows:
            r.destroy()
        self._rows.clear()

    def select_all(self):
        for r in self._rows:
            r.set_selected(True)

    def select_none(self):
        for r in self._rows:
            r.set_selected(False)

    @property
    def selected_rows(self) -> list[NetRow]:
        return [r for r in self._rows if r.selected]

    def __len__(self):
        return len(self._rows)


# ── main window ───────────────────────────────────────────────────────────

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Wifite GUI — by dasax0s")
        self.geometry("1080x700")
        self.minsize(820, 560)
        self.configure(bg=BG)

        self._proc: subprocess.Popen | None = None
        self._q: queue.Queue = queue.Queue()
        self._running = False
        self._results: list[dict] = []
        self._log = os.path.join(os.path.expanduser("~"), ".wifite_gui_results.json")
        self._load_results()

        self._apply_styles()
        self._build()
        self._populate_interfaces()
        self.after(80, self._poll)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ── styles ────────────────────────────────────────────────────────────

    def _apply_styles(self):
        s = ttk.Style(self)
        s.theme_use("default")
        s.configure("Treeview", background=PANEL, foreground=FG,
                    fieldbackground=PANEL, rowheight=22, font=FONTS)
        s.configure("Treeview.Heading", background=ENTRY, foreground=ACCENT,
                    font=FONTB, relief=tk.FLAT)
        s.map("Treeview", background=[("selected", SEL)])
        s.configure("TNotebook", background=BG, borderwidth=0)
        s.configure("TNotebook.Tab", background=PANEL, foreground=DIM,
                    font=FONTS, padding=(10, 4))
        s.map("TNotebook.Tab",
              background=[("selected", BG)],
              foreground=[("selected", ACCENT)])
        s.configure("TCombobox", fieldbackground=ENTRY, background=ENTRY,
                    foreground=FG, selectbackground=SEL)
        s.configure("TScrollbar", background=PANEL, troughcolor=ENTRY,
                    borderwidth=0, arrowsize=12)
        s.configure("TProgressbar", troughcolor=ENTRY, background=ACCENT)

    # ── layout ────────────────────────────────────────────────────────────

    def _build(self):
        self._build_toolbar()
        pane = tk.PanedWindow(self, orient=tk.HORIZONTAL, bg=BG,
                              sashwidth=5, sashrelief=tk.FLAT)
        pane.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)
        left = tk.Frame(pane, bg=BG)
        right = tk.Frame(pane, bg=BG)
        pane.add(left, width=400, minsize=260)
        pane.add(right, minsize=280)
        self._build_net_panel(left)
        self._build_options(left)
        self._build_output(right)
        self._build_statusbar()

    # ── toolbar ───────────────────────────────────────────────────────────

    def _build_toolbar(self):
        bar = tk.Frame(self, bg=PANEL, height=46)
        bar.pack(fill=tk.X)
        bar.pack_propagate(False)

        tk.Label(bar, text="⚡ Wifite GUI", bg=PANEL, fg=ACCENT,
                 font=FONTB).pack(side=tk.LEFT, padx=12)
        tk.Label(bar, text="by dasax0s", bg=PANEL, fg=DIM,
                 font=FONTS).pack(side=tk.LEFT, padx=(0, 10))

        tk.Label(bar, text="Interface:", bg=PANEL, fg=DIM,
                 font=FONTS).pack(side=tk.LEFT, padx=(6, 3))
        self._iface = tk.StringVar()
        self._iface_cb = ttk.Combobox(bar, textvariable=self._iface,
                                       width=10, state="readonly", font=FONTS)
        self._iface_cb.pack(side=tk.LEFT, padx=3)

        self._tbtn(bar, "↻", self._populate_interfaces, DIM)
        self._tbtn(bar, "Monitor Mode", self._toggle_monitor, ACCENT)
        tk.Frame(bar, bg=DIM, width=1).pack(side=tk.LEFT, fill=tk.Y, pady=6, padx=6)
        self._scan_btn   = self._tbtn(bar, "▶ Scan",   self._scan,   GREEN)
        self._attack_btn = self._tbtn(bar, "⚔ Attack All", self._attack_all, ORANGE)
        self._stop_btn   = self._tbtn(bar, "■ Stop",   self._stop,   RED)
        self._stop_btn.configure(state=tk.DISABLED)

    def _tbtn(self, parent, text, cmd, fg):
        b = tk.Button(parent, text=text, command=cmd, bg=PANEL, fg=fg,
                      relief=tk.FLAT, activebackground=SEL, activeforeground=fg,
                      font=FONTB, cursor="hand2", padx=8, pady=6)
        b.pack(side=tk.LEFT, padx=3)
        return b

    # ── network panel ─────────────────────────────────────────────────────

    def _build_net_panel(self, parent):
        frame = tk.LabelFrame(parent, text="  Networks ", bg=PANEL, fg=ACCENT,
                               font=FONTB, bd=0, padx=4, pady=4)
        frame.pack(fill=tk.BOTH, expand=True, pady=(0, 4))

        btns = tk.Frame(frame, bg=PANEL)
        btns.pack(fill=tk.X, pady=(0, 4))
        for txt, cmd in [("Select All", self._sel_all),
                         ("Deselect",   self._sel_none),
                         ("Clear",      self._clear_nets)]:
            tk.Button(btns, text=txt, command=cmd, bg=ENTRY, fg=FG,
                      relief=tk.FLAT, font=FONTS, cursor="hand2",
                      padx=6).pack(side=tk.LEFT, padx=2)

        self._netcount = tk.StringVar(value="Networks: 0")
        tk.Label(btns, textvariable=self._netcount, bg=PANEL, fg=DIM,
                 font=FONTS).pack(side=tk.RIGHT, padx=4)

        self._netlist = NetList(frame)
        self._netlist.pack(fill=tk.BOTH, expand=True)

    # ── attack options ────────────────────────────────────────────────────

    def _build_options(self, parent):
        frame = tk.LabelFrame(parent, text="  Options ", bg=PANEL, fg=ACCENT,
                               font=FONTB, bd=0, padx=8, pady=6)
        frame.pack(fill=tk.X)

        r1 = tk.Frame(frame, bg=PANEL); r1.pack(fill=tk.X)
        self._wpa   = self._chk(r1, "WPA",   True)
        self._wps   = self._chk(r1, "WPS",   True)
        self._pmkid = self._chk(r1, "PMKID", True)
        self._wep   = self._chk(r1, "WEP",   False)

        r2 = tk.Frame(frame, bg=PANEL); r2.pack(fill=tk.X, pady=(4, 0))
        self._kill_nm = self._chk(r2, "Kill NetworkManager", True)
        self._verbose = self._chk(r2, "Verbose", False)

        r3 = tk.Frame(frame, bg=PANEL); r3.pack(fill=tk.X, pady=(4, 0))
        self._timeout = self._lentry(r3, "Timeout:", "300", 5)
        self._minpwr  = self._lentry(r3, "Min PWR:", "-80", 4)

        r4 = tk.Frame(frame, bg=PANEL); r4.pack(fill=tk.X, pady=(4, 0))
        tk.Label(r4, text="Wordlist:", bg=PANEL, fg=DIM, font=FONTS).pack(side=tk.LEFT)
        self._wl = tk.StringVar(value=detect_wordlist())
        tk.Entry(r4, textvariable=self._wl, bg=ENTRY, fg=FG,
                 insertbackground=FG, relief=tk.FLAT, font=FONTS,
                 width=22).pack(side=tk.LEFT, padx=4)
        tk.Button(r4, text="…", command=self._browse_wl, bg=ENTRY,
                  fg=ACCENT, relief=tk.FLAT, font=FONTS,
                  cursor="hand2").pack(side=tk.LEFT)
        if not self._wl.get():
            tk.Label(frame, text="⚠ No wordlist found", bg=PANEL,
                     fg=ORANGE, font=FONTS).pack(anchor=tk.W, pady=(2, 0))

    def _chk(self, parent, text, default):
        var = tk.BooleanVar(value=default)
        tk.Checkbutton(parent, text=text, variable=var, bg=PANEL, fg=FG,
                       selectcolor=ENTRY, activebackground=PANEL,
                       activeforeground=FG, font=FONTS,
                       cursor="hand2").pack(side=tk.LEFT, padx=5)
        return var

    def _lentry(self, parent, label, default, width):
        tk.Label(parent, text=label, bg=PANEL, fg=DIM,
                 font=FONTS).pack(side=tk.LEFT, padx=(0, 2))
        var = tk.StringVar(value=default)
        tk.Entry(parent, textvariable=var, bg=ENTRY, fg=FG,
                 insertbackground=FG, relief=tk.FLAT, font=FONTS,
                 width=width).pack(side=tk.LEFT, padx=(0, 10))
        return var

    # ── output panel ──────────────────────────────────────────────────────

    def _build_output(self, parent):
        nb = ttk.Notebook(parent)
        nb.pack(fill=tk.BOTH, expand=True)

        # live output tab
        out_frame = tk.Frame(nb, bg=BG)
        nb.add(out_frame, text="  Live Output  ")

        ctrl = tk.Frame(out_frame, bg=BG)
        ctrl.pack(fill=tk.X, pady=(4, 2))
        self._autoscroll = tk.BooleanVar(value=True)
        tk.Checkbutton(ctrl, text="Auto-scroll", variable=self._autoscroll,
                       bg=BG, fg=DIM, selectcolor=ENTRY,
                       activebackground=BG, font=FONTS).pack(side=tk.LEFT, padx=4)
        tk.Button(ctrl, text="Clear", command=self._clear_out,
                  bg=ENTRY, fg=DIM, relief=tk.FLAT, font=FONTS,
                  cursor="hand2").pack(side=tk.RIGHT, padx=4)

        self._out = scrolledtext.ScrolledText(
            out_frame, bg="#11111b", fg=FG, insertbackground=FG,
            font=FONTS, relief=tk.FLAT, state=tk.DISABLED, wrap=tk.WORD)
        self._out.pack(fill=tk.BOTH, expand=True, padx=4, pady=(0, 4))
        self._out.tag_configure("ok",   foreground=GREEN)
        self._out.tag_configure("err",  foreground=RED)
        self._out.tag_configure("warn", foreground=ORANGE)
        self._out.tag_configure("hi",   foreground=ACCENT)
        self._out.tag_configure("dim",  foreground=DIM)

        # results tab
        res_frame = tk.Frame(nb, bg=BG)
        nb.add(res_frame, text="  Results  ")

        cols = ("time", "essid", "bssid", "enc", "password")
        self._rtree = ttk.Treeview(res_frame, columns=cols, show="headings")
        for col, lbl, w in [("time","Time",130), ("essid","ESSID",150),
                             ("bssid","BSSID",140), ("enc","ENC",55),
                             ("password","Password",200)]:
            self._rtree.heading(col, text=lbl)
            self._rtree.column(col, width=w)
        vsb = ttk.Scrollbar(res_frame, orient=tk.VERTICAL, command=self._rtree.yview)
        self._rtree.configure(yscrollcommand=vsb.set)
        self._rtree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(4,0), pady=4)
        vsb.pack(side=tk.RIGHT, fill=tk.Y, pady=4)

        br = tk.Frame(res_frame, bg=BG)
        br.pack(side=tk.BOTTOM, fill=tk.X, padx=4, pady=4)
        tk.Button(br, text="Export CSV", command=self._export,
                  bg=ENTRY, fg=ACCENT, relief=tk.FLAT, font=FONTS,
                  cursor="hand2").pack(side=tk.LEFT, padx=2)
        tk.Button(br, text="Clear", command=self._clear_results,
                  bg=ENTRY, fg=DIM, relief=tk.FLAT, font=FONTS,
                  cursor="hand2").pack(side=tk.LEFT, padx=2)

        self._refresh_results()

    # ── statusbar ─────────────────────────────────────────────────────────

    def _build_statusbar(self):
        bar = tk.Frame(self, bg=PANEL, height=26)
        bar.pack(fill=tk.X, side=tk.BOTTOM)
        bar.pack_propagate(False)
        self._status = tk.StringVar(value="Ready")
        tk.Label(bar, textvariable=self._status, bg=PANEL, fg=DIM,
                 font=FONTS, anchor=tk.W).pack(side=tk.LEFT, padx=10)
        self._progress = ttk.Progressbar(bar, mode="indeterminate", length=140)
        self._progress.pack(side=tk.RIGHT, padx=8, pady=4)

    # ── interface management ──────────────────────────────────────────────

    def _populate_interfaces(self):
        ifaces = detect_interfaces()
        if not ifaces:
            self._log_out("[!] No wireless interfaces found\n", "warn")
            return
        self._iface_cb["values"] = ifaces
        self._iface.set(ifaces[0])

    def _toggle_monitor(self):
        iface = self._iface.get()
        if not iface:
            return
        if not on_linux():
            self._log_out("[!] Monitor mode requires Linux\n", "warn")
            return
        try:
            subprocess.run(["airmon-ng", "start", iface], check=True)
            self._iface.set(iface + "mon")
            self._populate_interfaces()
            self._log_out(f"[+] Monitor mode: {iface}mon\n", "ok")
        except Exception as e:
            self._log_out(f"[-] airmon-ng failed: {e}\n", "err")

    # ── command building ──────────────────────────────────────────────────

    def _base_cmd(self) -> list[str]:
        iface = self._iface.get() or "wlan0"
        cmd = ["wifite", "-i", iface]
        if self._wpa.get():     cmd.append("--wpa")
        if self._wps.get():     cmd.append("--wps")
        if self._pmkid.get():   cmd.append("--pmkid")
        if self._wep.get():     cmd.append("--wep")
        if self._kill_nm.get(): cmd.append("--kill")
        if self._verbose.get(): cmd.append("--verbose")
        t = self._timeout.get().strip()
        if t.isdigit(): cmd += ["--timeout", t]
        try:
            int(self._minpwr.get())
            cmd += ["--min-power", self._minpwr.get().strip()]
        except ValueError:
            pass
        wl = self._wl.get().strip()
        if wl and os.path.isfile(wl):
            cmd += ["-dict", wl]
        return cmd

    # ── scan / attack ─────────────────────────────────────────────────────

    def _scan(self):
        if self._running:
            return
        if not self._iface.get():
            messagebox.showwarning("No Interface", "Select a wireless interface first.")
            return
        self._run(["wifite", "-i", self._iface.get(),
                   "--wpa", "--wps", "--pmkid", "--kill"])

    def _attack_all(self):
        """Attack all checked networks, or all if none checked."""
        if self._running:
            return
        if not len(self._netlist):
            messagebox.showwarning("No Networks", "Scan for networks first.")
            return
        if not messagebox.askyesno("Confirm",
                "Only attack networks you own or have explicit written permission to test.\n\nContinue?"):
            return
        self._run(self._base_cmd())

    def _attack_single(self, essid: str):
        """Attack one specific network by ESSID."""
        if self._running:
            messagebox.showwarning("Busy", "Stop the current process first.")
            return
        if not messagebox.askyesno("Confirm",
                f"Attack network: {essid}\n\n"
                "Only use on networks you own or have explicit written permission to test.\n\nContinue?"):
            return
        cmd = self._base_cmd() + ["--essid", essid]
        self._run(cmd)

    def _run(self, cmd: list[str]):
        if not on_linux():
            self._log_out("[!] wifite requires Linux.\n", "warn")
            return
        self._running = True
        self._scan_btn.configure(state=tk.DISABLED)
        self._attack_btn.configure(state=tk.DISABLED)
        self._stop_btn.configure(state=tk.NORMAL)
        self._progress.start(12)
        self._status.set("Running…")
        self._log_out("$ " + " ".join(cmd) + "\n\n", "dim")

        def worker():
            try:
                self._proc = subprocess.Popen(
                    cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    text=True, bufsize=1)
                for line in self._proc.stdout:
                    self._q.put(line)
                self._proc.wait()
            except FileNotFoundError:
                self._q.put("[-] wifite not found. Run install.sh first.\n")
            except Exception as e:
                self._q.put(f"[-] {e}\n")
            finally:
                self._q.put(None)

        threading.Thread(target=worker, daemon=True).start()

    def _stop(self):
        if self._proc:
            try: self._proc.terminate()
            except Exception: pass
        self._finish()
        self._log_out("[!] Stopped.\n", "warn")

    def _finish(self):
        self._running = False
        self._scan_btn.configure(state=tk.NORMAL)
        self._attack_btn.configure(state=tk.NORMAL)
        self._stop_btn.configure(state=tk.DISABLED)
        self._progress.stop()
        self._status.set("Ready")

    # ── output polling ────────────────────────────────────────────────────

    def _poll(self):
        try:
            while True:
                line = self._q.get_nowait()
                if line is None:
                    self._finish()
                else:
                    self._process_line(line)
        except Exception:
            pass
        self.after(80, self._poll)

    def _process_line(self, line: str):
        clean = strip_ansi(line)
        lo = clean.lower()
        if any(k in lo for k in ("cracked", "password", "found", "pin")):
            tag = "ok"
            self._parse_result(clean)
        elif any(k in lo for k in ("error", "failed")):
            tag = "err"
        elif any(k in lo for k in ("warning", "kill")):
            tag = "warn"
        elif clean.lstrip().startswith("[+]"):
            tag = "hi"
        elif re.match(r"^\s*\d+\s+\S", clean):
            tag = "dim"
            self._parse_net(clean)
        else:
            tag = None
        self._log_out(clean, tag)

    # wifite output: "  10    Ucom_6FDF    9  WPA2-P   26db   no"
    _NET_RE = re.compile(
        r"^\s*(\d+)\s{2,}(.+?)\s{2,}(\d+)\s{2,}(WPA\S*|WEP)\s+(\d+)db\s+(yes|no)",
        re.IGNORECASE
    )

    def _parse_net(self, line: str):
        m = self._NET_RE.match(line)
        if m:
            num, essid, ch, enc, pwr, wps = m.groups()
            essid = essid.strip()
            # avoid duplicates
            existing = {r.winfo_children()[1].cget("text")  # num label
                        for r in self._netlist._rows}
            if num not in existing:
                self._netlist.add(
                    num, essid, ch, enc, pwr + "db", wps,
                    on_attack=lambda e=essid: self._attack_single(e)
                )
                self._netcount.set(f"Networks: {len(self._netlist)}")

    def _parse_result(self, line: str):
        m = re.search(r"(\S+)\s+\(?([\dA-Fa-f:]{17})\)?.+?:\s+(.+)", line)
        if m:
            self._add_result(m.group(1), m.group(2), "WPA2", m.group(3).strip())

    def _log_out(self, text: str, tag=None):
        self._out.configure(state=tk.NORMAL)
        self._out.insert(tk.END, text, tag or "")
        if self._autoscroll.get():
            self._out.see(tk.END)
        self._out.configure(state=tk.DISABLED)

    # ── network list helpers ──────────────────────────────────────────────

    def _sel_all(self):   self._netlist.select_all()
    def _sel_none(self):  self._netlist.select_none()

    def _clear_nets(self):
        self._netlist.clear()
        self._netcount.set("Networks: 0")

    # ── results ───────────────────────────────────────────────────────────

    def _add_result(self, essid, bssid, enc, password):
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        entry = dict(time=ts, essid=essid, bssid=bssid, enc=enc, password=password)
        self._results.append(entry)
        self._rtree.insert("", tk.END, values=(ts, essid, bssid, enc, password))
        self._save_results()

    def _refresh_results(self):
        for r in self._rtree.get_children():
            self._rtree.delete(r)
        for r in self._results:
            self._rtree.insert("", tk.END,
                values=(r["time"], r["essid"], r["bssid"], r["enc"], r["password"]))

    def _save_results(self):
        try:
            with open(self._log, "w") as f:
                json.dump(self._results, f, indent=2)
        except Exception:
            pass

    def _load_results(self):
        try:
            with open(self._log) as f:
                self._results = json.load(f)
        except Exception:
            self._results = []

    def _clear_results(self):
        if not messagebox.askyesno("Clear", "Delete all saved results?"):
            return
        self._results.clear()
        self._refresh_results()
        self._save_results()

    def _export(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv"), ("JSON", "*.json")])
        if not path:
            return
        try:
            if path.endswith(".json"):
                with open(path, "w") as f:
                    json.dump(self._results, f, indent=2)
            else:
                with open(path, "w") as f:
                    f.write("Time,ESSID,BSSID,ENC,Password\n")
                    for r in self._results:
                        f.write(f"{r['time']},{r['essid']},{r['bssid']},"
                                f"{r['enc']},{r['password']}\n")
        except Exception as e:
            messagebox.showerror("Export Error", str(e))

    # ── misc ──────────────────────────────────────────────────────────────

    def _clear_out(self):
        self._out.configure(state=tk.NORMAL)
        self._out.delete("1.0", tk.END)
        self._out.configure(state=tk.DISABLED)

    def _browse_wl(self):
        path = filedialog.askopenfilename(title="Select Wordlist")
        if path:
            self._wl.set(path)

    def _on_close(self):
        if self._running and not messagebox.askyesno("Quit", "Process running. Quit anyway?"):
            return
        if self._running:
            self._stop()
        self.destroy()


def main():
    require_root()
    App().mainloop()


if __name__ == "__main__":
    main()
