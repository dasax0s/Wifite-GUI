# ⚡ Wifite GUI

A graphical front-end for the [wifite](https://github.com/derv82/wifite2) wireless auditing tool, built with Python and tkinter.

**Created by dasax0s**

> ⚠️ For authorized penetration testing only. Only use on networks you own or have explicit written permission to test.

---

## Features

- **Network Scanner** — automatically discovers nearby Wi-Fi networks with ESSID, BSSID, channel, encryption type, and signal strength
- **Attack Options** — WPA Handshake, WPS Pixie-Dust, WEP, and PMKID attacks with configurable parameters
- **Live Output** — real-time color-coded output from wifite
- **Results Log** — saves cracked credentials with timestamps, exportable to CSV or JSON
- **Command Preview** — shows the exact wifite command before execution
- **Auto Root Elevation** — automatically re-launches with `sudo` if not running as root

---

## Requirements

- Python 3.10+
- Linux (Debian/Ubuntu, Fedora, or Arch) — or WSL on Windows
- Wireless adapter that supports monitor mode

---

## Installation

### Automatic (recommended)

```bash
sudo apt update   # run this first before installing
git clone https://github.com/dasax0s/wifite-gui
cd wifite-gui
chmod +x install.sh
sudo ./install.sh
```

The installer automatically:
- Detects your package manager (`apt` / `dnf` / `pacman`)
- Installs all dependencies: `wifite`, `aircrack-ng`, `hcxdumptool`, `hcxtools`, `hashcat`, `python3-tk`
- Falls back to installing wifite from source if not in repos
- Creates a `/usr/local/bin/wifite-gui` launcher
- Adds a desktop shortcut to your applications menu

### Manual

```bash
# Debian / Ubuntu
sudo apt install python3 python3-tk wifite aircrack-ng hcxdumptool hcxtools hashcat

# Arch
sudo pacman -S python python-tk aircrack-ng wifite hcxdumptool hcxtools hashcat

# Fedora
sudo dnf install python3 python3-tkinter aircrack-ng hashcat
```

---

## Usage

```bash
# After install.sh:
wifite-gui

# Or directly:
sudo python3 wifite_gui.py
```

1. Select your wireless interface from the dropdown
2. Click **Monitor Mode** to enable monitor mode on the interface
3. Click **Scan** to discover nearby networks
4. Check (✓) the networks you want to target
5. Configure attack options — wordlist, timeout, min signal, attack types
6. Review the generated command in the **Command** tab
7. Click **Attack** and confirm

> On Windows the app runs in demo mode (simulated output) since wifite requires Linux.

---

## Attack Types

| Attack | Description |
|---|---|
| WPA Handshake | Captures 4-way handshake, cracks offline with hashcat |
| WPS Pixie-Dust | Exploits weak WPS implementations, often instant |
| PMKID | Clientless WPA attack, no handshake needed |
| WEP | Deprecated encryption, cracked via IV collection |

---

## Files

| File | Description |
|---|---|
| `wifite_gui.py` | Main GUI application |
| `install.sh` | Automatic dependency installer |

---

## Screenshots

> Coming soon

---

## Disclaimer

This tool is intended for **educational purposes and authorized security testing only**.  
The author is not responsible for any misuse or illegal activity.  
Always obtain written permission before testing any network.

---

## License

MIT
