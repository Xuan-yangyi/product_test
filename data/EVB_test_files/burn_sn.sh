#!/bin/bash
date

if [ $# -ne 1 ]; then
	echo "Please enter sn of EVB"
	echo "QA_FAIL_SN"
	exit 1
else
	device_sn=$1
fi

echo "device sn: $device_sn"

echo 0 > /sys/block/mmcblk0boot1/force_ro
if [ $? -ne 0 ]; then
	echo "Unlock force_ro failed"
	echo "QA_FAIL_SN"
	exit 1
fi

echo $device_sn > device_sn.txt
dd if=device_sn.txt of=/dev/mmcblk0boot1 count=17 bs=1 seek=0
if [ $? -ne 0 ]; then
	echo "Burn device sn failed"
	echo "QA_FAIL_SN"
	exit 1
fi

echo 1 > /sys/block/mmcblk0boot1/force_ro

/usr/sbin/read_oem.sh

r_device_sn=$(grep -w SN /factory/OEMconfig.ini | awk '{print $3}')
if [ $r_device_sn != $device_sn ]; then
	echo "Verify device sn failed"
	echo "QA_FAIL_SN"
	exit 1
else
	echo "read device sn: $r_device_sn"
	echo "Verify device sn successed"
fi

date
echo "QA_PASS_SN"
