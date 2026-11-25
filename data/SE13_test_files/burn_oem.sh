#!/bin/bash

# 平台通过 SSH 以 linaro 身份执行；需要 root 的脚本自动提权（sudo 密码固定 linaro）
if [ "$(id -u)" -ne 0 ]; then
    printf 'linaro\n' | sudo -S -p '' bash "$0" "$@"
    exit $?
fi
date
#用法：sudo ./burn_oen.sh <name> <value>
#例：sudo ./burn_oem.sh CHIP CV186AH

if [ $# -ne 2 ]; then
	echo "Please enter both the name and value of oem information"
	echo " For examle: ./burn_oem.sh CHIP CV186AH"
	echo "QA_FAIL_OEM"
	exit 1
else
	name=$1
	value=$2
fi


if [ $name == "SN0" ]; then
	w_value=$value
	addr=0
	count=32
	type="str"
elif [ $name == "SN1" ]; then
	w_value=$value
	addr=32
	count=32
	type="str"
elif [ $name == "MAC0" ]; then
	w_value=${value#0x}
	addr=64
	count=16
	type="hex"
elif [ $name == "MAC1" ]; then
	w_value=${value#0x}
	addr=80
	count=16
	type="hex"
elif [ $name == "PRODUCT_TYPE" ]; then
	w_value=${value#0x}
	addr=96
	count=16
	type="hex"
elif [ $name == "MODULE_TYPE" ]; then
	w_value=$value
	addr=112
	count=16
	type="str"
elif [ $name == "INTERFACE_FLAG" ]; then
	w_value=${value#0x}
	addr=128
	count=1
	type="hex"
elif [ $name == "AGING_FLAG" ]; then
	w_value=${value#0x}
	addr=129
	count=1
	type="hex"
elif [ $name == "VENDER" ]; then
	w_value=$value
	addr=144
	count=16
	type="str"
elif [ $name == "DTS_TYPE" ]; then
	w_value=$value
	addr=160
	count=32
	type="str"
elif [ $name == "HW_VERSION" ]; then
	w_value=$value
	addr=192
	count=16
	type="str"
elif [ $name == "PRODUCT" ]; then
	w_value=$value
	addr=208
	count=16
	type="str"
elif [ $name == "CHIP" ]; then
	w_value=$value
	addr=224
	count=16
	type="str"
else
	echo "This script does not support burning this information: $name"
	echo "QA_FAIL_OEM"
	exit 1
fi

echo "name: $name"
echo "value: $value"

echo 0 > /sys/block/mmcblk0boot1/force_ro
if [ $? -ne 0 ]; then
	echo "Unlock force_ro failed"
	echo "QA_FAIL_OEM"
	exit 1
fi

echo $w_value > ${name}.txt
if [ $type == "str" ]; then
	input_file=${name}.txt
elif [ $type == "hex" ]; then
	xxd -p -u -r ${name}.txt > ${name}.bin
	input_file=${name}.bin
fi

dd if=/dev/zero of=/dev/mmcblk0boot1 count=$count bs=1 seek=$addr
if [ $? -ne 0 ]; then
	echo "Erase $name failed"
	echo "QA_FAIL_OEM"
	exit 1
fi

dd if=$input_file of=/dev/mmcblk0boot1 count=$count bs=1 seek=$addr
if [ $? -ne 0 ]; then
	echo "Burn $name failed"
	echo "QA_FAIL_OEM"
	exit 1
fi

echo 1 > /sys/block/mmcblk0boot1/force_ro

/usr/sbin/read_oem.sh

r_value=$(grep -w $name /factory/OEMconfig.ini | awk '{print $3}')
if [ $r_value != $value ]; then
	echo "Verify $name failed"
	echo "QA_FAIL_OEM"
	exit 1
else
	echo "read $name: $r_value"
	echo "Verify $name successed"
fi

date
echo "QA_PASS_OEM"
