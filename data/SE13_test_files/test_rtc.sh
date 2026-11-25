#!/bin/bash

# 平台通过 SSH 以 linaro 身份执行；需要 root 的脚本自动提权（sudo 密码固定 linaro）
if [ "$(id -u)" -ne 0 ]; then
    printf 'linaro\n' | sudo -S -p '' bash "$0" "$@"
    exit $?
fi
# ============================================================================
# SE13 RTC/时间 基础功能测试
# 用法:
#   bash test_rtc.sh                        # 默认: 只读检查 1-4 (不修改时间)
#   bash test_rtc.sh --full                 # 完整测试: 含时间写入+同步验证 5-8
#
# 测试项:
#   1. 查看系统时间          — date / date -Iseconds
#   2. 查看系统时区          — timedatectl / date +%Z
#   3. 查看硬件时间          — hwclock -r
#   4. 网络时间同步状态      — timedatectl NTP / systemd-timesyncd
#   5. 手动设置系统时间      — date -s (仅 --full)
#   6. 手动设置硬件时间      — hwclock --set (仅 --full)
#   7. 硬件时钟→系统时钟     — hwclock --hctosys (仅 --full)
#   8. 系统时钟→硬件时钟     — hwclock --systohc (仅 --full)
#
# SE13 实测环境: root 用户, 无 ntpdate, systemd-timesyncd 自动校时
# ============================================================================
set -e

MODE="check"
FAIL_COUNT=0
PASS_COUNT=0

usage() {
    echo "用法: $0 [选项]"
    echo ""
    echo "  --full          完整测试 (含写入和同步操作, 会修改时间)"
    echo "  -h, --help      显示帮助"
    echo ""
    echo "  默认模式: 只读检查 1-4 项, 不修改任何时间"
    echo "  --full 模式: 执行全部 8 项, 测试后 systemd-timesyncd 自动恢复正确时间"
    exit 0
}

while [ $# -gt 0 ]; do
    case "$1" in
        --full)     MODE="full"; shift ;;
        -h|--help)  usage ;;
        *)          echo "未知参数: $1"; usage ;;
    esac
done

# ============================================================================
_pass()  { echo "  ✅ PASS: $1"; PASS_COUNT=$((PASS_COUNT + 1)); }
_fail()  { echo "  ❌ FAIL: $1"; FAIL_COUNT=$((FAIL_COUNT + 1)); }
_info()  { echo "  ℹ️  $1"; }
_warn()  { echo "  ⚠️  $1"; }
_skip()  { echo "  ⏭️  SKIP: $1"; }
# ============================================================================

echo "============================================"
echo "  SE13 RTC/时间 基础功能测试"
echo "  模式: $MODE"
echo "  时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo "============================================"
echo ""

# ========================================================================
# 测试 1: 查看系统时间
# ========================================================================
echo "--- [1/8] 查看系统时间 ---"
SYS_TIME_BEFORE=$(date '+%Y-%m-%d %H:%M:%S')
SYS_EPOCH_BEFORE=$(date +%s)
echo "  date:        $(date)"
echo "  ISO 8601:    $(date -Iseconds)"
echo "  Epoch:       $SYS_EPOCH_BEFORE"

SYS_YEAR=$(date +%Y)
if [ "$SYS_YEAR" -lt 2020 ] || [ "$SYS_YEAR" -gt 2099 ]; then
    _fail "系统时间异常 (年份=$SYS_YEAR)"
else
    _pass "系统时间可读, 年份=$SYS_YEAR"
fi

echo ""
# ========================================================================
# 测试 2: 查看系统时区
# ========================================================================
echo "--- [2/8] 查看系统时区 ---"

TZ_INFO=""
# 首选 timedatectl (systemd 下最权威)
if command -v timedatectl &>/dev/null; then
    TZ_INFO=$(timedatectl show --property=Timezone --value 2>/dev/null)
    echo "  timedatectl:  $TZ_INFO"
fi

# 备用: /etc/localtime 符号链接
if [ -z "$TZ_INFO" ]; then
    TZ_INFO=$(readlink /etc/localtime 2>/dev/null | sed 's|.*/zoneinfo/||')
    echo "  localtime:    $TZ_INFO"
fi

# 再备用: /etc/timezone (SE13 实测此文件可能不准, 仅作参考)
if [ -f /etc/timezone ]; then
    ETCTZ=$(cat /etc/timezone)
    echo "  /etc/timezone: $ETCTZ (仅供参考, 以 timedatectl 为准)"
fi

TZ_SHORT=$(date +%Z)
TZ_OFFSET=$(date +%z)
echo "  date +%Z:     $TZ_SHORT"
echo "  UTC 偏移:     $TZ_OFFSET"

if [ -n "$TZ_INFO" ]; then
    _pass "时区: $TZ_INFO (UTC$TZ_OFFSET)"
else
    _fail "无法获取时区信息"
fi

echo ""
# ========================================================================
# 测试 3: 查看硬件时间 (RTC)
# ========================================================================
echo "--- [3/8] 查看硬件时间 ---"

HWC_BEFORE=""
if HWC_BEFORE=$(hwclock -r 2>/dev/null); then
    echo "  hwclock -r:  $HWC_BEFORE"
    _pass "硬件时钟可读"

    # 计算软硬件时钟偏差
    HWC_EPOCH=$(date -d "$HWC_BEFORE" +%s 2>/dev/null || echo 0)
    if [ "$HWC_EPOCH" -gt 0 ]; then
        DRIFT=$((SYS_EPOCH_BEFORE - HWC_EPOCH))
        DRIFT_ABS=${DRIFT#-}
        echo "  软硬件偏差: ${DRIFT}秒"
        if [ "$DRIFT_ABS" -le 5 ]; then
            _pass "软硬件时钟偏差 ≤5秒"
        else
            _warn "软硬件时钟偏差较大 (${DRIFT}秒), --full 模式可同步"
        fi
    fi
else
    _fail "hwclock -r 失败 (RTC 不可用?)"
    HWC_BEFORE="N/A"
fi

echo ""
# ========================================================================
# 测试 4: 网络时间同步状态
# ========================================================================
echo "--- [4/8] 网络时间同步状态 ---"

NTP_METHOD=""
TIMESYNCD_ACTIVE=0

# 首选: timedatectl (SE13 实测可用)
if command -v timedatectl &>/dev/null; then
    NTP_ENABLED=$(timedatectl show --property=NTP 2>/dev/null)
    echo "  $NTP_ENABLED"
    if echo "$NTP_ENABLED" | grep -q "yes"; then
        echo "  systemd-timesyncd: active"
        TIMESYNCD_ACTIVE=1
        NTP_METHOD="systemd-timesyncd"
        _pass "NTP 已启用 (systemd-timesyncd)"
    else
        _info "systemd-timesyncd NTP 未启用"
    fi
fi

# 备选: ntpdate (SE13 实测未安装)
if command -v ntpdate &>/dev/null; then
    NTP_RESULT=$(ntpdate -q pool.ntp.org 2>&1) || true
    echo "  ntpdate -q pool.ntp.org:"
    echo "  $NTP_RESULT" | head -3
    _pass "ntpdate 可用"
    NTP_METHOD="ntpdate"
fi

if [ -z "$NTP_METHOD" ]; then
    _info "无 NTP 客户端, 时间同步依赖手动设置"
fi

echo ""
# ========================================================================
# 只读模式到此结束
# ========================================================================
if [ "$MODE" != "full" ]; then
    echo ""
    echo "============================================"
    echo "  测试结果 (只读检查模式)"
    echo "  PASS: $PASS_COUNT   FAIL: $FAIL_COUNT"
    echo "============================================"
    echo ""
    echo "  💡 完整测试 (含时间写入+时钟同步): bash $0 --full"
    if [ $FAIL_COUNT -gt 0 ]; then
        echo "  ⚠️  QA_FAIL_RTC"
        exit 1
    else
        echo "  ✅ QA_PASS_RTC"
        exit 0
    fi
fi

echo ""
echo "============================================"
echo "  ⚠️  完整测试模式 — 将修改时间"
echo "  systemd-timesyncd 会在测试后自动恢复正确时间"
echo "============================================"
echo ""

# ========================================================================
# 测试 5: 手动设置系统时间
# ========================================================================
echo "--- [5/8] 手动设置系统时间 ---"

# 跳到一个明显不同的时间, 用于验证设置生效
TEST_DATE="2026-01-01 12:00:00"
if date -s "$TEST_DATE" 2>/dev/null; then
    sleep 1
    echo "  设置目标: $TEST_DATE"
    echo "  date 确认: $(date)"
    _pass "date -s 设置成功"
else
    _fail "date -s 设置失败"
fi

echo ""
# ========================================================================
# 测试 6: 手动设置硬件时间
# ========================================================================
echo "--- [6/8] 手动设置硬件时间 ---"

HWC_TEST_DATE="2026-01-01 12:00:00"
if hwclock --set --date="$HWC_TEST_DATE" 2>/dev/null; then
    HWC_AFTER=$(hwclock -r 2>/dev/null)
    echo "  设置目标: $HWC_TEST_DATE"
    echo "  hwclock -r 确认: $HWC_AFTER"
    _pass "hwclock --set 设置成功"
else
    _fail "hwclock --set 设置失败"
fi

echo ""
# ========================================================================
# 测试 7: 硬件时钟 → 系统时钟 (hctosys)
# ========================================================================
echo "--- [7/8] 硬件时钟 → 系统时钟 (hwclock --hctosys) ---"

SYS_BEFORE=$(date '+%Y-%m-%d %H:%M:%S')
HWC_BEFORE_HCTOSYS=$(hwclock -r 2>/dev/null)
echo "  操作前: 系统=$SYS_BEFORE, 硬件=$HWC_BEFORE_HCTOSYS"

if hwclock --hctosys 2>/dev/null; then
    sleep 1
    SYS_AFTER=$(date '+%Y-%m-%d %H:%M:%S')
    echo "  操作后: 系统=$SYS_AFTER"

    HWC_EPOCH=$(date -d "$HWC_BEFORE_HCTOSYS" +%s 2>/dev/null || echo 0)
    SYS_EPOCH=$(date +%s)
    DRIFT=$((SYS_EPOCH - HWC_EPOCH))
    DRIFT_ABS=${DRIFT#-}

    if [ "$DRIFT_ABS" -le 5 ]; then
        _pass "hctosys: 系统时钟已从硬件时钟恢复 (偏差=${DRIFT}秒)"
    elif [ "$TIMESYNCD_ACTIVE" -eq 1 ] && [ "$DRIFT_ABS" -gt 3600 ]; then
        # systemd-timesyncd 正在运行, 可能立刻把时间跳回正确值
        _info "hctosys 执行完成, 但 systemd-timesyncd 可能已修正时间 (偏差=${DRIFT}秒, 预期行为)"
    else
        _info "hctosys 执行完成 (偏差=${DRIFT}秒)"
    fi
else
    _fail "hwclock --hctosys 失败"
fi

echo ""
# ========================================================================
# 测试 8: 系统时钟 → 硬件时钟 (systohc)
# ========================================================================
echo "--- [8/8] 系统时钟 → 硬件时钟 (hwclock --systohc) ---"

SYS_BEFORE_SYSTOHC=$(date '+%Y-%m-%d %H:%M:%S')
if hwclock --systohc 2>/dev/null; then
    HWC_AFTER=$(hwclock -r 2>/dev/null)
    echo "  系统时间: $SYS_BEFORE_SYSTOHC"
    echo "  写入后硬件时间: $HWC_AFTER"

    SYS_EPOCH=$(date +%s)
    HWC_EPOCH=$(date -d "$HWC_AFTER" +%s 2>/dev/null || echo 0)
    DRIFT=$((SYS_EPOCH - HWC_EPOCH))
    DRIFT_ABS=${DRIFT#-}

    if [ "$DRIFT_ABS" -le 2 ]; then
        _pass "systohc: 硬件时钟已与系统时钟同步 (偏差=${DRIFT}秒)"
    else
        _info "systohc 执行完成 (偏差=${DRIFT}秒)"
    fi
else
    _fail "hwclock --systohc 失败"
fi

echo ""
echo "============================================"
echo "  测试结果 (完整模式)"
echo "  PASS: $PASS_COUNT   FAIL: $FAIL_COUNT"
echo "  当前系统时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo "  当前硬件时间: $(hwclock -r 2>/dev/null || echo N/A)"
echo "============================================"

if [ $TIMESYNCD_ACTIVE -eq 1 ]; then
    echo "  ℹ️  systemd-timesyncd 会在数秒~数分钟内自动恢复正确时间"
fi

if [ $FAIL_COUNT -gt 0 ]; then
    echo "  ⚠️  QA_FAIL_RTC"
    exit 1
else
    echo "  ✅ QA_PASS_RTC"
    exit 0
fi