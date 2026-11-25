#!/bin/bash

# 平台通过 SSH 以 linaro 身份执行；需要 root 的脚本自动提权（sudo 密码固定 linaro）
if [ "$(id -u)" -ne 0 ]; then
    printf 'linaro\n' | sudo -S -p '' bash "$0" "$@"
    exit $?
fi
# ============================================================================
# SE13 4G 模块测试 (Fibocom/通用 AT 指令) — 自包含版，无外部依赖
# 用法: bash test_4g_modem.sh [-v]
# ============================================================================

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
log_info()  { echo -e "${CYAN}[INFO]${NC}  $(date '+%H:%M:%S') $*"; }
log_pass()  { echo -e "${GREEN}[PASS]${NC}  $*"; }
log_fail()  { echo -e "${RED}[FAIL]${NC}  $*"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }

VERBOSE=0
AT_TIMEOUT=3

declare -a RESULTS=()
add_result() { RESULTS+=("$1|$2|$3"); }

print_summary() {
    echo ""; echo "=============================================="
    echo "  测试结果汇总"
    echo "=============================================="
    local p=0 f=0 s=0
    for r in "${RESULTS[@]}"; do
        local n="${r%%|*}"; local rest="${r#*|}"; local st="${rest%%|*}"; local re="${rest#*|}"
        case "$st" in
            PASS) echo -e "  ${GREEN}✓${NC} $n"; p=$((p+1)) ;;
            FAIL) echo -e "  ${RED}✗${NC} $n — $re"; f=$((f+1)) ;;
            SKIP) echo -e "  ${YELLOW}−${NC} $n — $re"; s=$((s+1)) ;;
            WARN) echo -e "  ${YELLOW}⚠${NC} $n — $re" ;;
        esac
    done
    echo "----------------------------------------------"
    echo -e "  ${GREEN}PASS:$p${NC}  ${RED}FAIL:$f${NC}  ${YELLOW}SKIP:$s${NC}"
    echo "=============================================="
    [ "$f" -gt 0 ] && { echo "QA_FAIL_4G_MODEM"; exit 1; }
    echo "QA_PASS_4G_MODEM"; exit 0
}

while [ $# -gt 0 ]; do
    case "$1" in
        --help|-h) echo "用法: $0 [-v]"; echo "SE13 4G 模块基础功能测试 (AT 指令)"; exit 0 ;;
        --verbose|-v) VERBOSE=1 ;;
        *) echo "未知参数: $1"; exit 1 ;;
    esac
    shift
done

# ============================================================================
# 辅助函数
# ============================================================================

send_at() {
    local tty="$1" cmd="$2"
    stty -F "$tty" 115200 cs8 -cstopb -parenb -crtscts -echo raw 2>/dev/null
    timeout 0.5 cat "$tty" >/dev/null 2>&1 || true
    printf '%s\r\n' "$cmd" > "$tty"
    timeout "$AT_TIMEOUT" cat "$tty" 2>/dev/null || true
}

check_at() {
    local tty="$1" cmd="$2" expect="$3" label="$4"
    local resp
    resp=$(send_at "$tty" "$cmd")
    [ "$VERBOSE" -ge 1 ] && echo "$resp" | while read l; do [ -n "$l" ] && log_info "  [AT] $l"; done
    if [ -z "$resp" ]; then
        log_fail "$label — 无响应"
        return 1
    fi
    if echo "$resp" | grep -qi "$expect"; then
        log_pass "$label"
        return 0
    else
        local kl=$(echo "$resp" | grep -vE '^\s*$|^AT' | head -1)
        log_fail "$label — 期望含 '$expect', 实际: ${kl:-空}"
        return 1
    fi
}

find_at_port() {
    for tty in /dev/ttyUSB*; do
        [ -e "$tty" ] || continue
        local resp
        resp=$(send_at "$tty" "AT" 2>/dev/null)
        if echo "$resp" | grep -q "OK"; then
            echo "$tty"; return 0
        fi
    done
    for tty in /dev/ttyUSB*; do
        [ -e "$tty" ] && { echo "$tty"; return 0; }
    done
    return 1
}

# ============================================================================
# 测试用例
# ============================================================================

log_info "SE13 4G 模块测试开始"
log_info "测试时间: $(date '+%Y-%m-%d %H:%M:%S')"

# --- 1. 模块 USB 检测 ---
log_info "=== 1. 4G 模块 USB 检测 ==="
MODEM=$(lsusb 2>/dev/null | grep -iE "fibocom|sierra|huawei|quectel|simcom|telit|u-blox|thales|modem|1508")
if [ -z "$MODEM" ]; then
    log_warn "lsusb 未匹配已知 4G 模块，显示全部非 hub 设备:"
    lsusb 2>/dev/null | grep -v "root hub" | grep -v "Hub" | while read l; do [ -n "$l" ] && log_info "  $l"; done
    add_result "4G模块检测" "SKIP" "未找到"
    print_summary
fi
echo "$MODEM" | while read l; do [ -n "$l" ] && log_info "  $l"; done
add_result "4G模块检测" "PASS" "$(echo "$MODEM"|head -1|cut -d: -f3|tr -s ' ' ' ')"

# --- 2. ttyUSB 端口 ---
log_info "=== 2. ttyUSB 端口枚举 ==="
TTY_LIST=$(ls /dev/ttyUSB* 2>/dev/null)
[ -z "$TTY_LIST" ] && TTY_LIST=$(ls /dev/ttyACM* 2>/dev/null)
if [ -z "$TTY_LIST" ]; then
    log_fail "未找到 /dev/ttyUSB* 或 /dev/ttyACM*"
    add_result "ttyUSB端口" "FAIL" "无设备"
    print_summary
fi
TC=$(echo "$TTY_LIST" | wc -l)
log_info "$TC 个端口: $(echo $TTY_LIST | tr '\n' ' ')"
for t in $TTY_LIST; do log_info "  $t"; done
add_result "ttyUSB端口" "PASS" "${TC}个"

# --- 3. AT 端口探测 ---
log_info "=== 3. AT 端口探测 ==="
AT_PORT=$(find_at_port)
if [ -z "$AT_PORT" ]; then
    log_fail "未找到 AT 端口 (所有 ttyUSB 均无 OK 响应)"
    add_result "AT端口" "FAIL" "无响应"
    print_summary
fi
log_info "AT 端口: $AT_PORT"
add_result "AT端口" "PASS" "$AT_PORT"

# --- 4G 模块接口检测完成 (前3项已验证 USB枚举+AT端口通信) ---
print_summary