#!/bin/bash
# XMR Miner Auto-Monitor
# Watches CPU temp, load, and adjusts mining intensity via XMRig HTTP API

XMRIG_API="http://127.0.0.1:44444"
LOG="/var/log/xmr-monitor.log"
CHECK_INTERVAL=30

TEMP_MAX=80       # Stop reducing threads above this (°C)
TEMP_HIGH=75      # Reduce threads above this (°C)
TEMP_OK=65        # Full speed below this (°C)

LOAD_HIGH=0.90    # Reduce if system load per-core exceeds this
LOAD_OK=0.70      # Restore threads if load drops below this

CPU_CORES=$(nproc)
CPU_THREADS_MAX=$((CPU_CORES - 1))
[ "$CPU_THREADS_MAX" -lt 1 ] && CPU_THREADS_MAX=1
CPU_THREADS_MIN=1

current_threads=$CPU_THREADS_MAX

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG"
}

get_cpu_temp() {
    local temp=0

    # Try sensors (lm-sensors)
    if command -v sensors &>/dev/null; then
        temp=$(sensors 2>/dev/null | grep -E "Core 0|Tctl|CPU Temp|Package id" \
            | head -1 | grep -oP '\+\K[0-9]+' | head -1)
    fi

    # Fallback: read thermal zone
    if [ -z "$temp" ] || [ "$temp" -eq 0 ]; then
        for zone in /sys/class/thermal/thermal_zone*/temp; do
            local t
            t=$(cat "$zone" 2>/dev/null)
            t=$((t / 1000))
            [ "$t" -gt "$temp" ] && temp=$t
        done
    fi

    echo "${temp:-50}"
}

get_load_ratio() {
    local load1
    load1=$(awk '{print $1}' /proc/loadavg)
    echo "scale=2; $load1 / $CPU_CORES" | bc
}

get_miner_hashrate() {
    curl -s --max-time 3 "${XMRIG_API}/2/summary" 2>/dev/null \
        | python3 -c "import sys,json; d=json.load(sys.stdin); print(round(d['hashrate']['total'][0]/1000,2))" 2>/dev/null \
        || echo "0"
}

set_threads() {
    local n=$1
    [ "$n" -lt "$CPU_THREADS_MIN" ] && n=$CPU_THREADS_MIN
    [ "$n" -gt "$CPU_THREADS_MAX" ] && n=$CPU_THREADS_MAX
    [ "$n" -eq "$current_threads" ] && return

    log "Adjusting threads: ${current_threads} -> ${n}"
    curl -s --max-time 3 -X POST "${XMRIG_API}/2/config" \
        -H "Content-Type: application/json" \
        -d "{\"cpu\":{\"max-threads-hint\":$((n * 100 / CPU_CORES))}}" \
        > /dev/null 2>&1
    current_threads=$n
}

log "Monitor started. CPU cores: ${CPU_CORES}, max threads: ${CPU_THREADS_MAX}"

# Wait for XMRig API to be ready
for i in $(seq 1 20); do
    if curl -s --max-time 2 "${XMRIG_API}/2/summary" > /dev/null 2>&1; then
        log "XMRig API is ready."
        break
    fi
    sleep 3
done

while true; do
    TEMP=$(get_cpu_temp)
    LOAD=$(get_load_ratio)
    HASH=$(get_miner_hashrate)

    log "Temp: ${TEMP}°C | Load/core: ${LOAD} | Hashrate: ${HASH} kH/s | Threads: ${current_threads}/${CPU_THREADS_MAX}"

    # Temperature-based throttling
    if [ "$TEMP" -ge "$TEMP_MAX" ]; then
        NEW_THREADS=$((current_threads - 2))
        [ "$NEW_THREADS" -lt "$CPU_THREADS_MIN" ] && NEW_THREADS=$CPU_THREADS_MIN
        log "CRITICAL TEMP ${TEMP}°C — reducing to ${NEW_THREADS} threads"
        set_threads "$NEW_THREADS"

    elif [ "$TEMP" -ge "$TEMP_HIGH" ]; then
        NEW_THREADS=$((current_threads - 1))
        log "HIGH TEMP ${TEMP}°C — reducing to ${NEW_THREADS} threads"
        set_threads "$NEW_THREADS"

    elif [ "$TEMP" -lt "$TEMP_OK" ]; then
        # Load-based check before restoring threads
        LOAD_INT=$(echo "$LOAD * 100" | bc | cut -d. -f1)
        LOAD_OK_INT=$(echo "$LOAD_OK * 100" | bc | cut -d. -f1)
        LOAD_HIGH_INT=$(echo "$LOAD_HIGH * 100" | bc | cut -d. -f1)

        if [ "$LOAD_INT" -gt "$LOAD_HIGH_INT" ]; then
            NEW_THREADS=$((current_threads - 1))
            log "HIGH LOAD ${LOAD} — reducing to ${NEW_THREADS} threads"
            set_threads "$NEW_THREADS"

        elif [ "$LOAD_INT" -lt "$LOAD_OK_INT" ] && [ "$current_threads" -lt "$CPU_THREADS_MAX" ]; then
            NEW_THREADS=$((current_threads + 1))
            log "Temp/load OK — restoring to ${NEW_THREADS} threads"
            set_threads "$NEW_THREADS"
        fi
    fi

    sleep "$CHECK_INTERVAL"
done
