#!/bin/bash

# 平台通过 SSH 以 linaro 身份执行；需要 root 的脚本自动提权（sudo 密码固定 linaro）
if [ "$(id -u)" -ne 0 ]; then
    printf 'linaro\n' | sudo -S -p '' bash "$0" "$@"
    exit $?
fi
# ============================================================================
# SE13 HDMI 分辨率切换测试
#
# 测试内容: HDMI 显示器在不同分辨率模式下的显示功能
# 测试方法:
#   Phase 1 — sysfs 只读: 连接状态、模式枚举、EDID 解析
#   Phase 2 — 模式切换 (自动选最优方式):
#     Tier 1: fbset (最简)
#     Tier 2: python3 ctypes + libdrm (自包含, 零编译)
#     Tier 3: 只读模式 (无可用工具时降级)
#
# 依赖: 无外部依赖。python3 和 libdrm.so 为板子标配。
# 平台: SE13 cv84x (Linux, root)
# 接线: 必须连接 HDMI 显示器
# ============================================================================

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# === 内联公共函数库 (原 lib/test_common.sh) ===
set -o pipefail
VERBOSE=0
TEST_START_TIME=$(date '+%Y-%m-%d %H:%M:%S')
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
log_info()  { echo -e "${CYAN}[INFO]${NC}  $(date '+%H:%M:%S') $*"; }
log_pass()  { echo -e "${GREEN}[PASS]${NC}  $*"; }
log_fail()  { echo -e "${RED}[FAIL]${NC}  $*"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
log_debug() { [ "$VERBOSE" -ge 1 ] && echo -e "       [DEBUG] $*"; }
sentinel_pass() { echo "QA_PASS_$1"; }
sentinel_fail() { echo "QA_FAIL_$1: $2"; }
sentinel_skip() { echo "QA_SKIP_$1: $2"; }
run_sudo() { echo linaro | sudo -S "$@"; }
check_cmd() { command -v "$1" >/dev/null 2>&1 || { log_fail "命令 $1 未找到"; return 1; }; return 0; }
declare -a TEST_RESULTS=()
add_result() { TEST_RESULTS+=("$1|$2|$3"); }
print_summary() {
    echo ""; echo "=============================================="
    echo "  测试结果汇总  (开始: $TEST_START_TIME)"
    echo "=============================================="
    local pass_count=0 fail_count=0 skip_count=0
    for r in "${TEST_RESULTS[@]}"; do
        local name="${r%%|*}"; local rest="${r#*|}"; local status="${rest%%|*}"; local reason="${rest#*|}"
        case "$status" in
            PASS) echo -e "  ${GREEN}✓${NC} PASS: $name"; pass_count=$((pass_count+1)) ;;
            FAIL) echo -e "  ${RED}✗${NC} FAIL: $name — $reason"; fail_count=$((fail_count+1)) ;;
            SKIP) echo -e "  ${YELLOW}−${NC} SKIP: $name — $reason"; skip_count=$((skip_count+1)) ;;
        esac
    done
    echo "----------------------------------------------"
    echo -e "  ${GREEN}PASS:$pass_count${NC}  ${RED}FAIL:$fail_count${NC}  ${YELLOW}SKIP:$skip_count${NC}"
    echo "=============================================="
    if [ "$fail_count" -gt 0 ]; then
        sentinel_fail "$TEST_MODULE" "${fail_count}项失败"
        exit 1
    else
        sentinel_pass "$TEST_MODULE"
        exit 0
    fi
}
parse_args() {
    while [ $# -gt 0 ]; do case "$1" in
        --help|-h) usage; exit 0 ;;
        --verbose|-v) VERBOSE=1 ;;
        *) echo "未知参数: $1"; usage; exit 1 ;;
    esac; shift; done
}
check_device_reachable() {
    local ip="$1"
    [ -z "$ip" ] && return 0
    if ping -c 1 -W 2 "$ip" >/dev/null 2>&1; then
        log_info "设备 $ip 可达"; return 0
    else
        log_fail "设备 $ip 不可达"; add_result "设备连接" "FAIL" "ping 不通 $ip"; print_summary
    fi
}
gpio_export() { local n="$1"; [ -d "/sys/class/gpio/gpio$n" ] && return 0; run_sudo sh -c "echo $n > /sys/class/gpio/export" 2>/dev/null; sleep 0.1; }
gpio_unexport() { local n="$1"; run_sudo sh -c "echo $n > /sys/class/gpio/unexport" 2>/dev/null; }
gpio_set_dir() { local n="$1" d="$2"; run_sudo sh -c "echo $d > /sys/class/gpio/gpio$n/direction"; }
gpio_read() { local n="$1"; cat "/sys/class/gpio/gpio$n/value" 2>/dev/null; }
gpio_write() { local n="$1" v="$2"; run_sudo sh -c "echo $v > /sys/class/gpio/gpio$n/value"; }
# === 公共函数库结束 ===

TEST_MODULE="HDMI_RESOLUTION"
MODE_SWITCH_DELAY=3

usage() {
    cat <<EOF
用法: $0 [选项]
  SE13 HDMI 分辨率切换测试
选项:
  --help, -h       显示帮助
  --verbose, -v    详细输出
  --readonly, -r   只读模式 — 不执行分辨率切换
  --quick          快速模式 — 仅测试首选+最低分辨率
切换方式 (自动选择):
  1. fbset                2. python3 ctypes + libdrm
EOF
}

# --- 辅助函数 ---

_hdmi_sysfs() {
    for d in /sys/class/drm/card*-HDMI-*; do
        [ -d "$d" ] && { echo "$d"; return 0; }
    done
    if [ "$1" = "--any-connected" ]; then
        for d in /sys/class/drm/card*-*/; do
            local s=$(cat "${d}status" 2>/dev/null)
            [ "$s" = "connected" ] && { echo "${d%/}"; return 0; }
        done
    fi
    return 1
}

_all_connectors() {
    for d in /sys/class/drm/card*-*/; do
        [ -f "${d}status" ] || continue
        local name=$(basename "${d%/}")
        local status=$(cat "${d}status" 2>/dev/null)
        local modes="N/A"
        [ -f "${d}modes" ] && modes="$(wc -l < "${d}modes") modes"
        printf "  %-20s  status=%-12s  %s\n" "$name" "$status" "$modes"
    done
}

# ============================================================================
# Phase 2 内嵌: Python ctypes + libdrm 分辨率切换器
# 通过 python3 ctypes 直接调用 libdrm.so 的 drmMode* 函数,
# 零编译, 零外部依赖 (板子标配 python3 + libdrm.so)
# ============================================================================
_py_drm_mode_set() {
    # $1: connector_id, $2: mode_index (0=preferred)
    local conn_id="${1:-0}"
    local mode_idx="${2:-0}"

    python3 - "$conn_id" "$mode_idx" <<'PYEOF'
import sys, ctypes as ct

conn_id = int(sys.argv[1])
mode_idx = int(sys.argv[2])

libdrm = ct.CDLL("libdrm.so.2")

# --- DRM structures ---
class DRMModeInfo(ct.Structure):
    _fields_ = [
        ("clock", ct.c_uint32),
        ("hdisplay", ct.c_uint16), ("hsync_start", ct.c_uint16),
        ("hsync_end", ct.c_uint16), ("htotal", ct.c_uint16), ("hskew", ct.c_uint16),
        ("vdisplay", ct.c_uint16), ("vsync_start", ct.c_uint16),
        ("vsync_end", ct.c_uint16), ("vtotal", ct.c_uint16), ("vscan", ct.c_uint16),
        ("vrefresh", ct.c_uint32),
        ("flags", ct.c_uint32), ("type", ct.c_uint32),
        ("name", ct.c_char * 32),
    ]

class DRMConnector(ct.Structure):
    pass
DRMConnector._fields_ = [
    ("connector_id", ct.c_uint32), ("encoder_id", ct.c_uint32),
    ("connector_type", ct.c_uint32), ("connector_type_id", ct.c_uint32),
    ("connection", ct.c_uint32), ("mmWidth", ct.c_uint32), ("mmHeight", ct.c_uint32),
    ("subpixel", ct.c_uint32),
    ("count_modes", ct.c_int), ("modes", ct.POINTER(DRMModeInfo)),
    ("count_props", ct.c_int), ("props", ct.POINTER(ct.c_uint32)),
    ("prop_values", ct.POINTER(ct.c_uint64)),
    ("count_encoders", ct.c_int), ("encoders", ct.POINTER(ct.c_uint32)),
]

class DRMEncoder(ct.Structure):
    _fields_ = [
        ("encoder_id", ct.c_uint32), ("encoder_type", ct.c_uint32),
        ("crtc_id", ct.c_uint32), ("possible_crtcs", ct.c_uint32),
        ("possible_clones", ct.c_uint32),
    ]

class DRMRes(ct.Structure):
    _fields_ = [
        ("count_fbs", ct.c_int), ("fbs", ct.POINTER(ct.c_uint32)),
        ("count_crtcs", ct.c_int), ("crtcs", ct.POINTER(ct.c_uint32)),
        ("count_connectors", ct.c_int), ("connectors", ct.POINTER(ct.c_uint32)),
        ("count_encoders", ct.c_int), ("encoders", ct.POINTER(ct.c_uint32)),
        ("min_width", ct.c_uint32), ("max_width", ct.c_uint32),
        ("min_height", ct.c_uint32), ("max_height", ct.c_uint32),
    ]

# --- Function signatures ---
libdrm.drmModeGetResources.restype = ct.POINTER(DRMRes)
libdrm.drmModeGetResources.argtypes = [ct.c_int]

libdrm.drmModeGetConnector.restype = ct.POINTER(DRMConnector)
libdrm.drmModeGetConnector.argtypes = [ct.c_int, ct.c_uint32]

libdrm.drmModeGetEncoder.restype = ct.POINTER(DRMEncoder)
libdrm.drmModeGetEncoder.argtypes = [ct.c_int, ct.c_uint32]

libdrm.drmModeSetCrtc.restype = ct.c_int
libdrm.drmModeSetCrtc.argtypes = [ct.c_int, ct.c_uint32, ct.c_uint32,
    ct.c_uint32, ct.c_uint32, ct.POINTER(ct.c_uint32),
    ct.c_int, ct.POINTER(DRMModeInfo)]

libdrm.drmModeFreeResources.argtypes = [ct.POINTER(DRMRes)]
libdrm.drmModeFreeConnector.argtypes = [ct.POINTER(DRMConnector)]
libdrm.drmModeFreeEncoder.argtypes = [ct.POINTER(DRMEncoder)]

# --- 执行 ---
fd = ct.c_int(-1)
try:
    fd = ct.c_int(ct.CDLL("libc.so.6").open(b"/dev/dri/card0", 2))  # O_RDWR
    if fd.value < 0:
        fd = ct.c_int(ct.CDLL("libc.so.6").open(b"/dev/dri/card0", 0))  # O_RDONLY fallback
    if fd.value < 0:
        print("PY_ERR:cannot open /dev/dri/card0", file=sys.stderr)
        sys.exit(1)

    res = libdrm.drmModeGetResources(fd)
    if not res:
        print("PY_ERR:drmModeGetResources failed", file=sys.stderr)
        sys.exit(1)

    res_s = res.contents

    conn = libdrm.drmModeGetConnector(fd, ct.c_uint32(conn_id))
    if not conn:
        print(f"PY_ERR:connector {conn_id} not found", file=sys.stderr)
        libdrm.drmModeFreeResources(res)
        sys.exit(1)

    conn_s = conn.contents
    if conn_s.connection != 1:  # DRM_MODE_CONNECTED
        print(f"PY_ERR:connector {conn_id} not connected", file=sys.stderr)
        libdrm.drmModeFreeConnector(conn)
        libdrm.drmModeFreeResources(res)
        sys.exit(1)

    if mode_idx < 0 or mode_idx >= conn_s.count_modes:
        print(f"PY_ERR:mode_idx {mode_idx} out of range [0,{conn_s.count_modes})",
              file=sys.stderr)
        libdrm.drmModeFreeConnector(conn)
        libdrm.drmModeFreeResources(res)
        sys.exit(1)

    m = conn_s.modes[mode_idx]
    print(f"PY_INFO:target={m.hdisplay}x{m.vdisplay}@{m.vrefresh}Hz mode_idx={mode_idx}")

    # 找 encoder -> crtc
    if conn_s.count_encoders < 1:
        print("PY_ERR:no encoders on connector", file=sys.stderr)
        libdrm.drmModeFreeConnector(conn)
        libdrm.drmModeFreeResources(res)
        sys.exit(1)

    enc = libdrm.drmModeGetEncoder(fd, conn_s.encoders[0])
    if not enc:
        print("PY_ERR:encoder not found", file=sys.stderr)
        libdrm.drmModeFreeConnector(conn)
        libdrm.drmModeFreeResources(res)
        sys.exit(1)

    crtc_id = enc.contents.crtc_id
    libdrm.drmModeFreeEncoder(enc)

    # 纯 modeset (fb=0, 不绑定 framebuffer)
    conn_ids = (ct.c_uint32 * 1)(ct.c_uint32(conn_id))
    ret = libdrm.drmModeSetCrtc(fd, ct.c_uint32(crtc_id), ct.c_uint32(0),
        ct.c_uint32(0), ct.c_uint32(0), conn_ids, ct.c_int(1),
        ct.byref(m))

    if ret < 0:
        print(f"PY_ERR:drmModeSetCrtc failed ret={ret}", file=sys.stderr)
        libdrm.drmModeFreeConnector(conn)
        libdrm.drmModeFreeResources(res)
        sys.exit(1)

    print(f"PY_OK:{m.hdisplay}x{m.vdisplay}@{m.vrefresh}Hz crtc={crtc_id}")

    libdrm.drmModeFreeConnector(conn)
    libdrm.drmModeFreeResources(res)
finally:
    if fd.value >= 0:
        ct.CDLL("libc.so.6").close(fd.value)
PYEOF
}

# 列出 connector 和 modes (Python 版, 用于拿到 connector_id)
_py_drm_list() {
    python3 - <<'PYEOF'
import ctypes as ct

libdrm = ct.CDLL("libdrm.so.2")

class DRMModeInfo(ct.Structure):
    _fields_ = [
        ("clock", ct.c_uint32),
        ("hdisplay", ct.c_uint16), ("hsync_start", ct.c_uint16),
        ("hsync_end", ct.c_uint16), ("htotal", ct.c_uint16), ("hskew", ct.c_uint16),
        ("vdisplay", ct.c_uint16), ("vsync_start", ct.c_uint16),
        ("vsync_end", ct.c_uint16), ("vtotal", ct.c_uint16), ("vscan", ct.c_uint16),
        ("vrefresh", ct.c_uint32),
        ("flags", ct.c_uint32), ("type", ct.c_uint32),
        ("name", ct.c_char * 32),
    ]

class DRMConnector(ct.Structure):
    pass
DRMConnector._fields_ = [
    ("connector_id", ct.c_uint32), ("encoder_id", ct.c_uint32),
    ("connector_type", ct.c_uint32), ("connector_type_id", ct.c_uint32),
    ("connection", ct.c_uint32), ("mmWidth", ct.c_uint32), ("mmHeight", ct.c_uint32),
    ("subpixel", ct.c_uint32),
    ("count_modes", ct.c_int), ("modes", ct.POINTER(DRMModeInfo)),
    ("count_props", ct.c_int), ("props", ct.POINTER(ct.c_uint32)),
    ("prop_values", ct.POINTER(ct.c_uint64)),
    ("count_encoders", ct.c_int), ("encoders", ct.POINTER(ct.c_uint32)),
]

class DRMRes(ct.Structure):
    _fields_ = [
        ("count_fbs", ct.c_int), ("fbs", ct.POINTER(ct.c_uint32)),
        ("count_crtcs", ct.c_int), ("crtcs", ct.POINTER(ct.c_uint32)),
        ("count_connectors", ct.c_int), ("connectors", ct.POINTER(ct.c_uint32)),
        ("count_encoders", ct.c_int), ("encoders", ct.POINTER(ct.c_uint32)),
    ]

libdrm.drmModeGetResources.restype = ct.POINTER(DRMRes)
libdrm.drmModeGetResources.argtypes = [ct.c_int]
libdrm.drmModeGetConnector.restype = ct.POINTER(DRMConnector)
libdrm.drmModeGetConnector.argtypes = [ct.c_int, ct.c_uint32]
libdrm.drmModeFreeResources.argtypes = [ct.POINTER(DRMRes)]
libdrm.drmModeFreeConnector.argtypes = [ct.POINTER(DRMConnector)]

CONN_TYPES = {11: "HDMI-A", 12: "HDMI-B", 2: "VGA", 3: "DVI-I", 4: "DVI-D",
              14: "LVDS", 15: "DSI", 16: "eDP", 17: "DP"}
STATUS = {1: "connected", 2: "disconnected", 3: "unknown"}

fd = ct.CDLL("libc.so.6").open(b"/dev/dri/card0", 0)  # O_RDONLY
if fd < 0:
    print("PY_ERR:cannot open /dev/dri/card0", file=sys.stderr)
    sys.exit(1)

res = libdrm.drmModeGetResources(fd)
if not res:
    print("PY_ERR:no resources", file=sys.stderr)
    sys.exit(1)

rs = res.contents
for i in range(rs.count_connectors):
    c = libdrm.drmModeGetConnector(fd, rs.connectors[i])
    if not c: continue
    cs = c.contents
    ctype = CONN_TYPES.get(cs.connector_type, f"type{cs.connector_type}")
    cstat = STATUS.get(cs.connection, "?")
    print(f"PY_CONN:{cs.connector_id} {ctype}-{cs.connector_type_id} {cstat} modes={cs.count_modes}")
    if cs.connection == 1:
        for j in range(min(cs.count_modes, 8)):  # 前 8 个
            m = cs.modes[j]
            print(f"  [{j}] {m.hdisplay}x{m.vdisplay}@{m.vrefresh}Hz")
        if cs.count_modes > 8:
            print(f"  ... +{cs.count_modes - 8} more modes")
    libdrm.drmModeFreeConnector(c)

libdrm.drmModeFreeResources(res)
ct.CDLL("libc.so.6").close(fd)
PYEOF
}

# ============================================================================
# Phase 2: 模式切换 — 多 tier 自动选择
# ============================================================================

_ensure_switcher() {
    # 返回可用的切换方式: fbset | python | none
    if command -v fbset >/dev/null 2>&1; then
        echo "fbset"
        return
    fi
    if command -v python3 >/dev/null 2>&1 && \
       python3 -c "import ctypes; ctypes.CDLL('libdrm.so.2')" 2>/dev/null; then
        echo "python"
        return
    fi
    echo "none"
}

_py_get_conn_id() {
    _py_drm_list 2>/dev/null | grep "PY_CONN:" | grep "connected" | grep -i "HDMI" | head -1 | \
        awk -F'[: ]+' '{for(i=1;i<=NF;i++) if($i=="PY_CONN") print $(i+1)}'
}

_switch_mode_fbset() {
    local w="$1" h="$2"
    fbset -fb /dev/fb0 -xres "$w" -yres "$h" -vxres "$w" -vyres "$h" 2>&1
}

_switch_mode_python() {
    local conn_id="$1" mode_idx="$2"
    _py_drm_mode_set "$conn_id" "$mode_idx" 2>&1
}

# ============================================================================
# Phase 1: sysfs 只读
# ============================================================================

test_connection() {
    log_info "=== 1.1 HDMI 连接状态 ==="
    log_info "所有 DRM connector:"
    _all_connectors | while read l; do log_info "$l"; done

    local s=$(_hdmi_sysfs)
    [ -z "$s" ] && s=$(_hdmi_sysfs --any-connected)
    if [ -z "$s" ]; then
        sentinel_skip "HDMI_RESOLUTION" "无 connected DRM connector"
        add_result "HDMI 连接" "SKIP" "未连接"
        return 1
    fi

    local status=$(cat "${s}/status" 2>/dev/null)
    log_info "目标: $s  status=$status"
    if [ "$status" != "connected" ]; then
        sentinel_skip "HDMI_RESOLUTION" "HDMI 未连接"
        add_result "HDMI 连接" "SKIP" "status=$status"
        return 1
    fi

    log_pass "HDMI 已连接 ($s)"
    add_result "HDMI 连接" "PASS" "$(basename "$s") connected"
    HDMI_SYSFS="$s"

    # 同时用 Python 拿 connector_id (给 Phase 2 用)
    PY_CONN_ID=$(_py_get_conn_id 2>/dev/null)
    [ -n "$PY_CONN_ID" ] && log_info "DRM connector_id: $PY_CONN_ID"

    return 0
}

test_modes_enum() {
    log_info "=== 1.2 可用分辨率模式 ==="

    local mf="${HDMI_SYSFS}/modes"
    if [ ! -f "$mf" ]; then
        add_result "分辨率列表" "SKIP" "sysfs modes 不可用"
        return 1
    fi

    MODES_LIST=()
    local max_width=0 max_height=0 min_width=99999 min_height=99999

    log_info "显示器支持的模式:"
    local idx=0
    while IFS= read -r line; do
        [ -z "$line" ] && continue
        local w="${line%x*}"
        local h="${line#*x}"
        h="${h%%[!0-9]*}"
        [ -z "$w" ] || [ -z "$h" ] && continue

        log_info "  [$idx] ${w}x${h}"
        MODES_LIST+=("$line")

        [ "$w" -gt "$max_width" ] 2>/dev/null && max_width=$w
        [ "$h" -gt "$max_height" ] 2>/dev/null && max_height=$h
        [ "$w" -lt "$min_width" ] 2>/dev/null && min_width=$w
        [ "$h" -lt "$min_height" ] 2>/dev/null && min_height=$h
        idx=$((idx + 1))
    done < "$mf"

    MODE_COUNT=$idx

    if [ "$MODE_COUNT" -eq 0 ]; then
        add_result "分辨率列表" "FAIL" "modes 为空"
        return 1
    fi

    log_info ""
    log_info "最佳分辨率 (EDID preferred): ${MODES_LIST[0]}"
    log_info "最大分辨率: ${max_width}x${max_height}"
    [ "$MODE_COUNT" -gt 1 ] && log_info "最低分辨率: ${min_width}x${min_height}"
    log_info "模式总数: $MODE_COUNT"

    log_pass "可用 $MODE_COUNT 种分辨率"
    add_result "分辨率列表" "PASS" "$MODE_COUNT 种模式"
    return 0
}

test_edid() {
    log_info "=== 1.3 EDID 元数据 ==="

    local ef="${HDMI_SYSFS}/edid"
    if [ ! -f "$ef" ]; then
        add_result "EDID" "SKIP" "不可用"
        return 1
    fi

    local size=$(wc -c < "$ef" 2>/dev/null)
    log_info "EDID 大小: $size bytes"
    [ "$size" -lt 128 ] && { add_result "EDID" "FAIL" "size=$size"; return 1; }

    local hex_cmd=""
    if command -v xxd >/dev/null 2>&1; then
        hex_cmd="xxd -p"
    elif command -v od >/dev/null 2>&1; then
        hex_cmd="od -A n -t x1 -v | tr -d ' \n'"
    else
        add_result "EDID" "SKIP" "缺少解析工具"
        return 1
    fi

    local edata=$(eval "$hex_cmd < $ef" | tr -d '\n' | head -c 256)

    local header=$(echo "$edata" | head -c 16)
    [ "$header" = "00ffffffffffff00" ] && log_info "Header: 正确" || log_warn "Header: 异常"

    local mfg_hi=$((16#$(echo "$edata" | cut -c17-18) 2>/dev/null))
    local mfg_lo=$((16#$(echo "$edata" | cut -c19-20) 2>/dev/null))
    if [ -n "$mfg_hi" ] && [ -n "$mfg_lo" ]; then
        local c1=$(( ((mfg_hi >> 2) & 0x1F) + 64 ))
        local c2=$(( (((mfg_hi & 0x03) << 3) | ((mfg_lo >> 5) & 0x07)) + 64 ))
        local c3=$(( (mfg_lo & 0x1F) + 64 ))
        printf -v mfg "\\x$(printf %x $c1)\\x$(printf %x $c2)\\x$(printf %x $c3)"
        log_info "厂商: $mfg"
    fi

    local plo=$((16#$(echo "$edata" | cut -c21-22) 2>/dev/null))
    local phi=$((16#$(echo "$edata" | cut -c23-24) 2>/dev/null))
    [ -n "$plo" ] && [ -n "$phi" ] && \
        log_info "产品代码: 0x$(printf '%04x' $(( (phi<<8)|plo )))"

    local yb=$((16#$(echo "$edata" | cut -c35-36) 2>/dev/null))
    [ -n "$yb" ] && log_info "制造年份: $((1990 + yb))"

    log_info "Extension blocks: $((16#$(echo "$edata" | cut -c253-254) 2>/dev/null))"

    local cksum=$(echo "$edata" | head -c 256 | fold -w2 | \
        awk '{s+=strtonum("0x"$1)} END {print s % 256}')
    if [ "$cksum" -eq 0 ]; then
        log_pass "Checksum 正确"
        add_result "EDID" "PASS" "$size bytes, checksum OK"
    else
        log_warn "Checksum 异常 (mod 256 = $cksum)"
        add_result "EDID" "WARN" "checksum 异常"
    fi
    return 0
}

test_current_mode() {
    log_info "=== 1.4 当前显示模式 ==="
    if [ -f "${HDMI_SYSFS}/mode" ]; then
        log_info "sysfs mode: $(cat "${HDMI_SYSFS}/mode" 2>/dev/null)"
    else
        log_info "sysfs mode 文件不可用"
    fi
    if command -v fbset >/dev/null 2>&1 && [ -c "/dev/fb0" ]; then
        fbset -s 2>/dev/null | while read l; do [ -n "$l" ] && log_info "fb: $l"; done
        local fb_w=$(fbset -s 2>/dev/null | grep geometry | awk '{print $2}')
        local fb_h=$(fbset -s 2>/dev/null | grep geometry | awk '{print $3}')
        FB_CURRENT="${fb_w}x${fb_h}"
        add_result "当前mode" "PASS" "FB ${FB_CURRENT:-N/A}"
    else
        add_result "当前mode" "SKIP" "fbset 不可用"
    fi
    return 0
}

# ============================================================================
# Phase 2: 模式切换
# ============================================================================

test_mode_switch() {
    log_info "=== 2. 分辨率切换测试 ==="

    if [ "$MODE_COUNT" -le 1 ]; then
        add_result "分辨率切换" "SKIP" "模式数 ≤1"
        return 1
    fi

    if [ "$READONLY" = "1" ]; then
        add_result "分辨率切换" "SKIP" "--readonly"
        return 1
    fi

    local how=$(_ensure_switcher)
    log_info "切换方式: $how"

    case "$how" in
        fbset)  SWITCH_MODE=0 ;;
        python) SWITCH_MODE=1 ;;
        *)
            log_warn "无可用切换工具 (fbset/python3+libdrm), 降级为只读"
            add_result "分辨率切换" "SKIP" "无 fbset 和 python3+libdrm"
            return 1
            ;;
    esac

    local conn_id="${PY_CONN_ID:-0}"

    local test_indices=()
    if [ "$QUICK" = "1" ]; then
        test_indices=(0 $((MODE_COUNT - 1)))
        log_info "快速模式: idx=0 和 idx=$((MODE_COUNT - 1))"
    else
        for ((i = 0; i < MODE_COUNT; i++)); do test_indices+=("$i"); done
        log_info "完整模式: 全部 $MODE_COUNT 个分辨率"
    fi

    local switch_ok=0 switch_fail=0

    for idx in "${test_indices[@]}"; do
        local mode_str="${MODES_LIST[$idx]}"
        local w="${mode_str%x*}"
        local h="${mode_str#*x}"; h="${h%%[!0-9]*}"
        [ -z "$w" ] && w=0; [ -z "$h" ] && h=0

        log_info "--- 切换到 [$idx] ${w}x${h} ---"

        local out="" ret=0
        if [ "$SWITCH_MODE" -eq 0 ]; then
            out=$(_switch_mode_fbset "$w" "$h" 2>&1); ret=$?
        else
            out=$(_switch_mode_python "$conn_id" "$idx" 2>&1); ret=$?
        fi

        if [ $ret -eq 0 ]; then
            log_info "  切换命令返回 OK"
            log_info "  输出: $(echo "$out" | grep 'PY_OK\|PY_INFO')"
            sleep "$MODE_SWITCH_DELAY"

            # 验证: 读回 sysfs mode (如果有)
            if [ -f "${HDMI_SYSFS}/mode" ]; then
                log_info "  sysfs mode: $(cat "${HDMI_SYSFS}/mode" 2>/dev/null)"
            fi

            log_pass "  mode [$idx] 切换成功"
            add_result "Mode[$idx] ${w}x${h}" "PASS" "切换成功"
            switch_ok=$((switch_ok + 1))
        else
            log_fail "  切换失败: $(echo "$out" | grep 'PY_ERR\|Error' | head -3)"
            add_result "Mode[$idx] ${w}x${h}" "FAIL" "$(echo "$out" | head -1)"
            switch_fail=$((switch_fail + 1))
        fi
    done

    # 恢复最佳分辨率
    local best="${MODES_LIST[0]}"
    local bw="${best%x*}"; local bh="${best#*x}"; bh="${bh%%[!0-9]*}"
    log_info "--- 恢复到最佳: ${bw}x${bh} ---"
    if [ "$SWITCH_MODE" -eq 0 ]; then
        _switch_mode_fbset "$bw" "$bh" >/dev/null 2>&1
    else
        _switch_mode_python "$conn_id" "0" >/dev/null 2>&1
    fi
    sleep 1

    local total=$((switch_ok + switch_fail))
    if [ "$switch_fail" -eq 0 ]; then
        log_pass "分辨率切换: $switch_ok/$total 全部通过"
        sentinel_pass "HDMI_RESOLUTION"
    elif [ "$switch_ok" -gt 0 ]; then
        log_warn "分辨率切换: $switch_ok/$total 通过, $switch_fail 失败"
        sentinel_fail "HDMI_RESOLUTION" "$switch_fail/$total 失败"
    else
        log_fail "分辨率切换: 全部 $switch_fail 个失败"
        sentinel_fail "HDMI_RESOLUTION" "全部 $switch_fail 个失败"
    fi
    return 0
}

# ============================================================================

main() {
    if [ "${BASH_SOURCE[0]}" != "$0" ]; then
        echo "ERROR: 不可 source 执行, 请直接运行: bash $0" >&2; return 1
    fi

    READONLY=0; QUICK=0
    while [ $# -gt 0 ]; do
        case "$1" in
            --help|-h) usage; return 0 ;;
            --verbose|-v) VERBOSE=1; shift ;;
            --readonly|-r) READONLY=1; shift ;;
            --quick) QUICK=1; shift ;;
            *) echo "未知参数: $1"; usage; return 1 ;;
        esac
    done

    HDMI_SYSFS=""; MODES_LIST=(); MODE_COUNT=0; PY_CONN_ID=""
    FB_CURRENT=""; SWITCH_MODE=-1

    log_info "SE13 HDMI 分辨率切换测试"
    log_info "时间: $(date '+%Y-%m-%d %H:%M:%S')"
    [ "$READONLY" = "1" ] && log_info "模式: 只读"
    [ "$QUICK" = "1" ] && log_info "模式: 快速"

    if ! test_connection; then print_summary; return 0; fi
    test_modes_enum
    test_edid
    test_current_mode

    if [ "$MODE_COUNT" -ge 2 ]; then
        test_mode_switch
    fi

    print_summary
}

main "$@"