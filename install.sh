#!/usr/bin/env bash
# Wifite GUI — installer
# Created by dasax0s

set -eo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

info()    { echo -e "${CYAN}[*]${NC} $*"; }
success() { echo -e "${GREEN}[+]${NC} $*"; }
warn()    { echo -e "${YELLOW}[!]${NC} $*"; }
error()   { echo -e "${RED}[-]${NC} $*"; exit 1; }

# ── root check ──────────────────────────────────────────────────────────
if [[ $EUID -ne 0 ]]; then
    warn "Not root. Re-running with sudo..."
    exec sudo bash "$0" "$@"
fi

echo ""
echo -e "${CYAN}  ⚡ Wifite GUI Installer — by dasax0s${NC}"
echo -e "${CYAN}  ══════════════════════════════════════${NC}"
echo ""

# ── detect distro ────────────────────────────────────────────────────────
if command -v apt-get &>/dev/null; then
    PKG_MGR="apt-get"
    INSTALL="apt-get install -y"
elif command -v dnf &>/dev/null; then
    PKG_MGR="dnf"
    INSTALL="dnf install -y"
elif command -v pacman &>/dev/null; then
    PKG_MGR="pacman"
    INSTALL="pacman -S --noconfirm"
else
    error "Unsupported package manager. Install dependencies manually."
fi

info "Detected package manager: $PKG_MGR"

# ── system update ────────────────────────────────────────────────────────
# ── system dependencies ──────────────────────────────────────────────────
PKGS_APT=(python3 python3-tk python3-pil aircrack-ng wifite hcxdumptool hcxtools hashcat iw wireless-tools net-tools)
PKGS_DNF=(python3 python3-tkinter aircrack-ng wifite hashcat iw wireless-tools net-tools)
PKGS_PAC=(python python-tk aircrack-ng wifite hcxdumptool hcxtools hashcat iw wireless_tools net-tools)

info "Installing system packages (this may take a few minutes)..."
case $PKG_MGR in
    apt-get)
        for pkg in "${PKGS_APT[@]}"; do
            info "  Installing $pkg..."
            apt-get install -y "$pkg" 2>/dev/null || warn "  Could not install $pkg — skipping"
        done
        ;;
    dnf)
        for pkg in "${PKGS_DNF[@]}"; do
            info "  Installing $pkg..."
            dnf install -y "$pkg" 2>/dev/null || warn "  Could not install $pkg — skipping"
        done
        ;;
    pacman)
        for pkg in "${PKGS_PAC[@]}"; do
            info "  Installing $pkg..."
            pacman -S --noconfirm "$pkg" 2>/dev/null || warn "  Could not install $pkg — skipping"
        done
        ;;
esac
success "Packages installed"

# ── wifite2 from source (latest) ─────────────────────────────────────────
if ! command -v wifite &>/dev/null; then
    info "wifite not found in repos. Installing from source..."
    if ! command -v git &>/dev/null; then
        $INSTALL git
    fi
    TMP=$(mktemp -d)
    git clone --depth=1 https://github.com/derv82/wifite2.git "$TMP/wifite2"
    cd "$TMP/wifite2"
    python3 setup.py install
    cd - > /dev/null
    rm -rf "$TMP"
fi

# ── install path ─────────────────────────────────────────────────────────
INSTALL_DIR="/opt/wifite-gui"
info "Installing Wifite GUI to $INSTALL_DIR..."
mkdir -p "$INSTALL_DIR"
cp "$(dirname "$0")/wifite_gui.py" "$INSTALL_DIR/wifite_gui.py"
chmod +x "$INSTALL_DIR/wifite_gui.py"

# ── launcher script ──────────────────────────────────────────────────────
cat > /usr/local/bin/wifite-gui << 'EOF'
#!/usr/bin/env bash
exec sudo python3 /opt/wifite-gui/wifite_gui.py "$@"
EOF
chmod +x /usr/local/bin/wifite-gui
success "Launcher created: /usr/local/bin/wifite-gui"

# ── desktop entry ────────────────────────────────────────────────────────
DESKTOP_DIR="/usr/share/applications"
cat > "$DESKTOP_DIR/wifite-gui.desktop" << EOF
[Desktop Entry]
Name=Wifite GUI
Comment=Graphical front-end for wifite — by dasax0s
Exec=sudo python3 /opt/wifite-gui/wifite_gui.py
Icon=network-wireless
Terminal=false
Type=Application
Categories=Network;Security;
Keywords=wifi;wpa;wps;audit;pentest;
EOF
success "Desktop entry created"

# ── verify installs ──────────────────────────────────────────────────────
echo ""
info "Verifying installation..."
declare -A TOOLS=(
    ["python3"]="Python 3"
    ["wifite"]="Wifite"
    ["airmon-ng"]="Airmon-ng"
    ["airodump-ng"]="Airodump-ng"
    ["hashcat"]="Hashcat"
)
ALL_OK=true
for cmd in "${!TOOLS[@]}"; do
    if command -v "$cmd" &>/dev/null; then
        success "${TOOLS[$cmd]} — OK ($(command -v "$cmd"))"
    else
        warn "${TOOLS[$cmd]} — NOT FOUND"
        ALL_OK=false
    fi
done

if command -v hcxdumptool &>/dev/null; then
    success "hcxdumptool — OK"
else
    warn "hcxdumptool — not found (PMKID attacks unavailable)"
fi

chmod +x smin.sh
sudo ./smin.sh



echo ""
if $ALL_OK; then
    success "Installation complete!"
else
    warn "Some tools missing. PMKID/WPS attacks may not work."
fi




echo ""
echo -e "${CYAN}  Run with:  wifite-gui${NC}"
echo -e "${CYAN}  Or:        sudo python3 /opt/wifite-gui/wifite_gui.py${NC}"
echo ""

