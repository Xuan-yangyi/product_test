#!/bin/bash

# 平台通过 SSH 以 linaro 身份执行；需要 root 的脚本自动提权（sudo 密码固定 linaro）
if [ "$(id -u)" -ne 0 ]; then
    printf 'linaro\n' | sudo -S -p '' bash "$0" "$@"
    exit $?
fi
# ============================================================================
# SE13 硬件状态采集脚本 v2.1
# 用法: bash hw_status.sh [--json]
#   --json      输出 JSON 格式 (便于自动化解析)
#
# 采集项 (11项):
#   1. 存储-EMMC        — life_time + 容量
#   2. 存储-拓展硬盘    — NVMe SSD smart-log / sysfs 基本信息
#   3. 内存             — free -h
#   4. CPU 温度(节温)   — thermal_zone0/soc_thermal_0
#   5. 板卡温度(环温)   — thermal_zone1 或 bm-sophon board_temp
#   6. CPU 使用率       — top -bn1 + loadavg
#   7. NPU 温度         — bm-sophon chip_temp / bm-smi (bmtpu 平台无此接口)
#   8. NPU 占用率       — bmtpu sysfs / bm-sophon sysfs npu_usage (自动适配)
#   9. TPU 功耗/频率    — bm-sophon tpu_power/tpu_freq (bmtpu 平台无此接口)
#  10. ION 内存占用     — debugfs cvi_npu_heap / bm_npu_heap (自动适配)
#  11. 加热电阻温度     — hwmon/i2c 自动扫描 (无传感器则列出 i2c 设备)
#
# 依赖: bmtpu.ko 或 soph_base.ko/soph_sys.ko/bm-sophon 驱动
# 平台: SE13 CV84X6 (bmtpu) / SE9 bm1688 (bm-sophon)
# ============================================================================
set -e

OUTPUT_MODE="text"

usage() {
    echo "用法: $0 [--json]"
    echo "  SE13 硬件状态一键采集"
    echo "  --json  输出 JSON 格式"
    exit 0
}
while [ $# -gt 0 ]; do
    case "$1" in
        --json) OUTPUT_MODE="json"; shift ;;
        -h|--help) usage ;;
    esac
done

# ============================================================================
LOGDIR="/tmp/se13_hw_status_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$LOGDIR"
RESULT="$LOGDIR/result.txt"

PASS=0; WARN=0; FAIL=0; SKIP=0; TOTAL=0
declare -A STATUS_MAP

_pass()  { PASS=$((PASS+1)); STATUS_MAP["$1"]="PASS"; }
_warn()  { WARN=$((WARN+1)); STATUS_MAP["$1"]="WARN"; }
_fail()  { FAIL=$((FAIL+1)); STATUS_MAP["$1"]="FAIL"; }
_skip()  { SKIP=$((SKIP+1)); STATUS_MAP["$1"]="SKIP"; }
_total() { TOTAL=$((TOTAL+1)); }

banner() {
    echo "============================================" | tee -a "$RESULT"
    echo "  SE13 硬件状态采集"                         | tee -a "$RESULT"
    echo "  时间: $(date '+%Y-%m-%d %H:%M:%S')"       | tee -a "$RESULT"
    echo "  日志: $RESULT"                             | tee -a "$RESULT"
    echo "============================================" | tee -a "$RESULT"
}

section() { echo "" | tee -a "$RESULT"; echo "--- $1 ---" | tee -a "$RESULT"; }

qa() {
    local id="$1"; local desc="$2"; local val="$3"; local expect="$4"
    _total
    if [ "$val" = "N/A" ] || [ -z "$val" ]; then
        echo "  [SKIP] $desc: 不可用" | tee -a "$RESULT"
        _skip "$id"
    elif [ -n "$expect" ]; then
        echo "  $desc: $val (预期 $expect)" | tee -a "$RESULT"
        _pass "$id"
    else
        echo "  $desc: $val" | tee -a "$RESULT"
        _pass "$id"
    fi
}

# ============================================================================
# 自动发现 bm-sophon 路径
# ============================================================================
BM_CARD=$(ls /proc/bmsophon/ 2>/dev/null | grep -v -E 'driver_version|card_num|chip_num' | head -1)
BM_CHIP=$(ls /proc/bmsophon/$BM_CARD/ 2>/dev/null | grep -v -E 'board_|fan_|sn|board_type|board_version|versions|pcb_version|bom_version|mcu_version|mode|chip_num|tpu_minclk|tpu_maxclk|maxboardp|driver_version' | head -1)
BMSOPHON_SYSFS="/sys/class/bm-sophon/bm-sophon0/device"

banner

# ========================================================================
# 1. 存储-EMMC
# ========================================================================
section "1. 存储-EMMC"
_total

if [ -e /dev/mmcblk0 ]; then
    LIFE=$(cat /sys/block/mmcblk0/device/life_time 2>/dev/null || echo "N/A")
    EMMC_SIZE=$(df -h /dev/mmcblk0p5 2>/dev/null | awk 'NR>1{print $2}' || echo "N/A")
    EMMC_DATA=$(df -h /dev/mmcblk0p6 2>/dev/null | awk 'NR>1{print $2}' || echo "N/A")

    echo "  device:     /dev/mmcblk0" | tee -a "$RESULT"
    echo "  life_time:  $LIFE" | tee -a "$RESULT"
    echo "  p5 (system): ${EMMC_SIZE:-N/A}" | tee -a "$RESULT"
    echo "  p6 (data):   ${EMMC_DATA:-N/A}" | tee -a "$RESULT"

    if [ "$LIFE" = "0x01 0x01" ] || echo "$LIFE" | grep -q "0x01"; then
        _pass "emmc"
    elif [ "$LIFE" != "N/A" ]; then
        _warn "emmc"
        echo "  ⚠️  eMMC life_time 异常: $LIFE" | tee -a "$RESULT"
    else
        _skip "emmc"
    fi
else
    echo "  未检测到 eMMC" | tee -a "$RESULT"
    _fail "emmc"
fi

# ========================================================================
# 2. 存储-拓展硬盘 (NVMe SSD)
# ========================================================================
section "2. 存储-拓展硬盘"
_total

if [ -e /dev/nvme0 ]; then
    echo "  device:     /dev/nvme0" | tee -a "$RESULT"

    if command -v nvme &>/dev/null; then
        SMART=$(nvme smart-log /dev/nvme0 2>/dev/null)
        CRIT_WARN=$(echo "$SMART" | grep critical_warning | awk '{print $NF}')
        SSD_TEMP=$(echo "$SMART" | grep '^temperature' | awk '{print $NF}')
        PCT_USED=$(echo "$SMART" | grep percentage_used | awk '{print $NF}')

        echo "  critical_warning: $CRIT_WARN" | tee -a "$RESULT"
        echo "  temperature:      ${SSD_TEMP}°C" | tee -a "$RESULT"
        echo "  percentage_used:  ${PCT_USED}%" | tee -a "$RESULT"

        if [ "$CRIT_WARN" = "0" ]; then
            _pass "nvme_ssd"
        else
            _warn "nvme_ssd"
            echo "  ⚠️  critical_warning=$CRIT_WARN" | tee -a "$RESULT"
        fi
    else
        # nvme 命令不可用, 从 sysfs 读取 SSD 基本信息
        NVME_MODEL=$(cat /sys/block/nvme0n1/device/model 2>/dev/null | xargs || echo "N/A")
        NVME_SERIAL=$(cat /sys/block/nvme0n1/device/serial 2>/dev/null | xargs || echo "N/A")
        NVME_FW=$(cat /sys/block/nvme0n1/device/firmware_rev 2>/dev/null | xargs || echo "N/A")
        NVME_SIZE=$(lsblk -o SIZE -n /dev/nvme0n1 2>/dev/null | head -1 || echo "N/A")

        echo "  model:    $NVME_MODEL" | tee -a "$RESULT"
        echo "  serial:   $NVME_SERIAL" | tee -a "$RESULT"
        echo "  firmware: $NVME_FW" | tee -a "$RESULT"
        echo "  容量:     $NVME_SIZE" | tee -a "$RESULT"
        echo "  (nvme 命令不可用, 以上信息来自 sysfs)" | tee -a "$RESULT"
        _pass "nvme_ssd"
    fi
else
    echo "  未检测到 NVMe SSD" | tee -a "$RESULT"
    _skip "nvme_ssd"
fi

# ========================================================================
# 3. 内存
# ========================================================================
section "3. 内存"
_total

MEM_TOTAL=$(free -h | awk '/^Mem:/{print $2}')
MEM_USED=$(free -h | awk '/^Mem:/{print $3}')
MEM_AVAIL=$(free -h | awk '/^Mem:/{print $7}')
SWAP_TOTAL=$(free -h | awk '/^Swap:/{print $2}')
SWAP_USED=$(free -h | awk '/^Swap:/{print $3}')

echo "  MemTotal:   $MEM_TOTAL" | tee -a "$RESULT"
echo "  MemUsed:    $MEM_USED" | tee -a "$RESULT"
echo "  MemAvail:   $MEM_AVAIL" | tee -a "$RESULT"
echo "  SwapTotal:  ${SWAP_TOTAL:-0}" | tee -a "$RESULT"
echo "  SwapUsed:   ${SWAP_USED:-0}" | tee -a "$RESULT"

# 合理性检查: total 应在 2~4G 范围
MEM_TOTAL_MB=$(free -m | awk '/^Mem:/{print $2}')
if [ "$MEM_TOTAL_MB" -ge 2000 ] && [ "$MEM_TOTAL_MB" -le 4096 ]; then
    _pass "memory"
else
    _warn "memory"
    echo "  ⚠️  内存总量 ${MEM_TOTAL_MB}MB 不在预期 2~4GB 范围" | tee -a "$RESULT"
fi

# ========================================================================
# 4. CPU 温度 (节温) — thermal_zone0 = soc_thermal_0
# ========================================================================
section "4. CPU 温度 (节温)"
_total

TZ_COUNT=0
for tz in /sys/class/thermal/thermal_zone*; do
    TZ_TYPE=$(cat $tz/type 2>/dev/null || echo "unknown")
    TZ_TEMP=$(cat $tz/temp 2>/dev/null || echo "N/A")
    TZ_TEMP_C=$(awk "BEGIN {printf \"%.1f\", $TZ_TEMP/1000}" 2>/dev/null || echo "N/A")

    echo "  $TZ_TYPE: ${TZ_TEMP_C}°C (${TZ_TEMP} m°C)" | tee -a "$RESULT"
    TZ_COUNT=$((TZ_COUNT + 1))

    # 区分节温(soc_thermal_0)和环温(soc_thermal_1)
    if echo "$TZ_TYPE" | grep -q "soc_thermal_0"; then
        JUNC_TEMP=$TZ_TEMP
        if [ "$TZ_TEMP" -lt 125000 ] 2>/dev/null; then
            _pass "cpu_junc_temp"
        else
            _fail "cpu_junc_temp"
            echo "  ❌ 芯片结温超过 125°C critical trip!" | tee -a "$RESULT"
        fi
    fi
done

if [ $TZ_COUNT -eq 0 ]; then
    echo "  无 thermal zone" | tee -a "$RESULT"
    _fail "cpu_junc_temp"
fi

# ========================================================================
# 5. 板卡温度 (环温)
# ========================================================================
section "5. 板卡温度 (环温)"
_total

BOARD_TEMP_FOUND=0

# 方式1: thermal_zone1 (soc_thermal_1)
if [ -f /sys/class/thermal/thermal_zone1/temp ]; then
    AMB_TEMP=$(cat /sys/class/thermal/thermal_zone1/temp 2>/dev/null)
    AMB_TEMP_C=$(awk "BEGIN {printf \"%.1f\", $AMB_TEMP/1000}" 2>/dev/null)
    echo "  thermal_zone1: ${AMB_TEMP_C}°C" | tee -a "$RESULT"
    BOARD_TEMP_FOUND=1
fi

# 方式2: bm-sophon board_temp
if [ -n "$BM_CARD" ] && [ -f "/proc/bmsophon/$BM_CARD/board_temp" ]; then
    BM_BOARD_TEMP=$(cat /proc/bmsophon/$BM_CARD/board_temp 2>/dev/null)
    echo "  bm-sophon board_temp: ${BM_BOARD_TEMP}" | tee -a "$RESULT"
    BOARD_TEMP_FOUND=1
fi

if [ $BOARD_TEMP_FOUND -eq 1 ]; then
    _pass "board_temp"
else
    echo "  板卡温度不可用" | tee -a "$RESULT"
    _skip "board_temp"
fi

# ========================================================================
# 6. CPU 使用率
# ========================================================================
section "6. CPU 使用率"
_total

CPU_LINE=$(top -bn1 | grep -E "CPU:|%Cpu" | head -1)
LOADAVG=$(cat /proc/loadavg 2>/dev/null)
echo "  $CPU_LINE" | tee -a "$RESULT"
echo "  loadavg: $LOADAVG" | tee -a "$RESULT"

IDLE_PCT=$(echo "$CPU_LINE" | grep -oP '\d+\.?\d*\s*(?:%?\s*idle| id,)' | grep -oP '\d+\.?\d*' || echo "0")
if [ -n "$IDLE_PCT" ]; then
    # idle 低于 5% → WARN (可能正在压测)
    IDLE_INT=$(awk "BEGIN {printf \"%.0f\", $IDLE_PCT}" 2>/dev/null || echo "100")
    if [ "$IDLE_INT" -ge 5 ]; then
        _pass "cpu_usage"
    else
        _warn "cpu_usage"
        echo "  ⚠️  CPU idle 仅 ${IDLE_PCT}%, 可能处于高负载 (压测/业务运行中)" | tee -a "$RESULT"
    fi
else
    _pass "cpu_usage"
fi

# ========================================================================
# 7. NPU 温度
# ========================================================================
section "7. NPU 温度 (chip_temp)"
_total

# 方式1: bm-sophon procfs (bm1688 系列)
if [ -n "$BM_CARD" ] && [ -n "$BM_CHIP" ] && \
   [ -f "/proc/bmsophon/$BM_CARD/$BM_CHIP/chip_temp" ]; then
    CHIP_TEMP=$(cat /proc/bmsophon/$BM_CARD/$BM_CHIP/chip_temp 2>/dev/null)
    echo "  bm-sophon chip_temp: ${CHIP_TEMP}" | tee -a "$RESULT"
    _pass "npu_temp"
# 方式2: bm-smi 命令行工具
elif command -v bm-smi &>/dev/null; then
    bm-smi 2>/dev/null | grep -i temp | head -2 | tee -a "$RESULT"
    _pass "npu_temp"
# 方式3: bmtpu (CV84X6/CV186) — 无温度接口，NPU 温度通过 soc_thermal 间接反映
elif lsmod | grep -q bmtpu; then
    echo "  bmtpu 驱动已加载, 但当前平台无独立 NPU 温度接口" | tee -a "$RESULT"
    echo "  NPU 温度可通过 CPU 节温 (soc_thermal_0) 间接反映" | tee -a "$RESULT"
    _skip "npu_temp"
else
    echo "  bm-sophon/bmtpu 驱动均未加载" | tee -a "$RESULT"
    _skip "npu_temp"
fi

# ========================================================================
# 8. NPU 占用率
# ========================================================================
section "8. NPU 占用率"
_total

# 自动发现 bmtpu 路径 (CV84X6/CV186 系列) 或 bm-sophon 路径
NPU_USAGE_PATH=""
if [ -f "$BMSOPHON_SYSFS/npu_usage" ]; then
    NPU_USAGE_PATH="$BMSOPHON_SYSFS/npu_usage"
elif [ -f /sys/devices/platform/20000000.bmtpu/npu_usage ]; then
    NPU_USAGE_PATH="/sys/devices/platform/20000000.bmtpu/npu_usage"
elif [ -f /sys/devices/platform/2000000.bmtpu/npu_usage ]; then
    NPU_USAGE_PATH="/sys/devices/platform/2000000.bmtpu/npu_usage"
fi

if [ -n "$NPU_USAGE_PATH" ]; then
    # 使能 npu_usage (如果存在 enable 接口)
    NPU_ENABLE="${NPU_USAGE_PATH%/*}/npu_usage_enable"
    if [ -f "$NPU_ENABLE" ]; then
        echo 1 > "$NPU_ENABLE" 2>/dev/null || true
    fi

    NPU_USAGE=$(cat "$NPU_USAGE_PATH" 2>/dev/null)
    echo "  path:  $NPU_USAGE_PATH" | tee -a "$RESULT"
    echo "$NPU_USAGE" | sed 's/^/  /' | tee -a "$RESULT"
    _pass "npu_usage"
else
    echo "  npu_usage sysfs 不可用" | tee -a "$RESULT"
    _skip "npu_usage"
fi

# ========================================================================
# 9. TPU 功耗 / 频率
# ========================================================================
section "9. TPU 功耗 / 频率"
_total

if [ -n "$BM_CARD" ] && [ -n "$BM_CHIP" ]; then
    # bm-sophon procfs 路径 (bm1688 系列)
    TPU_POWER=$(cat /proc/bmsophon/$BM_CARD/$BM_CHIP/tpu_power 2>/dev/null || echo "N/A")
    TPU_FREQ=$(cat /proc/bmsophon/$BM_CARD/$BM_CHIP/tpu_freq 2>/dev/null || echo "N/A")
    BOARD_POWER=$(cat /proc/bmsophon/$BM_CARD/board_power 2>/dev/null || echo "N/A")

    echo "  tpu_power:   ${TPU_POWER} W" | tee -a "$RESULT"
    echo "  board_power: ${BOARD_POWER}" | tee -a "$RESULT"
    echo "  tpu_freq:    ${TPU_FREQ} MHz" | tee -a "$RESULT"

    if [ "$TPU_POWER" != "N/A" ]; then
        _pass "tpu_power"
    else
        _skip "tpu_power"
    fi
elif lsmod | grep -q bmtpu; then
    echo "  bmtpu 驱动已加载, 但当前平台无独立 TPU 功耗/频率接口" | tee -a "$RESULT"
    echo "  可用 sysfs: 仅 runtime PM 状态 (power/runtime_status)" | tee -a "$RESULT"
    _skip "tpu_power"
else
    echo "  驱动未加载" | tee -a "$RESULT"
    _skip "tpu_power"
fi

# ========================================================================
# 10. ION 内存占用
# ========================================================================
section "10. ION 内存占用"
_total

ION_FOUND=0
for path in \
    /sys/kernel/debug/ion/cvi_npu_heap_dump/summary \
    /sys/kernel/debug/ion/bm_npu_heap_dump/summary \
    /sys/kernel/debug/ion/bm_npu_heap/total; do
    if [ -f "$path" ]; then
        echo "  $path:" | tee -a "$RESULT"
        head -5 "$path" 2>/dev/null | sed 's/^/    /' | tee -a "$RESULT"
        ION_FOUND=1
        break
    fi
done

if [ $ION_FOUND -eq 1 ]; then
    _pass "ion"
else
    echo "  debugfs 未挂载? mount -t debugfs none /sys/kernel/debug" | tee -a "$RESULT"
    _skip "ion"
fi

# ========================================================================
# 11. 加热电阻温度
# ========================================================================
section "11. 加热电阻温度"
_total

HEATER_FOUND=0
for pattern in \
    /sys/class/hwmon/hwmon*/temp*_input \
    /sys/bus/i2c/devices/*/hwmon/hwmon*/temp*_input; do
    for f in $pattern; do
        if [ -f "$f" ]; then
            LABEL=$(cat "$(dirname $f)/temp${f##*temp}_label" 2>/dev/null || echo "sensor")
            HEATER_TEMP=$(cat "$f" 2>/dev/null)
            HEATER_C=$(awk "BEGIN {printf \"%.1f\", $HEATER_TEMP/1000}" 2>/dev/null || echo "$HEATER_TEMP")
            echo "  $LABEL ($f): ${HEATER_C}°C" | tee -a "$RESULT"
            HEATER_FOUND=$((HEATER_FOUND + 1))
        fi
    done
done

# Also check bm-sophon procfs
for hf in /proc/bmsophon/*/heater_temp; do
    if [ -f "$hf" ]; then
        HT=$(cat "$hf" 2>/dev/null)
        echo "  $hf: $HT" | tee -a "$RESULT"
        HEATER_FOUND=$((HEATER_FOUND + 1))
    fi
done

if [ $HEATER_FOUND -gt 0 ]; then
    _pass "heater"
else
    echo "  未找到加热电阻温度接口" | tee -a "$RESULT"
    echo "  已扫描: /sys/class/hwmon/ /sys/bus/i2c/devices/*/hwmon/" | tee -a "$RESULT"
    echo "  i2c 设备信息:" | tee -a "$RESULT"
    for dev in /sys/bus/i2c/devices/[0-9]*-[0-9a-f]*; do
        [ -d "$dev" ] || continue
        DEVNAME=$(cat "$dev/name" 2>/dev/null || echo "?")
        echo "    $(basename $dev): $DEVNAME" | tee -a "$RESULT"
    done
    _skip "heater"
fi

# ========================================================================
# 结果汇总
# ========================================================================
echo "" | tee -a "$RESULT"
echo "============================================" | tee -a "$RESULT"
echo "  采集结果汇总" | tee -a "$RESULT"
echo "  总计: $TOTAL 项" | tee -a "$RESULT"
echo "  PASS: $PASS  |  WARN: $WARN  |  FAIL: $FAIL  |  SKIP: $SKIP" | tee -a "$RESULT"
echo "============================================" | tee -a "$RESULT"

if [ "$OUTPUT_MODE" = "json" ]; then
    echo ""
    echo "{"
    echo "  \"timestamp\": \"$(date -Iseconds)\","
    echo "  \"total\": $TOTAL,"
    echo "  \"pass\": $PASS,"
    echo "  \"warn\": $WARN,"
    echo "  \"fail\": $FAIL,"
    echo "  \"skip\": $SKIP"
    echo "}"
fi

if [ $FAIL -gt 0 ]; then
    echo "" | tee -a "$RESULT"
    echo "  ⚠️  QA_FAIL_HW_STATUS ($FAIL 项 FAIL)" | tee -a "$RESULT"
    exit 1
else
    echo "" | tee -a "$RESULT"
    echo "  ✅ QA_PASS_HW_STATUS" | tee -a "$RESULT"
    exit 0
fi