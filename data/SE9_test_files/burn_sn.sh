#!/bin/bash
date

# 检查参数数量
if [ "$#" -ne 2 ]; then
	echo "Usage: $0 <board_sn> <device_sn>"
	echo "Both parameters must be either a 17-character alphanumeric string or 'None'."
	echo "QA_FAIL_SN"
	exit 1
fi

# 检查board_sn参数
if ! [[ $1 =~ ^[a-zA-Z0-9]{17}$ || $1 == "None" ]]; then
	echo "Error: board_sn must be a 17-character alphanumeric string or 'None'."
	echo "QA_FAIL_SN"
	exit 1
fi
board_sn=$1

# 检查device_sn参数
if ! [[ $2 =~ ^[a-zA-Z0-9]{17}$ || $2 == "None" ]]; then
	echo "Error: device_sn must be a 17-character alphanumeric string or 'None'."
	echo "QA_FAIL_SN"
	exit 1
fi
device_sn=$2

echo "board sn: $board_sn"
echo "device sn: $device_sn"

echo 0 > /sys/block/mmcblk0boot1/force_ro
if [ $? -ne 0 ]; then
	echo "Unlock force_ro failed"
	echo "QA_FAIL_SN"
	exit 1
fi

if [ "$board_sn" != "None" ]; then
	echo $board_sn > board_sn.txt
	dd if=board_sn.txt of=/dev/mmcblk0boot1 count=17 bs=1 seek=0
	if [ $? -ne 0 ]; then
		echo "Burn board sn failed"
		echo "QA_FAIL_SN"
		exit 1
	fi
fi

if [ "$device_sn" != "None" ]; then
	echo $device_sn > device_sn.txt
	dd if=device_sn.txt of=/dev/mmcblk0boot1 count=17 bs=1 seek=32
	if [ $? -ne 0 ]; then
		echo "Burn device sn failed"
		echo "QA_FAIL_SN"
		exit 1
	fi
fi

echo 1 > /sys/block/mmcblk0boot1/force_ro

/usr/sbin/read_oem.sh

if [ "$board_sn" != "None" ]; then
	r_board_sn=$(grep -w SN /factory/OEMconfig.ini | awk '{print $3}')
	if [ $r_board_sn != $board_sn ]; then
		echo "Verify board sn failed"
		echo "QA_FAIL_SN"
		exit 1
	else
		echo "read board sn: $r_board_sn"
		echo "Verify board sn successed"
	fi
fi

if [ "$device_sn" != "None" ]; then
	r_device_sn=$(grep -w DEVICE_SN /factory/OEMconfig.ini | awk '{print $3}')
	if [ $r_device_sn != $device_sn ]; then
		echo "Verify device sn failed"
		echo "QA_FAIL_SN"
		exit 1
	else
		echo "read device sn: $r_device_sn"
		echo "Verify device sn successed"
	fi
fi

date
echo "QA_PASS_SN"
