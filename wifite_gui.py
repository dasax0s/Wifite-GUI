#!/usr/bin/env python3
"""
Wifite GUI — graphical front-end for the wifite wireless auditing tool.
Created by dasax0s.
Requires: wifite installed on a Linux system (or WSL on Windows).
For authorized penetration testing only.
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
import subprocess
import threading
import queue
import os
import datetime
import json
import re
import sys
import shutil


DARK_BG = "#1e1e2e"
PANEL_BG = "#2a2a3e"
ACCENT = "#89b4fa"
ACCENT2 = "#a6e3a1"
WARNING = "#fab387"
DANGER = "#f38ba8"
FG = "#cdd6f4"
FG_DIM = "#6c7086"
ENTRY_BG = "#313244"
SEL_BG = "#45475a"

FONT_MAIN = ("Consolas", 10)
FONT_BOLD = ("Consolas", 10, "bold")
FONT_TITLE = ("Consolas", 12, "bold")
FONT_SMALL = ("Consolas", 9)


def is_linux() -> bool:
    return sys.platform.startswith("linux")


def get_interfaces() -> list[str]:
    """Return wireless interface names."""
    try:
        out = subprocess.check_output(["iwconfig"], stderr=subprocess.DEVNULL, text=True)
        return re.findall(r"^(\w+)\s+IEEE", out, re.MULTILINE)
    except Exception:
        return []


class WifiteGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Wifite GUI — by dasax0s")
        self.geometry("1100x720")
        self.minsize(900, 600)
        self.configure(bg=DARK_BG)

        self._process: subprocess.Popen | None = None
        self._output_queue: queue.Queue = queue.Queue()
        self._networks: list[dict] = []
        self._results: list[dict] = []
        self._running = False
        self._log_file_path = os.path.join(
            os.path.expanduser("~"), "wifite_gui_results.json"
        )
        self._load_results()

        self._build_ui()
        self._refresh_interfaces()
        self.after(100, self._poll_output)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ─── UI construction ─────────────────────────────────────────────────

    def _build_ui(self):
        self._build_toolbar()
        self._build_main()
        self._build_statusbar()

    def _build_toolbar(self):
        bar = tk.Frame(self, bg=PANEL_BG, height=46)
        bar.pack(fill=tk.X)
        bar.pack_propagate(False)

        tk.Label(bar, text="⚡ Wifite GUI", bg=PANEL_BG, fg=ACCENT,
                 font=FONT_TITLE).pack(side=tk.LEFT, padx=12)
        tk.Label(bar, text="by dasax0s", bg=PANEL_BG, fg=FG_DIM,
                 font=FONT_SMALL).pack(side=tk.LEFT, padx=(0, 8))

        sep = tk.Frame(bar, bg=FG_DIM, width=1)
        sep.pack(side=tk.LEFT, fill=tk.Y, pady=6, padx=4)

        tk.Label(bar, text="Interface:", bg=PANEL_BG, fg=FG_DIM,
                 font=FONT_MAIN).pack(side=tk.LEFT, padx=(8, 4))

        self._iface_var = tk.StringVar(value="wlan0")
        self._iface_cb = ttk.Combobox(
            bar, textvariable=self._iface_var, width=10,
            state="readonly", font=FONT_MAIN
        )
        self._iface_cb.pack(side=tk.LEFT, padx=4)

        self._btn_refresh_iface = self._toolbar_btn(
            bar, "↻ Interfaces", self._refresh_interfaces, FG_DIM
        )
        self._btn_monitor = self._toolbar_btn(
            bar, "Monitor Mode", self._toggle_monitor, ACCENT
        )

        sep2 = tk.Frame(bar, bg=FG_DIM, width=1)
        sep2.pack(side=tk.LEFT, fill=tk.Y, pady=6, padx=8)

        self._btn_scan = self._toolbar_btn(bar, "▶  Scan", self._start_scan, ACCENT2)
        self._btn_attack = self._toolbar_btn(bar, "⚔  Attack", self._start_attack, WARNING)
        self._btn_stop = self._toolbar_btn(bar, "■  Stop", self._stop, DANGER)
        self._btn_stop.configure(state=tk.DISABLED)

        self._toolbar_btn(bar, "⎙  Export Log", self._export_log, FG_DIM,
                          side=tk.RIGHT, padx=(4, 12))
        self._toolbar_btn(bar, "🗑  Clear Results", self._clear_results, FG_DIM,
                          side=tk.RIGHT)

    def _toolbar_btn(self, parent, text, cmd, fg, side=tk.LEFT, padx=4):
        btn = tk.Button(
            parent, text=text, command=cmd,
            bg=PANEL_BG, fg=fg, relief=tk.FLAT,
            activebackground=SEL_BG, activeforeground=fg,
            font=FONT_BOLD, cursor="hand2", padx=8, pady=6
        )
        btn.pack(side=side, padx=padx)
        return btn

    def _build_main(self):
        pane = tk.PanedWindow(self, orient=tk.HORIZONTAL, bg=DARK_BG,
                              sashwidth=5, sashrelief=tk.FLAT)
        pane.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)

        # ── left column ──
        left = tk.Frame(pane, bg=DARK_BG)
        pane.add(left, width=380, minsize=260)

        self._build_network_list(left)
        self._build_attack_options(left)

        # ── right column ──
        right = tk.Frame(pane, bg=DARK_BG)
        pane.add(right, minsize=300)

        self._build_output_panel(right)

    def _build_network_list(self, parent):
        frame = tk.LabelFrame(parent, text="  Networks ", bg=PANEL_BG, fg=ACCENT,
                               font=FONT_BOLD, bd=0, labelanchor="nw",
                               padx=4, pady=4)
        frame.pack(fill=tk.BOTH, expand=True, pady=(0, 4))

        # toolbar
        btn_bar = tk.Frame(frame, bg=PANEL_BG)
        btn_bar.pack(fill=tk.X, pady=(0, 4))

        for txt, cmd in [("Select All", self._select_all_networks),
                         ("Deselect", self._deselect_networks),
                         ("Clear List", self._clear_networks)]:
            tk.Button(btn_bar, text=txt, command=cmd,
                      bg=ENTRY_BG, fg=FG, relief=tk.FLAT,
                      font=FONT_SMALL, cursor="hand2", padx=6
                      ).pack(side=tk.LEFT, padx=2)

        # columns
        cols = ("sel", "essid", "bssid", "ch", "enc", "pwr")
        self._net_tree = ttk.Treeview(frame, columns=cols, show="headings",
                                       selectmode="browse", height=14)
        headings = {"sel": ("✓", 30), "essid": ("ESSID", 140),
                    "bssid": ("BSSID", 130), "ch": ("CH", 36),
                    "enc": ("ENC", 60), "pwr": ("PWR", 46)}
        for col, (label, width) in headings.items():
            self._net_tree.heading(col, text=label,
                                   command=lambda c=col: self._sort_networks(c))
            self._net_tree.column(col, width=width, anchor=tk.CENTER
                                  if col in ("sel", "ch", "enc", "pwr") else tk.W)

        vsb = ttk.Scrollbar(frame, orient=tk.VERTICAL,
                             command=self._net_tree.yview)
        self._net_tree.configure(yscrollcommand=vsb.set)
        self._net_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        self._net_tree.bind("<Button-1>", self._toggle_network_selection)

        self._apply_treeview_style()

    def _build_attack_options(self, parent):
        frame = tk.LabelFrame(parent, text="  Attack Options ", bg=PANEL_BG,
                               fg=ACCENT, font=FONT_BOLD, bd=0,
                               labelanchor="nw", padx=8, pady=6)
        frame.pack(fill=tk.X, pady=4)

        row1 = tk.Frame(frame, bg=PANEL_BG)
        row1.pack(fill=tk.X)

        self._opt_wpa = self._option_check(row1, "WPA Handshake", True)
        self._opt_wps = self._option_check(row1, "WPS Pixie-Dust", True)
        self._opt_wep = self._option_check(row1, "WEP", False)
        self._opt_pmkid = self._option_check(row1, "PMKID", True)

        row2 = tk.Frame(frame, bg=PANEL_BG)
        row2.pack(fill=tk.X, pady=(6, 0))

        self._add_labeled_entry(row2, "Timeout (s):", "300", 5, "_timeout_var")
        self._add_labeled_entry(row2, "Min PWR:", "-80", 4, "_minpwr_var")

        row3 = tk.Frame(frame, bg=PANEL_BG)
        row3.pack(fill=tk.X, pady=(6, 0))

        self._opt_kill_nm = self._option_check(row3, "Kill NetworkManager", True)
        self._opt_verbose = self._option_check(row3, "Verbose", False)

        wordlist_frame = tk.Frame(frame, bg=PANEL_BG)
        wordlist_frame.pack(fill=tk.X, pady=(6, 0))

        tk.Label(wordlist_frame, text="Wordlist:", bg=PANEL_BG, fg=FG_DIM,
                 font=FONT_SMALL).pack(side=tk.LEFT)
        self._wordlist_var = tk.StringVar(value="/usr/share/wordlists/rockyou.txt")
        tk.Entry(wordlist_frame, textvariable=self._wordlist_var,
                 bg=ENTRY_BG, fg=FG, insertbackground=FG, relief=tk.FLAT,
                 font=FONT_SMALL, width=28).pack(side=tk.LEFT, padx=4)
        tk.Button(wordlist_frame, text="Browse", command=self._browse_wordlist,
                  bg=ENTRY_BG, fg=ACCENT, relief=tk.FLAT, font=FONT_SMALL,
                  cursor="hand2").pack(side=tk.LEFT)

    def _option_check(self, parent, text, default):
        var = tk.BooleanVar(value=default)
        cb = tk.Checkbutton(parent, text=text, variable=var,
                            bg=PANEL_BG, fg=FG, selectcolor=ENTRY_BG,
                            activebackground=PANEL_BG, activeforeground=FG,
                            font=FONT_SMALL, cursor="hand2")
        cb.pack(side=tk.LEFT, padx=6)
        return var

    def _add_labeled_entry(self, parent, label, default, width, attr):
        tk.Label(parent, text=label, bg=PANEL_BG, fg=FG_DIM,
                 font=FONT_SMALL).pack(side=tk.LEFT, padx=(0, 2))
        var = tk.StringVar(value=default)
        setattr(self, attr, var)
        tk.Entry(parent, textvariable=var, bg=ENTRY_BG, fg=FG,
                 insertbackground=FG, relief=tk.FLAT, font=FONT_SMALL,
                 width=width).pack(side=tk.LEFT, padx=(0, 12))

    def _build_output_panel(self, parent):
        nb = ttk.Notebook(parent)
        nb.pack(fill=tk.BOTH, expand=True)

        # ── Live Output ──
        live_frame = tk.Frame(nb, bg=DARK_BG)
        nb.add(live_frame, text="  Live Output  ")

        ctrl = tk.Frame(live_frame, bg=DARK_BG)
        ctrl.pack(fill=tk.X, pady=(4, 2))

        self._autoscroll_var = tk.BooleanVar(value=True)
        tk.Checkbutton(ctrl, text="Auto-scroll", variable=self._autoscroll_var,
                       bg=DARK_BG, fg=FG_DIM, selectcolor=ENTRY_BG,
                       activebackground=DARK_BG, font=FONT_SMALL).pack(side=tk.LEFT, padx=4)
        tk.Button(ctrl, text="Clear", command=self._clear_output,
                  bg=ENTRY_BG, fg=FG_DIM, relief=tk.FLAT, font=FONT_SMALL,
                  cursor="hand2").pack(side=tk.RIGHT, padx=4)
        tk.Button(ctrl, text="Save Output", command=self._save_output,
                  bg=ENTRY_BG, fg=FG_DIM, relief=tk.FLAT, font=FONT_SMALL,
                  cursor="hand2").pack(side=tk.RIGHT, padx=4)

        self._output_text = scrolledtext.ScrolledText(
            live_frame, bg="#11111b", fg=FG, insertbackground=FG,
            font=("Consolas", 9), relief=tk.FLAT, state=tk.DISABLED,
            wrap=tk.WORD
        )
        self._output_text.pack(fill=tk.BOTH, expand=True, padx=4, pady=(0, 4))
        self._configure_output_tags()

        # ── Results Log ──
        results_frame = tk.Frame(nb, bg=DARK_BG)
        nb.add(results_frame, text="  Results Log  ")
        self._build_results_table(results_frame)

        # ── Command Preview ──
        cmd_frame = tk.Frame(nb, bg=DARK_BG)
        nb.add(cmd_frame, text="  Command  ")

        tk.Label(cmd_frame, text="Command that will be executed:",
                 bg=DARK_BG, fg=FG_DIM, font=FONT_SMALL).pack(anchor=tk.W, padx=8, pady=4)
        self._cmd_text = scrolledtext.ScrolledText(
            cmd_frame, bg=ENTRY_BG, fg=ACCENT2, insertbackground=FG,
            font=("Consolas", 10), relief=tk.FLAT, height=5, wrap=tk.WORD
        )
        self._cmd_text.pack(fill=tk.X, padx=8)

        tk.Button(cmd_frame, text="Copy to Clipboard", command=self._copy_command,
                  bg=ENTRY_BG, fg=ACCENT, relief=tk.FLAT, font=FONT_SMALL,
                  cursor="hand2").pack(anchor=tk.W, padx=8, pady=4)

        # Update command preview on option changes
        for var in (self._opt_wpa, self._opt_wps, self._opt_wep, self._opt_pmkid,
                    self._opt_kill_nm, self._opt_verbose, self._wordlist_var,
                    self._timeout_var, self._minpwr_var, self._iface_var):
            var.trace_add("write", lambda *_: self.after(50, self._update_cmd_preview))
        self._update_cmd_preview()

    def _build_results_table(self, parent):
        cols = ("time", "essid", "bssid", "enc", "password")
        self._results_tree = ttk.Treeview(parent, columns=cols, show="headings")
        hdrs = {"time": ("Time", 130), "essid": ("ESSID", 160),
                "bssid": ("BSSID", 140), "enc": ("ENC", 60),
                "password": ("Password", 200)}
        for col, (label, width) in hdrs.items():
            self._results_tree.heading(col, text=label)
            self._results_tree.column(col, width=width)

        vsb2 = ttk.Scrollbar(parent, orient=tk.VERTICAL,
                              command=self._results_tree.yview)
        self._results_tree.configure(yscrollcommand=vsb2.set)
        self._results_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True,
                                padx=(4, 0), pady=4)
        vsb2.pack(side=tk.RIGHT, fill=tk.Y, pady=4)
        self._refresh_results_table()

    def _build_statusbar(self):
        bar = tk.Frame(self, bg=PANEL_BG, height=26)
        bar.pack(fill=tk.X, side=tk.BOTTOM)
        bar.pack_propagate(False)

        self._status_var = tk.StringVar(value="Ready")
        tk.Label(bar, textvariable=self._status_var, bg=PANEL_BG, fg=FG_DIM,
                 font=FONT_SMALL, anchor=tk.W).pack(side=tk.LEFT, padx=10)

        self._net_count_var = tk.StringVar(value="Networks: 0")
        tk.Label(bar, textvariable=self._net_count_var, bg=PANEL_BG, fg=FG_DIM,
                 font=FONT_SMALL).pack(side=tk.RIGHT, padx=10)

        self._progress = ttk.Progressbar(bar, mode="indeterminate", length=160)
        self._progress.pack(side=tk.RIGHT, padx=8, pady=4)

    # ─── Styling ────────────────────────────────────────────────────────

    def _apply_treeview_style(self):
        style = ttk.Style(self)
        style.theme_use("default")
        style.configure("Treeview", background=PANEL_BG, foreground=FG,
                        fieldbackground=PANEL_BG, rowheight=22, font=FONT_SMALL)
        style.configure("Treeview.Heading", background=ENTRY_BG, foreground=ACCENT,
                        font=FONT_BOLD, relief=tk.FLAT)
        style.map("Treeview", background=[("selected", SEL_BG)])
        style.configure("TNotebook", background=DARK_BG, borderwidth=0)
        style.configure("TNotebook.Tab", background=PANEL_BG, foreground=FG_DIM,
                        font=FONT_SMALL, padding=(10, 4))
        style.map("TNotebook.Tab",
                  background=[("selected", DARK_BG)],
                  foreground=[("selected", ACCENT)])
        style.configure("TCombobox", fieldbackground=ENTRY_BG, background=ENTRY_BG,
                        foreground=FG, selectbackground=SEL_BG)
        style.configure("TScrollbar", background=PANEL_BG, troughcolor=ENTRY_BG,
                        borderwidth=0, arrowsize=12)

    def _configure_output_tags(self):
        self._output_text.tag_configure("info", foreground=FG)
        self._output_text.tag_configure("success", foreground=ACCENT2)
        self._output_text.tag_configure("warning", foreground=WARNING)
        self._output_text.tag_configure("error", foreground=DANGER)
        self._output_text.tag_configure("found", foreground=ACCENT)
        self._output_text.tag_configure("dim", foreground=FG_DIM)

    # ─── Interface management ────────────────────────────────────────────

    def _refresh_interfaces(self):
        ifaces = get_interfaces()
        if not ifaces:
            ifaces = ["wlan0", "wlan1", "wlp2s0"]  # fallback suggestions
        self._iface_cb["values"] = ifaces
        if ifaces:
            self._iface_var.set(ifaces[0])

    def _toggle_monitor(self):
        iface = self._iface_var.get()
        if not iface:
            return
        if not is_linux():
            self._append_output(
                "[!] Monitor mode control requires Linux. Use a real interface.\n", "warning"
            )
            return
        try:
            subprocess.run(["airmon-ng", "start", iface], check=True)
            mon = iface + "mon"
            self._iface_var.set(mon)
            self._append_output(f"[+] Monitor mode enabled: {mon}\n", "success")
        except Exception as e:
            self._append_output(f"[-] Failed to enable monitor mode: {e}\n", "error")

    # ─── Command building ────────────────────────────────────────────────

    def _build_command(self, targets: list[str] | None = None) -> list[str]:
        iface = self._iface_var.get() or "wlan0"
        # no sudo prefix — script is already running as root
        cmd = ["wifite", "-i", iface]

        if self._opt_wpa.get():
            cmd.append("--wpa")
        if self._opt_wps.get():
            cmd.append("--wps")
        if self._opt_wep.get():
            cmd.append("--wep")
        if self._opt_pmkid.get():
            cmd.append("--pmkid")
        if self._opt_kill_nm.get():
            cmd.append("--kill")
        if self._opt_verbose.get():
            cmd.append("--verbose")

        timeout = self._timeout_var.get().strip()
        if timeout.isdigit():
            cmd += ["--timeout", timeout]

        minpwr = self._minpwr_var.get().strip()
        try:
            int(minpwr)
            cmd += ["--min-power", minpwr]
        except ValueError:
            pass

        wl = self._wordlist_var.get().strip()
        if wl:
            cmd += ["-dict", wl]

        if targets:
            cmd += ["--bssid", targets[0]] if len(targets) == 1 else []

        return cmd

    def _update_cmd_preview(self):
        cmd = self._build_command()
        self._cmd_text.delete("1.0", tk.END)
        self._cmd_text.insert(tk.END, " ".join(cmd))

    def _copy_command(self):
        cmd = self._cmd_text.get("1.0", tk.END).strip()
        self.clipboard_clear()
        self.clipboard_append(cmd)

    # ─── Scan / Attack ───────────────────────────────────────────────────

    def _start_scan(self):
        if self._running:
            messagebox.showwarning("Running", "Stop the current process first.")
            return
        iface = self._iface_var.get()
        cmd = ["sudo", "wifite", "-i", iface, "--wpa", "--wps", "--pmkid",
               "--kill", "--scan"]
        self._run_process(cmd, scan_mode=True)

    def _start_attack(self):
        if self._running:
            messagebox.showwarning("Running", "Stop the current process first.")
            return

        selected = [self._net_tree.item(i, "values")[2]   # BSSID column
                    for i in self._net_tree.get_children()
                    if self._net_tree.item(i, "values")[0] == "✓"]

        cmd = self._build_command(selected)

        if not messagebox.askyesno(
            "Confirm Attack",
            "You are about to run an attack.\n\n"
            "Only use this on networks you own or have explicit written permission to test.\n\n"
            "Continue?",
        ):
            return
        self._run_process(cmd, scan_mode=False)

    def _run_process(self, cmd: list[str], scan_mode: bool):
        if not is_linux() and not shutil.which("wsl"):
            self._append_output(
                "[!] wifite requires Linux. On Windows use WSL.\n"
                "    Showing simulated output for demonstration.\n\n", "warning"
            )
            self._simulate_output(scan_mode)
            return

        self._running = True
        self._btn_scan.configure(state=tk.DISABLED)
        self._btn_attack.configure(state=tk.DISABLED)
        self._btn_stop.configure(state=tk.NORMAL)
        self._progress.start(12)
        self._set_status(f"Running: {' '.join(cmd[:4])} ...")

        def worker():
            try:
                self._process = subprocess.Popen(
                    cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    text=True, bufsize=1
                )
                for line in self._process.stdout:
                    self._output_queue.put(("line", line))
                self._process.wait()
            except FileNotFoundError:
                self._output_queue.put(("line",
                    "[-] wifite not found. Install with: sudo apt install wifite\n"))
            except Exception as e:
                self._output_queue.put(("line", f"[-] Error: {e}\n"))
            finally:
                self._output_queue.put(("done", None))

        threading.Thread(target=worker, daemon=True).start()

    def _stop(self):
        if self._process:
            try:
                self._process.terminate()
            except Exception:
                pass
        self._running = False
        self._btn_scan.configure(state=tk.NORMAL)
        self._btn_attack.configure(state=tk.NORMAL)
        self._btn_stop.configure(state=tk.DISABLED)
        self._progress.stop()
        self._set_status("Stopped")
        self._append_output("[!] Process stopped by user.\n", "warning")

    # ─── Demo simulation (Windows / no wifite) ──────────────────────────

    def _simulate_output(self, scan_mode: bool):
        self._running = True
        self._btn_scan.configure(state=tk.DISABLED)
        self._btn_attack.configure(state=tk.DISABLED)
        self._btn_stop.configure(state=tk.NORMAL)
        self._progress.start(12)

        demo_scan = [
            ("[*] Enabling monitor mode on wlan0\n", "info"),
            ("[+] Monitor mode enabled: wlan0mon\n", "success"),
            ("[*] Scanning for wireless networks...\n\n", "info"),
            (" NUM  ESSID               BSSID              CH  ENC  PWR\n", "dim"),
            ("  1   HomeNetwork         AA:BB:CC:DD:EE:FF  6   WPA2 -45\n", "info"),
            ("  2   OfficeWifi          11:22:33:44:55:66  11  WPA2 -62\n", "info"),
            ("  3   GuestNetwork        AA:11:BB:22:CC:33  1   WPA  -78\n", "info"),
            ("  4   [WPS] FastRouter    DE:AD:BE:EF:CA:FE  6   WPA2 -55\n", "found"),
            ("\n[*] Scan complete. 4 networks found.\n", "info"),
        ]

        demo_attack = [
            ("[*] Attacking network: HomeNetwork (AA:BB:CC:DD:EE:FF)\n", "info"),
            ("[*] Attempting PMKID attack...\n", "info"),
            ("[*] Running hcxdumptool...\n", "dim"),
            ("[*] Got PMKID. Running hashcat...\n", "info"),
            ("[+] Cracked PMKID: password123\n", "success"),
            ("[+] Results saved to /root/hs/HomeNetwork.txt\n\n", "success"),
            ("[*] Attacking network: FastRouter (DE:AD:BE:EF:CA:FE)\n", "info"),
            ("[*] Attempting WPS Pixie-Dust attack...\n", "info"),
            ("[+] WPS PIN found: 12345670  Password: Str0ngP@ss!\n", "success"),
        ]

        lines = demo_scan if scan_mode else demo_attack

        def feed(idx=0):
            if idx < len(lines):
                text, tag = lines[idx]
                self._output_queue.put(("line_tagged", (text, tag)))
                if scan_mode and "NUM" not in text and "BSSID" in (
                    ("AA:BB:CC:DD:EE:FF" if "HomeN" in text else "")
                ):
                    pass
                self.after(350, lambda: feed(idx + 1))
            else:
                if scan_mode:
                    self._inject_demo_networks()
                else:
                    self._inject_demo_result()
                self._output_queue.put(("done", None))

        self.after(300, feed)

    def _inject_demo_networks(self):
        demo = [
            ("HomeNetwork",   "AA:BB:CC:DD:EE:FF", "6",  "WPA2", "-45"),
            ("OfficeWifi",    "11:22:33:44:55:66", "11", "WPA2", "-62"),
            ("GuestNetwork",  "AA:11:BB:22:CC:33", "1",  "WPA",  "-78"),
            ("FastRouter",    "DE:AD:BE:EF:CA:FE", "6",  "WPA2", "-55"),
        ]
        for essid, bssid, ch, enc, pwr in demo:
            self._add_network(essid, bssid, ch, enc, pwr)

    def _inject_demo_result(self):
        self._add_result("HomeNetwork", "AA:BB:CC:DD:EE:FF", "WPA2", "password123")
        self._add_result("FastRouter",  "DE:AD:BE:EF:CA:FE", "WPA2", "Str0ngP@ss!")

    # ─── Output polling ──────────────────────────────────────────────────

    def _poll_output(self):
        try:
            while True:
                item = self._output_queue.get_nowait()
                kind, data = item
                if kind == "line":
                    self._process_line(data)
                elif kind == "line_tagged":
                    self._append_output(*data)
                elif kind == "done":
                    self._running = False
                    self._btn_scan.configure(state=tk.NORMAL)
                    self._btn_attack.configure(state=tk.NORMAL)
                    self._btn_stop.configure(state=tk.DISABLED)
                    self._progress.stop()
                    self._set_status("Finished")
        except queue.Empty:
            pass
        self.after(80, self._poll_output)

    def _process_line(self, line: str):
        line_l = line.lower()
        if any(k in line_l for k in ("cracked", "password", "found", "pin")):
            tag = "success"
            self._parse_cracked(line)
        elif any(k in line_l for k in ("error", "failed", "not found")):
            tag = "error"
        elif any(k in line_l for k in ("warning", "kill")):
            tag = "warning"
        elif line_l.startswith("[+]"):
            tag = "found"
        elif any(k in line_l for k in ("num", "essid", "bssid")):
            tag = "dim"
            self._parse_network_line(line)
        elif re.match(r"\s+\d+\s+\S", line):
            tag = "info"
            self._parse_network_line(line)
        else:
            tag = "info"
        self._append_output(line, tag)

    def _parse_network_line(self, line: str):
        m = re.match(
            r"\s*\d+\s+(\S+)\s+([\dA-Fa-f:]{17})\s+(\d+)\s+(WPA2?|WEP)\s+(-\d+)",
            line
        )
        if m:
            self._add_network(*m.groups())

    def _parse_cracked(self, line: str):
        m = re.search(r"(\S+)\s+\(([A-Fa-f0-9:]{17})\).+?:\s+(.+)", line)
        if m:
            self._add_result(m.group(1), m.group(2), "WPA2", m.group(3).strip())

    def _append_output(self, text: str, tag: str = "info"):
        self._output_text.configure(state=tk.NORMAL)
        self._output_text.insert(tk.END, text, tag)
        if self._autoscroll_var.get():
            self._output_text.see(tk.END)
        self._output_text.configure(state=tk.DISABLED)

    # ─── Network list management ─────────────────────────────────────────

    def _add_network(self, essid, bssid, ch, enc, pwr):
        existing = {self._net_tree.item(i, "values")[2]
                    for i in self._net_tree.get_children()}
        if bssid.upper() in existing:
            return
        self._net_tree.insert("", tk.END,
                              values=("", essid, bssid.upper(), ch, enc, pwr))
        self._networks.append({"essid": essid, "bssid": bssid.upper(),
                                "ch": ch, "enc": enc, "pwr": pwr})
        self._net_count_var.set(f"Networks: {len(self._networks)}")

    def _toggle_network_selection(self, event):
        row = self._net_tree.identify_row(event.y)
        if not row:
            return
        vals = list(self._net_tree.item(row, "values"))
        vals[0] = "" if vals[0] == "✓" else "✓"
        self._net_tree.item(row, values=vals)

    def _select_all_networks(self):
        for row in self._net_tree.get_children():
            vals = list(self._net_tree.item(row, "values"))
            vals[0] = "✓"
            self._net_tree.item(row, values=vals)

    def _deselect_networks(self):
        for row in self._net_tree.get_children():
            vals = list(self._net_tree.item(row, "values"))
            vals[0] = ""
            self._net_tree.item(row, values=vals)

    def _clear_networks(self):
        for row in self._net_tree.get_children():
            self._net_tree.delete(row)
        self._networks.clear()
        self._net_count_var.set("Networks: 0")

    def _sort_networks(self, col):
        rows = [(self._net_tree.item(i, "values"), i)
                for i in self._net_tree.get_children()]
        cols = ("sel", "essid", "bssid", "ch", "enc", "pwr")
        idx = cols.index(col)
        rows.sort(key=lambda x: x[0][idx])
        for pos, (_, iid) in enumerate(rows):
            self._net_tree.move(iid, "", pos)

    # ─── Results management ──────────────────────────────────────────────

    def _add_result(self, essid, bssid, enc, password):
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        entry = {"time": ts, "essid": essid, "bssid": bssid,
                 "enc": enc, "password": password}
        self._results.append(entry)
        self._results_tree.insert("", tk.END,
                                  values=(ts, essid, bssid, enc, password))
        self._save_results()

    def _refresh_results_table(self):
        for row in self._results_tree.get_children():
            self._results_tree.delete(row)
        for r in self._results:
            self._results_tree.insert("", tk.END,
                values=(r["time"], r["essid"], r["bssid"], r["enc"], r["password"]))

    def _clear_results(self):
        if not messagebox.askyesno("Clear Results", "Delete all saved results?"):
            return
        self._results.clear()
        self._refresh_results_table()
        self._save_results()

    def _save_results(self):
        try:
            with open(self._log_file_path, "w") as f:
                json.dump(self._results, f, indent=2)
        except Exception:
            pass

    def _load_results(self):
        try:
            with open(self._log_file_path) as f:
                self._results = json.load(f)
        except Exception:
            self._results = []

    def _export_log(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv"), ("JSON", "*.json"), ("All", "*.*")],
            title="Export Results"
        )
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
            messagebox.showinfo("Exported", f"Saved to:\n{path}")
        except Exception as e:
            messagebox.showerror("Export Error", str(e))

    # ─── Misc ────────────────────────────────────────────────────────────

    def _clear_output(self):
        self._output_text.configure(state=tk.NORMAL)
        self._output_text.delete("1.0", tk.END)
        self._output_text.configure(state=tk.DISABLED)

    def _save_output(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text", "*.txt"), ("All", "*.*")]
        )
        if path:
            with open(path, "w") as f:
                f.write(self._output_text.get("1.0", tk.END))

    def _browse_wordlist(self):
        path = filedialog.askopenfilename(title="Select Wordlist")
        if path:
            self._wordlist_var.set(path)

    def _set_status(self, msg: str):
        self._status_var.set(msg)

    def _on_close(self):
        if self._running:
            if not messagebox.askyesno("Quit", "A process is still running. Quit anyway?"):
                return
            self._stop()
        self.destroy()


def require_root():
    """Re-launch the script with sudo if not already root (Linux only)."""
    if not is_linux():
        return
    if os.geteuid() == 0:
        return
    print("[*] Root required. Re-launching with sudo...")
    args = ["sudo", sys.executable] + sys.argv
    try:
        os.execvp("sudo", args)
    except Exception as e:
        print(f"[-] Failed to elevate: {e}")
        sys.exit(1)


def main():
    require_root()
    app = WifiteGUI()
    app.mainloop()


if __name__ == "__main__":
    main()
