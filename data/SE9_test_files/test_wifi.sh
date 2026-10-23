#!/bin/bash
date

lspci -n | grep '10ec:'
if [ $? -ne 0 ];then
	echo "check wifi device failed"
	echo "QA_FAIL_WIFI"
	exit 1
fi

date
echo "QA_PASS_WIFI"
