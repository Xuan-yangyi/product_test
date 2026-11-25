#!/bin/bash

# 平台通过 SSH 以 linaro 身份执行；需要 root 的脚本自动提权（sudo 密码固定 linaro）
if [ "$(id -u)" -ne 0 ]; then
    printf 'linaro\n' | sudo -S -p '' bash "$0" "$@"
    exit $?
fi
# ============================================================================
# SE13 USB 存储设备 + 4G 模块 基础功能测试 (自包含版, 不依赖 lib)
# 通过跳板机串口运行: bash /tmp/se13_usb_4g_test.sh
# ============================================================================

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
log_info()  { echo -e "${CYAN}[INFO]${NC}  $(date '+%H:%M:%S') $*"; }
log_pass()  { echo -e "${GREEN}[PASS]${NC}  $*"; }
log_fail()  { echo -e "${RED}[FAIL]${NC}  $*"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }

PASS=0; FAIL=0; SKIP=0

result() {
    case "$2" in
        PASS) echo -e "  ${GREEN}✓${NC} $1: $3"; PASS=$((PASS+1)) ;;
        FAIL) echo -e "  ${RED}✗${NC} $1: $3"; FAIL=$((FAIL+1)) ;;
        SKIP) echo -e "  ${YELLOW}−${NC} $1: $3"; SKIP=$((SKIP+1)) ;;
    esac
}

summary() {
    echo ""; echo "=============================================="
    echo "  测试结果: PASS=$PASS  FAIL=$FAIL  SKIP=$SKIP"
    echo "=============================================="
    [ "$FAIL" -gt 0 ] && { echo "QA_FAIL_$1"; exit 1; }
    echo "QA_PASS_$1"; exit 0
}

# ======================================================================
# Section 1: USB 存储设备测试
# ======================================================================
test_usb_flash() {
    log_info "========== USB 存储设备测试 =========="

    # 1.1 控制器检测
    log_info "--- 1.1 USB 控制器 ---"
    if lsusb >/dev/null 2>&1; then
        lsusb 2>/dev/null | grep -i "root hub" | while read l; do log_info "  $l"; done
        log_pass "USB 控制器正常"
        result "USB控制器" PASS ""
    else
        log_fail "USB 控制器不可用"
        result "USB控制器" FAIL "lsusb 无输出"
        return
    fi

    # 1.2 USB 存储设备检测
    log_info "--- 1.2 USB 存储设备 ---"
    USB_DEV=$(lsblk -o NAME,TYPE,TRAN 2>/dev/null | grep -w usb | grep -w disk | awk '{print $1}' | head -1)
    if [ -z "$USB_DEV" ]; then
        # fallback: /sys/block/sd*/removable
        for f in /sys/block/sd*/removable; do
            [ -f "$f" ] && [ "$(cat $f 2>/dev/null)" = "1" ] && { USB_DEV=$(echo $f|cut -d/ -f4); break; }
        done 2>/dev/null
    fi
    if [ -z "$USB_DEV" ]; then
        log_warn "未检测到 USB 存储设备"
        result "USB存储设备" SKIP "未检测到"
        return
    fi
    log_info "USB 存储设备: /dev/$USB_DEV"
    lsblk "/dev/$USB_DEV" 2>/dev/null | while read l; do log_info "  $l"; done
    result "USB存储设备" PASS "/dev/$USB_DEV"

    # 1.3 分区
    log_info "--- 1.3 分区检测 ---"
    PART=""
    [ -b "/dev/${USB_DEV}1" ] && PART="/dev/${USB_DEV}1"
    [ -z "$PART" ] && [ -b "/dev/${USB_DEV}" ] && PART="/dev/${USB_DEV}"
    if [ -z "$PART" ]; then
        log_fail "找不到可用分区"
        result "分区检测" FAIL "无分区"
        return
    fi
    FSTYPE=$(blkid -s TYPE -o value "$PART" 2>/dev/null || echo "unknown")
    SIZE=$(lsblk -o SIZE -nd "$PART" 2>/dev/null | head -1)
    log_info "分区: $PART  fs=$FSTYPE  size=$SIZE"
    result "分区检测" PASS "$PART ($FSTYPE $SIZE)"

    # 1.4 挂载检测
    log_info "--- 1.4 挂载点 ---"
    MNT=$(mount | grep "^/dev/${USB_DEV}" | awk '{print $3}' | head -1)
    NEED_UMOUNT=0
    if [ -n "$MNT" ] && [ -d "$MNT" ]; then
        log_info "已挂载: $MNT"
    else
        MNT="/mnt/usb_flash_$$"
        mkdir -p "$MNT"
        if mount "$PART" "$MNT" 2>/dev/null; then
            log_info "手动挂载: $PART -> $MNT"
            NEED_UMOUNT=1
        else
            log_fail "挂载失败"
            result "挂载点" FAIL "mount 失败"
            rmdir "$MNT" 2>/dev/null
            return
        fi
    fi
    result "挂载点" PASS "$MNT"

    # 1.5 dd 读写
    log_info "--- 1.5 dd 读写 (10MB) ---"
    TF="$MNT/se13_usb_test_$$.bin"
    if dd if=/dev/zero of="$TF" bs=1M count=10 2>/dev/null; then
        sync
        WS=$(stat -c %s "$TF" 2>/dev/null || echo "?")
        log_info "写入: ${WS} bytes"
        MD5=$(md5sum "$TF" 2>/dev/null | awk '{print $1}')
        [ -n "$MD5" ] && log_info "md5: $MD5"
        if dd if="$TF" of=/dev/null bs=1M 2>/dev/null; then
            log_pass "dd 读写 OK"
            result "dd读写" PASS "10MB $([ -n "$MD5" ] && echo md5=$MD5)"
        else
            log_fail "读取失败"
            result "dd读写" FAIL "读取失败"
        fi
        rm -f "$TF"
    else
        log_fail "写入失败"
        result "dd读写" FAIL "写入失败"
    fi

    # 1.6 fsck
    log_info "--- 1.6 文件系统检查 ---"
    case "$FSTYPE" in
        vfat|msdos|fat)
            if command -v fsck.vfat >/dev/null 2>&1; then
                # 需要在未挂载状态
                umount "$PART" 2>/dev/null
                fsck.vfat -n "$PART" 2>&1 | while read l; do [ -n "$l" ] && log_info "  $l"; done
                if [ $? -eq 0 ]; then
                    result "fsck" PASS "$FSTYPE 正常"
                else
                    result "fsck" WARN "$FSTYPE 有警告"
                fi
                # 恢复挂载
                [ "$NEED_UMOUNT" -eq 0 ] && mount "$PART" "$MNT" 2>/dev/null
            else
                result "fsck" SKIP "无 fsck.vfat"
            fi
            ;;
        ext2|ext3|ext4)
            if command -v fsck.ext4 >/dev/null 2>&1; then
                umount "$PART" 2>/dev/null
                fsck.ext4 -n "$PART" 2>&1 | while read l; do [ -n "$l" ] && log_info "  $l"; done
                [ $? -eq 0 ] && result "fsck" PASS "$FSTYPE 正常" || result "fsck" WARN "有警告"
                [ "$NEED_UMOUNT" -eq 0 ] && mount "$PART" "$MNT" 2>/dev/null
            else
                result "fsck" SKIP "无 fsck.ext4"
            fi
            ;;
        *) result "fsck" SKIP "fstype=$FSTYPE";;
    esac

    # cleanup
    [ "$NEED_UMOUNT" -eq 1 ] && { umount "$MNT" 2>/dev/null; rmdir "$MNT" 2>/dev/null; }

    log_info "========== USB 存储测试完成 =========="
}

# ======================================================================
# Section 2: 4G 模块测试
# ======================================================================
test_4g_modem() {
    log_info "========== 4G 模块测试 =========="

    # 2.1 模块检测
    log_info "--- 2.1 4G 模块 USB 检测 ---"
    MODEM=$(lsusb 2>/dev/null | grep -iE "fibocom|sierra|huawei|quectel|simcom|telit|u-blox|thales|modem|1508")
    if [ -z "$MODEM" ]; then
        log_info "lsusb 未匹配已知 4G 模块，显示全部非 hub USB 设备:"
        lsusb 2>/dev/null | grep -v "root hub" | grep -v "Hub" | while read l; do [ -n "$l" ] && log_info "  $l"; done
        log_warn "未检测到 4G 模块"
        result "4G模块检测" SKIP "lsusb 无匹配"
        return
    fi
    echo "$MODEM" | while read l; do [ -n "$l" ] && log_info "  $l"; done
    result "4G模块检测" PASS "$(echo "$MODEM"|head -1|cut -d: -f3|tr -s ' ' ' ')"
    log_pass "4G 模块已检测到"

    # 2.2 ttyUSB 端口
    log_info "--- 2.2 ttyUSB 端口 ---"
    TTY_LIST=$(ls /dev/ttyUSB* 2>/dev/null)
    [ -z "$TTY_LIST" ] && TTY_LIST=$(ls /dev/ttyACM* 2>/dev/null)
    if [ -z "$TTY_LIST" ]; then
        log_fail "未找到 ttyUSB/ttyACM 设备"
        result "ttyUSB端口" FAIL "无设备"
        return
    fi
    TTY_COUNT=$(echo "$TTY_LIST" | wc -l)
    log_info "$TTY_COUNT 个端口: $(echo $TTY_LIST | tr '\n' ' ')"
    result "ttyUSB端口" PASS "$TTY_COUNT个"

    # 2.3 找 AT 端口
    log_info "--- 2.3 AT 端口探测 ---"
    AT_PORT=""
    for t in /dev/ttyUSB*; do
        [ -e "$t" ] || continue
        stty -F "$t" 115200 cs8 -cstopb -parenb -crtscts -echo raw 2>/dev/null
        timeout 0.5 cat "$t" >/dev/null 2>&1 || true
        printf 'AT\r\n' > "$t"
        RESP=$(timeout 3 cat "$t" 2>/dev/null || true)
        if echo "$RESP" | grep -q "OK"; then
            AT_PORT="$t"
            log_info "AT 端口: $AT_PORT"
            break
        fi
    done
    # 兜底: 用第一个 ttyUSB
    [ -z "$AT_PORT" ] && for t in /dev/ttyUSB*; do [ -e "$t" ] && { AT_PORT="$t"; log_warn "AT 探测失败，使用 $t (无 OK 响应)"; break; }; done
    if [ -z "$AT_PORT" ]; then
        log_fail "找不到可用 AT 端口"
        result "AT端口" FAIL "无响应"
        return
    fi
    result "AT端口" PASS "$AT_PORT"

    # 辅助函数
    at_send() {
        local cmd="$1"
        stty -F "$AT_PORT" 115200 cs8 -cstopb -parenb -crtscts -echo raw 2>/dev/null
        timeout 0.5 cat "$AT_PORT" >/dev/null 2>&1 || true
        printf '%s\r\n' "$cmd" > "$AT_PORT"
        timeout 3 cat "$AT_PORT" 2>/dev/null || true
    }

    # 2.4 AT 基础 (echo 模式)
    log_info "--- 2.4 AT 基础指令 ---"
    AT_RESP=$(at_send "AT")
    if echo "$AT_RESP" | grep -q "OK"; then
        log_pass "AT -> OK"
        result "AT基础指令" PASS "OK"

        # ATI 厂商信息
        ATI=$(at_send "ATI")
        MODEM_INFO=$(echo "$ATI" | grep -vE '^\s*$|^AT' | head -2 | tr '\n' ' ')
        [ -n "$MODEM_INFO" ] && log_info "模块: $MODEM_INFO"

        # IMEI
        IMEI_RESP=$(at_send "AT+CGSN")
        IMEI=$(echo "$IMEI_RESP" | grep -oE '[0-9]{15}' | head -1)
        [ -n "$IMEI" ] && log_info "IMEI: $IMEI"
    else
        log_fail "AT 无响应"
        result "AT基础指令" FAIL "无 OK"
        return
    fi

    # 2.5 SIM 卡
    log_info "--- 2.5 SIM 卡状态 ---"
    CPIN=$(at_send "AT+CPIN?")
    if echo "$CPIN" | grep -q "READY"; then
        log_pass "SIM: READY"
        result "SIM卡" PASS "READY"
    elif echo "$CPIN" | grep -qi "SIM PIN"; then
        log_warn "SIM 需要 PIN 码"
        result "SIM卡" WARN "需要PIN"
    else
        CPIN_LINE=$(echo "$CPIN" | grep '+CPIN' | head -1)
        log_warn "SIM: ${CPIN_LINE:-无响应}"
        result "SIM卡" WARN "$CPIN_LINE"
    fi

    # 2.6 信号强度
    log_info "--- 2.6 信号强度 ---"
    CSQ=$(at_send "AT+CSQ")
    CSQ_LINE=$(echo "$CSQ" | grep -oE '\+CSQ: [0-9,]+' | head -1)
    if [ -n "$CSQ_LINE" ]; then
        RSSI=$(echo "$CSQ_LINE" | awk '{print $2}' | cut -d, -f1)
        BER=$(echo "$CSQ_LINE" | awk '{print $2}' | cut -d, -f2)
        if [ "$RSSI" = "99" ]; then
            log_warn "信号: RSSI=99 (无信号)"
            result "信号强度" WARN "RSSI=99 无信号"
        else
            log_info "信号: RSSI=$RSSI BER=$BER"
            result "信号强度" PASS "RSSI=$RSSI"
        fi
    else
        log_warn "未获取信号值"
        result "信号强度" WARN "无响应"
    fi

    # 2.7 网络注册
    log_info "--- 2.7 网络注册状态 ---"
    CREG=$(at_send "AT+CREG?")
    CREG_LINE=$(echo "$CREG" | grep -oE '\+CREG: [0-9,]+' | head -1)
    if [ -n "$CREG_LINE" ]; then
        STAT=$(echo "$CREG_LINE" | awk '{print $2}' | cut -d, -f2)
        case "$STAT" in
            1) STAT_TXT="已注册(归属)";;
            5) STAT_TXT="已注册(漫游)";;
            2) STAT_TXT="搜索中";;
            *) STAT_TXT="状态=$STAT";;
        esac
        log_info "网络: $STAT_TXT"
        [ "$STAT" = "1" -o "$STAT" = "5" ] && result "网络注册" PASS "$STAT_TXT" || result "网络注册" WARN "$STAT_TXT"
    else
        log_warn "未获取注册状态"
        result "网络注册" WARN "无响应"
    fi

    # 2.8 运营商
    log_info "--- 2.8 运营商信息 ---"
    COPS=$(at_send "AT+COPS?")
    OPER=$(echo "$COPS" | grep '+COPS' | grep -o '"[^"]*"' | head -1 | tr -d '"')
    if [ -n "$OPER" ]; then
        log_info "运营商: $OPER"
        result "运营商" PASS "$OPER"
    else
        log_info "运营商: 未获取"
        result "运营商" WARN "无响应"
    fi

    log_info "========== 4G 模块测试完成 =========="
}

# ======================================================================
# 主流程
# ======================================================================
echo "=============================================="
echo "  SE13 USB 存储 + 4G 模块 基础功能测试"
echo "  时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo "=============================================="

# USB Flash (不调用 summary，让它跑完)
PASS=0; FAIL=0; SKIP=0
test_usb_flash
USB_PASS=$PASS; USB_FAIL=$FAIL; USB_SKIP=$SKIP
echo ""
echo "--- USB Flash 小结: PASS=$USB_PASS FAIL=$USB_FAIL SKIP=$USB_SKIP ---"

# 4G Modem
PASS=0; FAIL=0; SKIP=0
test_4g_modem
MODEM_PASS=$PASS; MODEM_FAIL=$FAIL; MODEM_SKIP=$SKIP
echo ""
echo "--- 4G Modem 小结: PASS=$MODEM_PASS FAIL=$MODEM_FAIL SKIP=$MODEM_SKIP ---"

# 最终汇总
echo ""
echo "=============================================="
echo "  最终结果"
echo "  USB Flash:  PASS=$USB_PASS  FAIL=$USB_FAIL  SKIP=$USB_SKIP"
echo "  4G Modem:   PASS=$MODEM_PASS  FAIL=$MODEM_FAIL  SKIP=$MODEM_SKIP"
echo "=============================================="
TOTAL_FAIL=$((USB_FAIL + MODEM_FAIL))
[ "$TOTAL_FAIL" -gt 0 ] && { echo "QA_FAIL_SE13_USB_4G"; exit 1; }
echo "QA_PASS_SE13_USB_4G"
exit 0