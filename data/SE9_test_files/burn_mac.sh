#!/bin/bash
date

if [ $# -ne 2 ]; then
	echo "Please enter both two mac addresses"
	echo "QA_FAIL_MAC"
	exit 1
else
	mac0=$1
	mac1=$2
fi

echo "mac0: $mac0"
echo "mac1: $mac1"

echo 0 > /sys/block/mmcblk0boot1/force_ro
if [ $? -ne 0 ]; then
	echo "Unlock force_ro failed"
	echo "QA_FAIL_MAC"
	exit 1
fi

echo $mac0 > mac0.txt
xxd -p -u -r mac0.txt > mac0.bin
dd if=mac0.bin of=/dev/mmcblk0boot1 count=6 bs=1 seek=64
if [ $? -ne 0 ]; then
	echo "Burn mac0 failed"
	echo "QA_FAIL_MAC"
	exit 1
fi

echo $mac1 > mac1.txt
xxd -p -u -r mac1.txt > mac1.bin
dd if=mac1.bin of=/dev/mmcblk0boot1 count=6 bs=1 seek=80
if [ $? -ne 0 ]; then
	echo "Burn mac1 failed"
	echo "QA_FAIL_MAC"
	exit 1
fi

echo 1 > /sys/block/mmcblk0boot1/force_ro

/usr/sbin/read_oem.sh

r_mac0=$(grep -w MAC0 /factory/OEMconfig.ini | awk '{print $3}')
if [ $r_mac0 != $mac0 ]; then
	echo "Verify mac0 failed"
	echo "QA_FAIL_MAC"
	exit 1
else
	echo "read mac0: $r_mac0"
	echo "Verify mac0 successed"
fi

r_mac1=$(grep -w MAC1 /factory/OEMconfig.ini | awk '{print $3}')
if [ $r_mac1 != $mac1 ]; then
	echo "Verify mac1 failed"
	echo "QA_FAIL_MAC"
	exit 1
else
	echo "read mac1: $r_mac1"
	echo "Verify mac1 successed"
fi

date
echo "QA_PASS_MAC"
