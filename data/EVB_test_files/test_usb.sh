#!/bin/bash
date

if [ $# -ne 1 ]; then
	echo "Please enter the number of USB flash drives"
	echo "QA_FAIL_USB"
	exit 1
else
	usb_num=$1
fi

all_disk=$(ls /dev/|grep ^sd[a-f]$)
usb_cnt=0
for device in ${all_disk[@]}
do
	echo "Current device: $device"
	remove_flag=$(cat /sys/block/$device/removable)
	if [ $remove_flag -ne 1 ];then
		echo "$device is not a USB flash drive, continue"
		continue
	fi
	echo "$device is a USB flash drive"
	usb_addr=/dev/$device
	all_part=$(fdisk -l $usb_addr | grep "^$usb_addr" | awk '{print $1}')
	for partition in ${all_part[@]}
	do
		sudo umount -f $partition
	done

	sudo umount -f $usb_addr

	sudo mkfs.ext4 -F $usb_addr
	if [ $? -ne 0 ];then
		echo "Failed to format USB flash drive"
		echo "QA_FAIL_USB"
		exit 1
	fi

	echo "n
	p
	1


	w
	" | fdisk $usb_addr && sudo mkfs.ext4 -F ${usb_addr}1
	if [ $? -ne 0 ];then
		echo "USB flash drive partition failed"
		echo "QA_FAIL_USB"
		exit 1
	fi

	part_addr=${usb_addr}1
	mnt_addr=/media/USBtest
	mkdir -p $mnt_addr
	sudo mount -t ext4 $part_addr $mnt_addr
	if [ $? -ne 0 ];then
		echo "Failed to mount USB flash drive"
		echo "QA_FAIL_USB"
		exit 1
	fi

	cp data.bin $mnt_addr
	sync

	diff data.bin $mnt_addr/data.bin
	if [ $? -ne 0 ]; then
		echo "Failed to copy file to USB flash drive"
		echo "QA_FAIL_USB"
		exit 1
	fi

	rm -rf $mnt_addr/data.bin
	if [ $? -ne 0 ]; then
		echo "Failed to delete files from USB flash drive"
		echo "QA_FAIL_USB"
		exit 1
	fi
	sync

	sudo umount -f $part_addr
	if [ $? -ne 0 ]; then
		echo "Failed to umount USB flash drive"
		echo "QA_FAIL_USB"
		exit 1
	fi

	rm -rf $mnt_addr

	let usb_cnt+=1
done

if [ $usb_cnt -ne $usb_num ];then
	echo "The number of USB flash drives is not $usb_num"
	echo "QA_FAIL_USB"
	exit 1
fi

date
echo "QA_PASS_USB"
