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

## Requirements

- Python 3.10+
- Linux (or WSL on Windows)
- [wifite2](https://github.com/derv82/wifite2)

```bash
sudo apt install wifite
```

## Installation

```bash
git clone https://github.com/dasax0s/wifite-gui
cd wifite-gui
python wifite_gui.py
```

## Usage

1. Select your wireless interface from the dropdown
2. Click **Scan** to discover nearby networks
3. Check the networks you want to target
4. Configure attack options (wordlist, timeout, attack types)
5. Click **Attack** and confirm

On Windows the app runs in demo mode (simulated output) since wifite requires Linux.

## Screenshots

> Coming soon

## Disclaimer

This tool is intended for **educational purposes and authorized security testing only**.  
The author is not responsible for any misuse or illegal activity.  
Always obtain written permission before testing any network.

## License

MIT
