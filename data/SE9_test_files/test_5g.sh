#!/bin/bash
date

lsusb | grep '1e0e:'
if [ $? -ne 0 ];then
	echo "check 5g device failed"
	echo "QA_FAIL_5G"
	exit 1
fi

date
echo "QA_PASS_5G"
