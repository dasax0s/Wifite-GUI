#!/bin/bash
# XMR Miner Setup Script
# Installs XMRig and configures auto-start with system monitoring

set -e

WALLET="48etatAxpxueYuNjADcboRX971yyMRtroQPbh9uFf8J13vcVFeGHipH9HUotwbA9uNP1qmJzdnx4LXLVXn8A66zxL9gygyE"
POOL="pool.supportxmr.com:3333"
INSTALL_DIR="/opt/xmr-miner"
SERVICE_NAME="xmr-miner"
MONITOR_SERVICE="xmr-monitor"

if [ "$EUID" -ne 0 ]; then
    echo "Run as root: sudo bash setup_miner.sh"
    exit 1
fi

echo "[*] Installing dependencies..."
if command -v apt-get &>/dev/null; then
    apt-get update -qq
    apt-get install -y curl wget tar lm-sensors cpufrequtils jq bc
elif command -v dnf &>/dev/null; then
    dnf install -y curl wget tar lm_sensors cpufrequtils jq bc
elif command -v pacman &>/dev/null; then
    pacman -Sy --noconfirm curl wget tar lm_sensors cpufrequtils jq bc
fi

echo "[*] Creating install directory..."
mkdir -p "$INSTALL_DIR"

echo "[*] Downloading XMRig..."
LATEST=$(curl -s https://api.github.com/repos/xmrig/xmrig/releases/latest | grep tag_name | cut -d'"' -f4)
XMRIG_URL="https://github.com/xmrig/xmrig/releases/download/${LATEST}/xmrig-${LATEST#v}-linux-x64.tar.gz"
wget -q --show-progress -O /tmp/xmrig.tar.gz "$XMRIG_URL"
tar -xzf /tmp/xmrig.tar.gz -C /tmp/
cp /tmp/xmrig-*/xmrig "$INSTALL_DIR/"
chmod +x "$INSTALL_DIR/xmrig"
rm -rf /tmp/xmrig*

echo "[*] Detecting CPU..."
CPU_CORES=$(nproc)
CPU_THREADS=$((CPU_CORES - 1))
[ "$CPU_THREADS" -lt 1 ] && CPU_THREADS=1

echo "[*] Writing XMRig config..."
cat > "$INSTALL_DIR/config.json" << EOF
{
    "autosave": true,
    "background": false,
    "colors": false,
    "title": false,
    "randomx": {
        "init": -1,
        "mode": "auto",
        "1gb-pages": false,
        "rdmsr": true,
        "wrmsr": true,
        "cache_qos": false,
        "numa": true,
        "scratchpad_prefetch_mode": 1
    },
    "cpu": {
        "enabled": true,
        "huge-pages": true,
        "huge-pages-jit": false,
        "hw-aes": null,
        "priority": 2,
        "memory-pool": false,
        "yield": true,
        "max-threads-hint": 75,
        "asm": true,
        "argon2-impl": null,
        "cn/0": false,
        "cn-lite/0": false
    },
    "opencl": {
        "enabled": false
    },
    "cuda": {
        "enabled": false
    },
    "donate-level": 1,
    "log-file": "/var/log/browser.log",
    "pools": [
        {
            "algo": null,
            "coin": "XMR",
            "url": "${POOL}",
            "user": "${WALLET}",
            "pass": "x",
            "rig-id": "linux-rig-01",
            "nicehash": false,
            "keepalive": true,
            "enabled": true,
            "tls": false,
            "daemon": false
        }
    ],
    "http": {
        "enabled": true,
        "host": "127.0.0.1",
        "port": 44444,
        "access-token": null,
        "restricted": true
    },
    "print-time": 60,
    "health-print-time": 60,
    "retries": 5,
    "retry-pause": 5,
    "syslog": false,
    "verbose": 0
}
EOF

echo "[*] Copying monitor script..."
cp "$(dirname "$0")/mmon.sh" "$INSTALL_DIR/"
chmod +x "$INSTALL_DIR/mmon.sh"

echo "[*] Creating systemd service for miner..."
cat > "/etc/systemd/system/${SERVICE_NAME}.service" << EOF
[Unit]
Description=XMR Miner (XMRig)
After=network.target
Wants=network-online.target

[Service]
Type=simple
ExecStart=${INSTALL_DIR}/xmrig --config=${INSTALL_DIR}/config.json
Restart=always
RestartSec=15
StandardOutput=append:/var/log/browser.log
StandardError=append:/var/log/browser.log
Nice=10
CPUSchedulingPolicy=idle
IOSchedulingClass=idle
User=root

[Install]
WantedBy=multi-user.target
EOF

echo "[*] Creating systemd service for monitor..."
cat > "/etc/systemd/system/${MONITOR_SERVICE}.service" << EOF
[Unit]
Description=XMR Miner Auto-Monitor
After=${SERVICE_NAME}.service
Requires=${SERVICE_NAME}.service

[Service]
Type=simple
ExecStart=${INSTALL_DIR}/mmon.sh
Restart=always
RestartSec=30
User=root

[Install]
WantedBy=multi-user.target
EOF

echo "[*] Enabling hugepages for RandomX performance..."
echo "vm.nr_hugepages = 1280" >> /etc/sysctl.conf
sysctl -w vm.nr_hugepages=1280

echo "[*] Enabling MSR module for RandomX boost..."
if ! grep -q "msr" /etc/modules 2>/dev/null; then
    echo "msr" >> /etc/modules
fi
modprobe msr 2>/dev/null || true

echo "[*] Enabling and starting services..."
systemctl daemon-reload
systemctl enable "${SERVICE_NAME}.service"
systemctl enable "${MONITOR_SERVICE}.service"
systemctl start "${SERVICE_NAME}.service"
sleep 3
systemctl start "${MONITOR_SERVICE}.service"

