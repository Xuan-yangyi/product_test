#!/bin/bash
date

size5=$(df -h | grep /dev/mmcblk0p5 | awk '{print $2}')
size5_num=${size5%G}

if [ `echo "$size5_num < 8" | bc` -eq 1 ]; then
	echo "/dev/mmcblk0p5 partition size error"
	echo "QA_FAIL_EMMC"
	exit 1
fi

size6=$(df -h | grep /dev/mmcblk0p6 | awk '{print $2}')
size6_num=${size6%G}

if [ `echo "$size6_num < 16" | bc` -eq 1 ]; then
	echo "/dev/mmcblk0p6 partition size error"
	echo "QA_FAIL_EMMC"
	exit 1
fi

date
echo "QA_PASS_EMMC"
