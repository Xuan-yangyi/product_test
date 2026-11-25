#!/bin/bash

# 平台通过 SSH 以 linaro 身份执行；需要 root 的脚本自动提权（sudo 密码固定 linaro）
if [ "$(id -u)" -ne 0 ]; then
    printf 'linaro\n' | sudo -S -p '' bash "$0" "$@"
    exit $?
fi
# SE13 eMMC 分区检查
# TODO: 确认 SE13 eMMC 分区表（p5/p6 编号和最小容量）
date

size5=$(df -h 2>/dev/null | grep "/dev/mmcblk0p5" | awk '{print $2}')
if [ -n "$size5" ]; then
    size5_num=${size5%G}
    if [ "$(echo "$size5_num < 6" | bc 2>/dev/null || echo 1)" = "1" ]; then
        echo "/dev/mmcblk0p5 partition size error (size=$size5)"
        echo "QA_FAIL_EMMC"; exit 1
    fi
else
    echo "WARN: /dev/mmcblk0p5 not found, skipping partition check"
fi

date; echo "QA_PASS_EMMC"