#!/bin/bash
date

echo 0 > /sys/block/mmcblk0boot1/force_ro
if [ $? -ne 0 ]; then
	echo "Unlock force_ro failed"
	echo "QA_FAIL_INTERFACE_FLAG"
	exit 1
fi

echo 01 > interface_flag.txt
xxd -p -u -r interface_flag.txt > interface_flag.bin
dd if=interface_flag.bin of=/dev/mmcblk0boot1 count=1 bs=1 seek=128
if [ $? -ne 0 ]; then
	echo "set interface flag failed"
	echo "QA_FAIL_INTERFACE_FLAG"
	exit 1
fi

echo 1 > /sys/block/mmcblk0boot1/force_ro

/usr/sbin/read_oem.sh

r_interface_flag=$(grep -w INTERFACE_FLAG /factory/OEMconfig.ini | awk '{print $3}')
if [ $r_interface_flag != "0x01" ]; then
	echo "Verify interface flag failed"
	echo "QA_FAIL_INTERFACE_FLAG"
	exit 1
else
	echo "read interface flag: $r_interface_flag"
	echo "Verify interface flag successed"
fi

date
echo "QA_PASS_INTERFACE_FLAG"
