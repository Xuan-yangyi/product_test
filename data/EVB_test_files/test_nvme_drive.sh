#!/bin/bash
date

if [ $# -ne 1 ]; then
	echo "Please enter the number of hard drives"
	echo "QA_FAIL_NVME_DRIVE"
	exit 1
else
	drive_num=$1
fi

all_disk=$(ls /dev/ | grep ^nvme[0-9]$)
drive_cnt=0
for device in ${all_disk[@]}
do
	echo "Current device: $device"
	drive_addr=/dev/${device}n1
	sudo umount -f $drive_addr

	sudo mkfs.ext4 -F $drive_addr
	if [ $? -ne 0 ];then
		echo "Failed to format hard drive"
		echo "QA_FAIL_NVME_DRIVE"
		exit 1
	fi

	mnt_addr=/media/NVMEtest
	mkdir -p $mnt_addr
	sudo mount -t ext4 $drive_addr $mnt_addr
	if [ $? -ne 0 ];then
		echo "Failed to mount hard drive"
		echo "QA_FAIL_NVME_DRIVE"
		exit 1
	fi

	cp data.bin $mnt_addr
	sync

	diff data.bin $mnt_addr/data.bin
	if [ $? -ne 0 ]; then
		echo "Failed to copy file to hard drive"
		echo "QA_FAIL_NVME_DRIVE"
		exit 1
	fi

	rm -rf $mnt_addr/data.bin
	if [ $? -ne 0 ]; then
		echo "Failed to delete files from hard drive"
		echo "QA_FAIL_NVME_DRIVE"
		exit 1
	fi
	sync

	sudo umount -f $drive_addr
	if [ $? -ne 0 ]; then
		echo "Failed to umount hard drive"
		echo "QA_FAIL_NVME_DRIVE"
		exit 1
	fi

	rm -rf $mnt_addr

	let drive_cnt+=1
done

if [ $drive_cnt -ne $drive_num ];then
	echo "The number of hard drives is not $drive_num"
	echo "QA_FAIL_NVME_DRIVE"
	exit 1
fi

date
echo "QA_PASS_NVME_DRIVE"
