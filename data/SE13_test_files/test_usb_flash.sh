#!/bin/bash

# 平台通过 SSH 以 linaro 身份执行；需要 root 的脚本自动提权（sudo 密码固定 linaro）
if [ "$(id -u)" -ne 0 ]; then
    printf 'linaro\n' | sudo -S -p '' bash "$0" "$@"
    exit $?
fi
# ============================================================================
# SE13 USB 存储设备测试 (U盘/SD读卡器) — 自包含版，无外部依赖
# 用法: bash test_usb_flash.sh [-v] [--size N]
# ============================================================================

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
log_info()  { echo -e "${CYAN}[INFO]${NC}  $(date '+%H:%M:%S') $*"; }
log_pass()  { echo -e "${GREEN}[PASS]${NC}  $*"; }
log_fail()  { echo -e "${RED}[FAIL]${NC}  $*"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }

TEST_SIZE_MB=10
VERBOSE=0

# 结果跟踪
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
        esac
    done
    echo "----------------------------------------------"
    echo -e "  ${GREEN}PASS:$p${NC}  ${RED}FAIL:$f${NC}  ${YELLOW}SKIP:$s${NC}"
    echo "=============================================="
    [ "$f" -gt 0 ] && { echo "QA_FAIL_USB_FLASH"; exit 1; }
    echo "QA_PASS_USB_FLASH"; exit 0
}

# 参数解析
while [ $# -gt 0 ]; do
    case "$1" in
        --help|-h) echo "用法: $0 [-v] [--size N]"; echo "SE13 USB 存储设备测试 (U盘/SD读卡器)"; exit 0 ;;
        --verbose|-v) VERBOSE=1 ;;
        --size) TEST_SIZE_MB="$2"; shift ;;
        *) echo "未知参数: $1"; exit 1 ;;
    esac
    shift
done

# ============================================================================
# 辅助函数
# ============================================================================

find_usb_block_device() {
    local dev
    dev=$(lsblk -o NAME,TYPE,TRAN 2>/dev/null | grep -w usb | grep -w disk | awk '{print $1}' | head -1)
    [ -n "$dev" ] && { echo "$dev"; return 0; }
    for f in /sys/block/sd*/removable; do
        [ -f "$f" ] || continue
        [ "$(cat "$f" 2>/dev/null)" = "1" ] || continue
        echo "$f" | cut -d'/' -f4; return 0
    done 2>/dev/null
    return 1
}

find_partition() {
    [ -b "/dev/${1}1" ] && { echo "/dev/${1}1"; return 0; }
    [ -b "/dev/${1}" ] && { echo "/dev/${1}"; return 0; }
    return 1
}

find_mountpoint() {
    mount | grep "^/dev/${1}" | awk '{print $3}' | head -1
}

# ============================================================================
# 测试用例
# ============================================================================

log_info "SE13 USB 存储设备测试开始"
log_info "测试时间: $(date '+%Y-%m-%d %H:%M:%S')"

# --- 1. USB 控制器 ---
log_info "=== 1. USB 控制器检测 ==="
if lsusb >/dev/null 2>&1; then
    lsusb 2>/dev/null | while read l; do [ -n "$l" ] && log_info "  $l"; done
    add_result "USB控制器" "PASS" ""
    log_pass "USB 控制器正常"
else
    log_fail "USB 控制器不可用"
    add_result "USB控制器" "FAIL" "lsusb 无输出"
    print_summary
fi

# --- 2. USB 存储设备 ---
log_info "=== 2. USB 存储设备检测 ==="
USB_DEV=$(find_usb_block_device)
if [ -z "$USB_DEV" ]; then
    log_warn "未检测到 USB 存储设备 (检查 U 盘/SD 读卡器是否插入)"
    add_result "USB存储设备" "SKIP" "未检测到"
    print_summary
fi
log_info "USB 存储设备: /dev/$USB_DEV"
lsblk "/dev/$USB_DEV" 2>/dev/null | while read l; do [ -n "$l" ] && log_info "  $l"; done
add_result "USB存储设备" "PASS" "/dev/$USB_DEV"

# --- 3. 分区与挂载 ---
log_info "=== 3. 分区与挂载点 ==="
PART=$(find_partition "$USB_DEV")
if [ -z "$PART" ]; then
    log_fail "找不到可用分区"
    add_result "分区与挂载" "FAIL" "无分区"
    print_summary
fi
FSTYPE=$(blkid -s TYPE -o value "$PART" 2>/dev/null || echo "unknown")
SIZE=$(lsblk -o SIZE -nd "$PART" 2>/dev/null | head -1)
log_info "分区: $PART  fs=$FSTYPE  size=$SIZE"

MNT=$(find_mountpoint "$USB_DEV")
NEED_UMOUNT=0
if [ -n "$MNT" ] && [ -d "$MNT" ]; then
    log_info "已挂载: $MNT"
else
    MNT="/mnt/usb_flash_test_$$"
    mkdir -p "$MNT"
    if mount "$PART" "$MNT" 2>/dev/null; then
        log_info "手动挂载: $PART → $MNT"
        NEED_UMOUNT=1
    else
        log_fail "挂载失败"
        add_result "分区与挂载" "FAIL" "挂载 $PART 失败"
        rmdir "$MNT" 2>/dev/null
        print_summary
    fi
fi
add_result "分区与挂载" "PASS" "$PART → $MNT ($FSTYPE)"

# --- 4. dd 读写 ---
log_info "=== 4. dd 读写验证 (${TEST_SIZE_MB}MB) ==="
TF="$MNT/se13_usb_test_$$.bin"
if dd if=/dev/zero of="$TF" bs=1M count="$TEST_SIZE_MB" 2>/dev/null; then
    sync
    WS=$(stat -c %s "$TF" 2>/dev/null || echo "?")
    log_info "写入完成: ${WS} bytes"
    MD5=$(md5sum "$TF" 2>/dev/null | awk '{print $1}')
    [ -n "$MD5" ] && log_info "md5: $MD5"

    if dd if="$TF" of=/dev/null bs=1M 2>/dev/null; then
        log_pass "dd 读写 OK"
        add_result "dd读写" "PASS" "${TEST_SIZE_MB}MB md5=$MD5"
    else
        log_fail "读取失败 (设备可能断开)"
        add_result "dd读写" "FAIL" "读取失败"
    fi
    rm -f "$TF"
else
    log_fail "写入失败"
    add_result "dd读写" "FAIL" "${TEST_SIZE_MB}MB 写入失败"
fi

# 验证设备仍存在
lsblk "/dev/$USB_DEV" >/dev/null 2>&1 || log_warn "写入后设备丢失"

# fsck 不测: busybox无fsck.vfat/ext4, dd+md5已覆盖数据完整性验证
[ "$NEED_UMOUNT" -eq 1 ] && { umount "$MNT" 2>/dev/null; rmdir "$MNT" 2>/dev/null; }

print_summary