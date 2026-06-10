#!/usr/bin/env python3
"""
Wifite GUI — graphical front-end for wifite.
Created by dasax0s.
For authorized penetration testing only.
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
import subprocess, threading, queue, os, sys, re, json, datetime, shutil

# ── colours ──────────────────────────────────────────────────────────────
BG      = "#1e1e2e"
PANEL   = "#2a2a3e"
ENTRY   = "#313244"
SEL     = "#45475a"
FG      = "#cdd6f4"
DIM     = "#6c7086"
ACCENT  = "#89b4fa"
GREEN   = "#a6e3a1"
ORANGE  = "#fab387"
RED     = "#f38ba8"

FONT  = ("Consolas", 10)
FONTB = ("Consolas", 10, "bold")
FONTS = ("Consolas", 9)

# ── system helpers ────────────────────────────────────────────────────────

def on_linux() -> bool:
    return sys.platform.startswith("linux")


def detect_interfaces() -> list[str]:
    try:
        out = subprocess.check_output(["iwconfig"], stderr=subprocess.DEVNULL, text=True)
        ifaces = re.findall(r"^(\w+)\s+IEEE", out, re.MULTILINE)
        return ifaces if ifaces else []
    except Exception:
        return []


def detect_wordlist() -> str:
    candidates = [
        "/usr/share/wordlists/rockyou.txt",
        "/usr/share/wordlists/rockyou.txt.gz",
        "/usr/share/wordlists/fasttrack.txt",
        "/usr/share/wordlists/dirb/common.txt",
        "/opt/wordlists/rockyou.txt",
        os.path.expanduser("~/wordlists/rockyou.txt"),
    ]
    for path in candidates:
        if os.path.isfile(path):
            return path
    return ""


def require_root():
    if not on_linux():
        return
    if os.geteuid() == 0:
        return
    print("[*] Root required — re-launching with sudo...")
    os.execvp("sudo", ["sudo", sys.executable] + sys.argv)


# ── main window ───────────────────────────────────────────────────────────

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Wifite GUI — by dasax0s")
        self.geometry("1050x680")
        self.minsize(800, 560)
        self.configure(bg=BG)

        self._proc: subprocess.Popen | None = None
        self._q: queue.Queue = queue.Queue()
        self._running = False
        self._networks: list[dict] = []
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
        pane.add(left, width=360, minsize=240)
        pane.add(right, minsize=280)
        self._build_networks(left)
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

        self._btn(bar, "↻", self._populate_interfaces, DIM)
        self._btn(bar, "Monitor Mode", self._toggle_monitor, ACCENT)
        tk.Frame(bar, bg=DIM, width=1).pack(side=tk.LEFT, fill=tk.Y, pady=6, padx=6)
        self._scan_btn   = self._btn(bar, "▶ Scan",   self._scan,   GREEN)
        self._attack_btn = self._btn(bar, "⚔ Attack", self._attack, ORANGE)
        self._stop_btn   = self._btn(bar, "■ Stop",   self._stop,   RED)
        self._stop_btn.configure(state=tk.DISABLED)

    def _btn(self, parent, text, cmd, fg, side=tk.LEFT, **kw):
        b = tk.Button(parent, text=text, command=cmd, bg=PANEL, fg=fg,
                      relief=tk.FLAT, activebackground=SEL, activeforeground=fg,
                      font=FONTB, cursor="hand2", padx=8, pady=6)
        b.pack(side=side, padx=kw.get("padx", 3))
        return b

    # ── network list ──────────────────────────────────────────────────────

    def _build_networks(self, parent):
        frame = tk.LabelFrame(parent, text="  Networks ", bg=PANEL, fg=ACCENT,
                               font=FONTB, bd=0, padx=4, pady=4)
        frame.pack(fill=tk.BOTH, expand=True, pady=(0, 4))

        btns = tk.Frame(frame, bg=PANEL)
        btns.pack(fill=tk.X, pady=(0, 4))
        for txt, cmd in [("All", self._sel_all), ("None", self._sel_none),
                         ("Clear", self._clear_nets)]:
            tk.Button(btns, text=txt, command=cmd, bg=ENTRY, fg=FG,
                      relief=tk.FLAT, font=FONTS, cursor="hand2",
                      padx=6).pack(side=tk.LEFT, padx=2)

        cols = ("sel", "essid", "bssid", "ch", "enc", "pwr")
        self._tree = ttk.Treeview(frame, columns=cols, show="headings",
                                   selectmode="browse", height=12)
        hdrs = [("✓",30), ("ESSID",130), ("BSSID",130), ("CH",34), ("ENC",52), ("PWR",44)]
        for col, (lbl, w) in zip(cols, hdrs):
            self._tree.heading(col, text=lbl)
            self._tree.column(col, width=w,
                               anchor=tk.W if col in ("essid","bssid") else tk.CENTER)
        vsb = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=self._tree.yview)
        self._tree.configure(yscrollcommand=vsb.set)
        self._tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        self._tree.bind("<Button-1>", self._toggle_sel)

    # ── attack options ────────────────────────────────────────────────────

    def _build_options(self, parent):
        frame = tk.LabelFrame(parent, text="  Options ", bg=PANEL, fg=ACCENT,
                               font=FONTB, bd=0, padx=8, pady=6)
        frame.pack(fill=tk.X)

        row1 = tk.Frame(frame, bg=PANEL)
        row1.pack(fill=tk.X)
        self._wpa   = self._check(row1, "WPA",   True)
        self._wps   = self._check(row1, "WPS",   True)
        self._pmkid = self._check(row1, "PMKID", True)
        self._wep   = self._check(row1, "WEP",   False)

        row2 = tk.Frame(frame, bg=PANEL)
        row2.pack(fill=tk.X, pady=(6, 0))
        self._kill_nm = self._check(row2, "Kill NetworkManager", True)
        self._verbose = self._check(row2, "Verbose", False)

        row3 = tk.Frame(frame, bg=PANEL)
        row3.pack(fill=tk.X, pady=(6, 0))
        self._timeout = self._labeled_entry(row3, "Timeout:", "300", 5)
        self._minpwr  = self._labeled_entry(row3, "Min PWR:", "-80", 4)

        wl_row = tk.Frame(frame, bg=PANEL)
        wl_row.pack(fill=tk.X, pady=(6, 0))
        tk.Label(wl_row, text="Wordlist:", bg=PANEL, fg=DIM,
                 font=FONTS).pack(side=tk.LEFT)
        self._wl = tk.StringVar(value=detect_wordlist())
        tk.Entry(wl_row, textvariable=self._wl, bg=ENTRY, fg=FG,
                 insertbackground=FG, relief=tk.FLAT, font=FONTS,
                 width=24).pack(side=tk.LEFT, padx=4)
        tk.Button(wl_row, text="…", command=self._browse_wl, bg=ENTRY,
                  fg=ACCENT, relief=tk.FLAT, font=FONTS,
                  cursor="hand2").pack(side=tk.LEFT)

        # warn if no wordlist found
        if not self._wl.get():
            tk.Label(frame, text="⚠ No wordlist found — WPA cracking needs one",
                     bg=PANEL, fg=ORANGE, font=FONTS).pack(anchor=tk.W, pady=(4, 0))

    def _check(self, parent, text, default):
        var = tk.BooleanVar(value=default)
        tk.Checkbutton(parent, text=text, variable=var, bg=PANEL, fg=FG,
                       selectcolor=ENTRY, activebackground=PANEL,
                       activeforeground=FG, font=FONTS,
                       cursor="hand2").pack(side=tk.LEFT, padx=5)
        return var

    def _labeled_entry(self, parent, label, default, width):
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

        # live output
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

        # results
        res_frame = tk.Frame(nb, bg=BG)
        nb.add(res_frame, text="  Results  ")
        cols = ("time", "essid", "bssid", "enc", "password")
        self._rtree = ttk.Treeview(res_frame, columns=cols, show="headings")
        for col, lbl, w in [("time","Time",130), ("essid","ESSID",150),
                             ("bssid","BSSID",140), ("enc","ENC",55),
                             ("password","Password",200)]:
            self._rtree.heading(col, text=lbl)
            self._rtree.column(col, width=w)
        vsb2 = ttk.Scrollbar(res_frame, orient=tk.VERTICAL,
                              command=self._rtree.yview)
        self._rtree.configure(yscrollcommand=vsb2.set)
        self._rtree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(4,0), pady=4)
        vsb2.pack(side=tk.RIGHT, fill=tk.Y, pady=4)

        btn_row = tk.Frame(res_frame, bg=BG)
        btn_row.pack(side=tk.BOTTOM, fill=tk.X, padx=4, pady=4)
        tk.Button(btn_row, text="Export CSV", command=self._export,
                  bg=ENTRY, fg=ACCENT, relief=tk.FLAT, font=FONTS,
                  cursor="hand2").pack(side=tk.LEFT, padx=2)
        tk.Button(btn_row, text="Clear", command=self._clear_results,
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
        self._netcount = tk.StringVar(value="Networks: 0")
        tk.Label(bar, textvariable=self._netcount, bg=PANEL, fg=DIM,
                 font=FONTS).pack(side=tk.RIGHT, padx=10)
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
            mon = iface + "mon"
            self._iface.set(mon)
            self._populate_interfaces()
            self._log_out(f"[+] Monitor mode: {mon}\n", "ok")
        except Exception as e:
            self._log_out(f"[-] airmon-ng failed: {e}\n", "err")

    # ── command building ──────────────────────────────────────────────────

    def _build_cmd(self, bssids: list[str] | None = None) -> list[str]:
        iface = self._iface.get() or "wlan0"
        cmd = ["wifite", "-i", iface]
        if self._wpa.get():   cmd.append("--wpa")
        if self._wps.get():   cmd.append("--wps")
        if self._pmkid.get(): cmd.append("--pmkid")
        if self._wep.get():   cmd.append("--wep")
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
        if bssids and len(bssids) == 1:
            cmd += ["--bssid", bssids[0]]
        return cmd

    # ── scan / attack ─────────────────────────────────────────────────────

    def _scan(self):
        if self._running:
            return
        iface = self._iface.get()
        if not iface:
            messagebox.showwarning("No Interface", "Select a wireless interface first.")
            return
        self._run(["wifite", "-i", iface, "--wpa", "--wps", "--pmkid", "--kill"])

    def _attack(self):
        if self._running:
            return
        selected = [self._tree.item(i, "values")[2]
                    for i in self._tree.get_children()
                    if self._tree.item(i, "values")[0] == "✓"]
        if not selected and not self._tree.get_children():
            messagebox.showwarning("No Networks", "Scan for networks first.")
            return
        if not messagebox.askyesno(
            "Confirm",
            "Only attack networks you own or have written permission to test.\n\nContinue?"
        ):
            return
        self._run(self._build_cmd(selected))

    def _run(self, cmd: list[str]):
        if not on_linux():
            self._log_out("[!] wifite requires Linux.\n", "warn")
            return
        self._running = True
        self._scan_btn.configure(state=tk.DISABLED)
        self._attack_btn.configure(state=tk.DISABLED)
        self._stop_btn.configure(state=tk.NORMAL)
        self._progress.start(12)
        self._status.set("Running: " + " ".join(cmd[:3]) + " ...")
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
                self._q.put(None)  # sentinel

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
        lo = line.lower()
        if any(k in lo for k in ("cracked", "password", "found", "pin")):
            tag = "ok"
            self._parse_result(line)
        elif any(k in lo for k in ("error", "failed")):
            tag = "err"
        elif any(k in lo for k in ("warning", "kill")):
            tag = "warn"
        elif line.startswith("[+]"):
            tag = "hi"
        elif re.match(r"\s*\d+\s+\S+\s+[\dA-Fa-f:]{17}", line):
            tag = "dim"
            self._parse_net(line)
        else:
            tag = None
        self._log_out(line, tag)

    def _parse_net(self, line: str):
        m = re.match(
            r"\s*\d+\s+(\S+)\s+([\dA-Fa-f:]{17})\s+(\d+)\s+(WPA2?|WEP)\s+(-\d+)", line)
        if m:
            self._add_net(*m.groups())

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

    # ── network list ──────────────────────────────────────────────────────

    def _add_net(self, essid, bssid, ch, enc, pwr):
        existing = {self._tree.item(i, "values")[2]
                    for i in self._tree.get_children()}
        if bssid.upper() in existing:
            return
        self._tree.insert("", tk.END, values=("", essid, bssid.upper(), ch, enc, pwr))
        self._networks.append(dict(essid=essid, bssid=bssid.upper(), ch=ch, enc=enc, pwr=pwr))
        self._netcount.set(f"Networks: {len(self._networks)}")

    def _toggle_sel(self, event):
        row = self._tree.identify_row(event.y)
        if not row:
            return
        v = list(self._tree.item(row, "values"))
        v[0] = "" if v[0] == "✓" else "✓"
        self._tree.item(row, values=v)

    def _sel_all(self):
        for r in self._tree.get_children():
            v = list(self._tree.item(r, "values")); v[0] = "✓"
            self._tree.item(r, values=v)

    def _sel_none(self):
        for r in self._tree.get_children():
            v = list(self._tree.item(r, "values")); v[0] = ""
            self._tree.item(r, values=v)

    def _clear_nets(self):
        for r in self._tree.get_children():
            self._tree.delete(r)
        self._networks.clear()
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
