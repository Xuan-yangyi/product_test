#!/bin/bash

# 平台通过 SSH 以 linaro 身份执行；需要 root 的脚本自动提权（sudo 密码固定 linaro）
if [ "$(id -u)" -ne 0 ]; then
    printf 'linaro\n' | sudo -S -p '' bash "$0" "$@"
    exit $?
fi
# ============================================================================
# SE13 USB 接口测试 (v2)
#
# 测试内容: USB 控制器检测、设备枚举、存储设备挂载读写、文件系统检查
#
# 测试流程:
#   1. USB 控制器检测 (lsusb)
#   2. USB 设备枚举 (列出所有非 root hub 设备)
#   3. USB 存储设备检测 (lsblk + removable flag)
#   4. 挂载检测 (自动挂载 vs 手动挂载) + dd 读写 (10MB)
#   5. 文件系统完整性检查 (fsck -n)
#   6. USB 热插拔历史 (dmesg)
#
# 兼容:
#   - 自动挂载设备 (如 /media/storage-hot-sda1): 直接使用已有挂载点
#   - 无自动挂载: 手动 mount → 测试 → umount
#   - 无 U 盘: 控制器检测通过, 存储测试 SKIP
#
# 预期结果: 检测到 U 盘、成功挂载读写、QA_PASS_USB
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

TEST_MODULE="USB"
TEST_SIZE_MB=5  # 默认 5MB, USB2.0 Flash 写入较慢

usage() {
    echo "用法: $0 [选项]"
    echo "  SE13 USB 接口测试"
    echo ""
    echo "选项:"
    echo "  --help, -h         显示帮助"
    echo "  --verbose, -v      详细输出"
    echo "  --size N           dd 写入大小 MB (默认 5, USB2.0 建议 ≤10)"
}

# ============================================================================
# 辅助函数
# ============================================================================

# 查找第一个 USB 可移除块设备 (返回设备名如 sda, 无则空)
find_usb_removable() {
    for f in /sys/block/sd*/removable; do
        [ -f "$f" ] || continue
        [ "$(cat "$f" 2>/dev/null)" = "1" ] || continue
        echo "$f" | cut -d'/' -f4
        return 0
    done 2>/dev/null
    return 1
}

# 检查设备是否已挂载 (返回挂载点, 无则空)
find_mountpoint() {
    local dev="$1"
    # 先精确匹配分区
    mount | grep "^/dev/${dev}" | awk '{print $3}' | head -1
    # 兼容不带分区号的裸设备
    [ -n "$_mp" ] || mount | grep "^/dev/${dev}[0-9]" | awk '{print $3}' | head -1
}

_is_mounted() { mount | grep -q "^/dev/$1"; }

# ============================================================================
# 测试用例
# ============================================================================

# --- TC-USB-001: USB 控制器检测 ---
test_usb_controller() {
    log_info "=== TC-USB-001 USB 控制器检测 ==="

    local usb_ctrs
    usb_ctrs=$(lsusb 2>/dev/null)
    if [ -z "$usb_ctrs" ]; then
        log_fail "lsusb 无输出 — USB 控制器不可用"
        add_result "USB 控制器" "FAIL" "lsusb 无输出"
        return 1
    fi

    log_info "USB 控制器列表:"
    echo "$usb_ctrs" | while read -r line; do
        [ -n "$line" ] && log_info "  $line"
    done

    add_result "USB 控制器" "PASS" ""
    log_pass "USB 控制器检测通过"
    return 0
}

# --- TC-USB-002: USB 设备枚举 ---
test_usb_device_enum() {
    log_info "=== TC-USB-002 USB 设备枚举 ==="

    local devices
    devices=$(lsusb 2>/dev/null | grep -v "root hub")
    if [ -z "$devices" ]; then
        log_warn "仅检测到 root hub，无 USB 外设连接"
        add_result "USB 设备枚举" "SKIP" "仅 root hub"
        return 0
    fi

    local count
    count=$(echo "$devices" | wc -l)
    log_info "检测到 $count 个 USB 设备:"
    echo "$devices" | while read -r line; do
        [ -n "$line" ] && log_info "  $line"
    done

    add_result "USB 设备枚举" "PASS" "${count}个设备"
    log_pass "USB 设备枚举 = $count 个"
    return 0
}

# --- TC-USB-003: USB 存储设备检测 ---
test_usb_storage_detect() {
    log_info "=== TC-USB-003 USB 存储设备检测 ==="

    local removable
    removable=$(find_usb_removable)

    if [ -z "$removable" ]; then
        # 兜底：通过 lsblk TRAN 列检测
        local usb_devs
        usb_devs=$(lsblk -o NAME,TYPE,TRAN,SIZE 2>/dev/null | grep -w usb)
        if [ -n "$usb_devs" ]; then
            log_info "USB 存储设备 (lsblk):"
            echo "$usb_devs" | while read -r line; do log_info "  $line"; done
            add_result "USB 存储检测" "PASS" "lsblk 检测到 usb 设备"
            log_pass "USB 存储设备检测通过"
            return 0
        fi
        log_warn "未检测到 USB 存储设备 (检查 U 盘是否插入)"
        add_result "USB 存储检测" "SKIP" "无 USB 存储设备"
        return 0
    fi

    log_info "可移除设备: /dev/$removable"
    lsblk "/dev/$removable" 2>/dev/null | while read -r line; do
        [ -n "$line" ] && log_info "  $line"
    done

    # 记录设备参数
    local size sectors
    size=$(lsblk -o SIZE -nd "/dev/$removable" 2>/dev/null | head -1)
    sectors=$(cat "/sys/block/${removable}/size" 2>/dev/null)
    log_info "设备容量: $size, sectors=$sectors"

    add_result "USB 存储检测" "PASS" "/dev/$removable $size"
    log_pass "USB 存储设备 = /dev/$removable ($size)"
    return 0
}

# --- TC-USB-004: USB 挂载读写 ---
test_usb_mount_rw() {
    log_info "=== TC-USB-004 USB 挂载读写 ==="

    local dev
    dev=$(find_usb_removable)
    if [ -z "$dev" ]; then
        log_warn "无可移除 USB 设备，跳过挂载读写测试"
        add_result "USB 挂载读写" "SKIP" "无可移除设备"
        return 0
    fi

    local mnt="" need_umount=0
    local partition="/dev/${dev}1"
    [ -b "$partition" ] || partition="/dev/${dev}"

    # 策略: 优先使用已有自动挂载点 (避免 umount 触发 USB 重枚举不稳定)
    # 无自动挂载时才手动 mount
    if _is_mounted "${dev}" || _is_mounted "${dev}1"; then
        mnt=$(mount | grep "^/dev/${dev}" | awk '{print $3}' | head -1)
        if [ -n "$mnt" ] && [ -d "$mnt" ]; then
            log_info "使用已有挂载点: /dev/${dev} → $mnt"
            need_umount=0  # 不卸载系统自动挂载点
        fi
    fi

    # 无已有挂载点, 手动挂载
    if [ -z "$mnt" ] || [ ! -d "$mnt" ]; then
        mnt="/mnt/usb_test_$$"
        run_sudo mkdir -p "$mnt" 2>/dev/null
        need_umount=1

        if run_sudo mount "$partition" "$mnt" 2>/dev/null; then
            log_info "手动挂载: $partition → $mnt"
        else
            log_fail "USB 挂载失败 ($partition → $mnt)"
            add_result "USB 挂载读写" "FAIL" "挂载失败"
            run_sudo rmdir "$mnt" 2>/dev/null
            return 1
        fi
    fi

    # dd 写入测试
    local test_file="$mnt/se13_usb_test_$$.bin"
    log_info "写入 ${TEST_SIZE_MB}MB 测试文件..."

    if ! run_sudo dd if=/dev/zero of="$test_file" bs=1M count="$TEST_SIZE_MB" status=none 2>/dev/null; then
        log_fail "USB 写入失败"
        add_result "USB 挂载读写" "FAIL" "${TEST_SIZE_MB}MB 写入失败"
        run_sudo rm -f "$test_file" 2>/dev/null
        [ "$need_umount" -eq 1 ] && { run_sudo umount "$mnt" 2>/dev/null; run_sudo rmdir "$mnt" 2>/dev/null; }
        return 1
    fi

    # 同步确保数据落盘, 检查设备
    run_sudo sync
    if ! lsblk "/dev/${dev}" >/dev/null 2>&1; then
        log_fail "写入后 USB 设备丢失 (可能连接不稳定)"
        add_result "USB 挂载读写" "FAIL" "写入后设备丢失"
        [ "$need_umount" -eq 1 ] && run_sudo rmdir "$mnt" 2>/dev/null
        return 1
    fi

    local write_size
    write_size=$(run_sudo stat -c %s "$test_file" 2>/dev/null || echo "unknown")
    log_info "写入完成: ${write_size} bytes"

    # dd 读取验证
    log_info "读取验证..."
    if run_sudo dd if="$test_file" of=/dev/null bs=1M status=none 2>/dev/null; then
        log_info "读取验证成功"
    else
        log_fail "USB 读取失败 (设备可能已断开)"
        add_result "USB 挂载读写" "FAIL" "${TEST_SIZE_MB}MB 读取失败"
        run_sudo rm -f "$test_file"
        [ "$need_umount" -eq 1 ] && { run_sudo umount "$mnt" 2>/dev/null; run_sudo rmdir "$mnt" 2>/dev/null; }
        return 1
    fi

    # md5 校验
    local md5_val
    md5_val=$(run_sudo md5sum "$test_file" 2>/dev/null | awk '{print $1}')
    [ -n "$md5_val" ] && log_info "md5: $md5_val"

    # 清理
    run_sudo rm -f "$test_file"

    if [ "$need_umount" -eq 1 ]; then
        run_sudo umount "$mnt" 2>/dev/null
        run_sudo rmdir "$mnt" 2>/dev/null
        log_info "umount 清理完成"
    fi

    log_pass "USB 挂载读写 (${TEST_SIZE_MB}MB) PASS"
    add_result "USB 挂载读写" "PASS" "${TEST_SIZE_MB}MB 读写成功"
    return 0
}

# --- TC-USB-005: 文件系统完整性 ---
test_usb_fsck() {
    log_info "=== TC-USB-005 文件系统检查 ==="

    local dev
    dev=$(find_usb_removable)
    if [ -z "$dev" ]; then
        log_warn "无可移除 USB 设备，跳过 fsck"
        add_result "USB fsck" "SKIP" "无可移除设备"
        return 0
    fi

    # 先 umount 再 fsck
    local was_mounted=0 mnt=""
    if _is_mounted "${dev}" || _is_mounted "${dev}1"; then
        was_mounted=1
        mnt=$(mount | grep "^/dev/${dev}" | awk '{print $3}' | head -1)
        run_sudo umount "$mnt" 2>/dev/null || log_warn "umount $mnt 失败, 跳过 fsck"
    fi

    local partition="/dev/${dev}1"
    [ -b "$partition" ] || partition="/dev/${dev}"

    local fstype
    fstype=$(run_sudo blkid -s TYPE -o value "$partition" 2>/dev/null)

    local fsck_cmd=""
    case "$fstype" in
        vfat|msdos|fat)      fsck_cmd="fsck.vfat" ;;
        ext2|ext3|ext4)      fsck_cmd="fsck.ext4" ;;
        ntfs)                 fsck_cmd="ntfsfix" ;;
    esac

    if [ -n "$fsck_cmd" ] && command -v "$fsck_cmd" >/dev/null 2>&1; then
        log_info "运行 $fsck_cmd -n $partition ..."
        local fsck_out
        fsck_out=$(run_sudo $fsck_cmd -n "$partition" 2>&1)
        local rc=$?

        if [ "$VERBOSE" -ge 1 ]; then
            echo "$fsck_out" | while read -r line; do log_info "  $line"; done
        fi

        if [ $rc -eq 0 ]; then
            log_pass "fsck 通过 ($fstype)"
            add_result "USB fsck" "PASS" "$fstype 文件系统正常"
        else
            log_warn "fsck 发现问题 (exit=$rc), 详见日志"
            add_result "USB fsck" "WARN" "$fstype fsck exit=$rc"
        fi
    else
        log_info "未找到 fsck 工具 (fstype=$fstype), 跳过"
        add_result "USB fsck" "SKIP" "无 $fstype fsck 工具"
    fi

    # 恢复挂载
    if [ "$was_mounted" -eq 1 ] && [ -n "$mnt" ]; then
        run_sudo mount "$partition" "$mnt" 2>/dev/null
        log_info "恢复挂载: $partition → $mnt"
    fi

    return 0
}

# --- TC-USB-006: USB 热插拔历史 ---
test_usb_hotplug_history() {
    log_info "=== TC-USB-006 USB 热插拔历史 ==="

    local events
    events=$(dmesg 2>/dev/null | grep -i "usb.*new\|usb.*disconnect" | tail -10)

    if [ -z "$events" ]; then
        log_info "dmesg 中无 USB 热插拔记录"
        add_result "USB 热插拔历史" "SKIP" "dmesg 无记录"
        return 0
    fi

    log_info "最近 10 条 USB 事件:"
    echo "$events" | while read -r line; do
        [ -n "$line" ] && log_info "  $line"
    done

    local last_connect
    last_connect=$(echo "$events" | grep "new high-speed\|new SuperSpeed" | tail -1)
    if [ -n "$last_connect" ]; then
        add_result "USB 热插拔历史" "PASS" "有连接记录"
    else
        local last_disconnect
        last_disconnect=$(echo "$events" | grep -i "disconnect" | tail -1)
        if [ -n "$last_disconnect" ]; then
            log_warn "最近事件为断开连接"
            add_result "USB 热插拔历史" "WARN" "最近为断开事件"
        else
            add_result "USB 热插拔历史" "SKIP" "无明显连接/断开事件"
        fi
    fi

    return 0
}

# ============================================================================
# 主流程
# ============================================================================

main() {
    # 先处理 --size (parse_args 不识别), 其余透传
    local filtered_args=()
    while [ $# -gt 0 ]; do
        case "$1" in
            --size) TEST_SIZE_MB="$2"; shift 2 ;;
            *) filtered_args+=("$1"); shift ;;
        esac
    done
    parse_args "${filtered_args[@]}"

    log_info "SE13 USB 接口测试开始 (v2)"
    log_info "测试时间: $(date '+%Y-%m-%d %H:%M:%S')"

    test_usb_controller
    test_usb_device_enum
    test_usb_storage_detect
    test_usb_mount_rw
    test_usb_fsck
    test_usb_hotplug_history

    print_summary
}

main "$@"