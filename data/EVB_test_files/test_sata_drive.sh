#!/bin/bash
date

if [ $# -ne 1 ]; then
	echo "Please enter the number of hard drives"
	echo "QA_FAIL_SATA_DRIVE"
	exit 1
else
	drive_num=$1
fi

all_disk=$(ls /dev/ | grep ^sd[a-f]$)
drive_cnt=0
for device in ${all_disk[@]}
do
	echo "Current device: $device"
	remove_flag=$(cat /sys/block/$device/removable)
	if [ $remove_flag -ne 0 ];then
		echo "$device is not a hard drive, continue"
		continue
	fi
	echo "$device is a hard drive"
	drive_addr=/dev/$device
	all_part=$(fdisk -l $drive_addr | grep "^$drive_addr" | awk '{print $1}')
	for partition in ${all_part[@]}
	do
		sudo umount -f $partition
	done

	sudo umount -f $drive_addr

	sudo mkfs.ext4 -F $drive_addr
	if [ $? -ne 0 ];then
		echo "Failed to format hard drive"
		echo "QA_FAIL_SATA_DRIVE"
		exit 1
	fi

	echo "n
	p
	1


	w
	" | fdisk $drive_addr && sudo mkfs.ext4 -F ${drive_addr}1
	if [ $? -ne 0 ];then
		echo "Hard drive partition failed"
		echo "QA_FAIL_SATA_DRIVE"
		exit 1
	fi

	part_addr=${drive_addr}1
	mnt_addr=/media/SATAtest
	mkdir -p $mnt_addr
	sudo mount -t ext4 $part_addr $mnt_addr
	if [ $? -ne 0 ];then
		echo "Failed to mount hard drive"
		echo "QA_FAIL_SATA_DRIVE"
		exit 1
	fi

	cp data.bin $mnt_addr
	sync

	diff data.bin $mnt_addr/data.bin
	if [ $? -ne 0 ]; then
		echo "Failed to copy file to hard drive"
		echo "QA_FAIL_SATA_DRIVE"
		exit 1
	fi

	rm -rf $mnt_addr/data.bin
	if [ $? -ne 0 ]; then
		echo "Failed to delete files from hard drive"
		echo "QA_FAIL_SATA_DRIVE"
		exit 1
	fi
	sync

	sudo umount -f $part_addr
	if [ $? -ne 0 ]; then
		echo "Failed to umount hard drive"
		echo "QA_FAIL_SATA_DRIVE"
		exit 1
	fi

	rm -rf $mnt_addr

	let drive_cnt+=1
done

if [ $drive_cnt -ne $drive_num ];then
	echo "The number of hard drives is not $drive_num"
	echo "QA_FAIL_SATA_DRIVE"
	exit 1
fi

date
echo "QA_PASS_SATA_DRIVE"
