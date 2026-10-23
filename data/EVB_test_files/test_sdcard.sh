#!/bin/bash
date

if [ $# -ne 1 ]; then
	echo "Please enter the device node name of the SDCard"
	echo "QA_FAIL_SDCARD"
	exit 1
else
	addr=$1
fi

if [ ! -b $addr ]; then
	echo "SDCard device does not exist"
	echo "QA_FAIL_SDCARD"
	exit 1
fi

all_part=$(fdisk -l $addr | grep "^$addr" | awk '{print $1}')
for partition in ${all_part[@]}
do
	sudo umount -f $partition
done

sudo umount -f $addr

sudo mkfs.vfat -F 32 $addr
if [ $? -ne 0 ];then
	echo "Failed to format SDCard"
	echo "QA_FAIL_SDCARD"
	exit 1
fi

echo "n
p
1


w
" | fdisk $addr && sudo mkfs.vfat -F 32 ${addr}p1
if [ $? -ne 0 ];then
	echo "SDCard partition failed"
	echo "QA_FAIL_SDCARD"
	exit 1
fi

mnt_addr=/media/SDtest
part_addr=${addr}p1
mkdir -p $mnt_addr
sudo mount $part_addr $mnt_addr
if [ $? -ne 0 ]; then
	echo "Failed to mount SDCard"
	echo "QA_FAIL_SDCARD"
	exit 1
fi

cp data.bin $mnt_addr
sync

diff data.bin $mnt_addr/data.bin
if [ $? -ne 0 ]; then
	echo "Failed to copy file to SDCard"
	echo "QA_FAIL_SDCARD"
	exit 1
fi

rm -rf $mnt_addr/data.bin
if [ $? -ne 0 ]; then
	echo "Failed to delete files from SDCard"
	echo "QA_FAIL_SDCARD"
	exit 1
fi
sync

sudo umount -f $part_addr
if [ $? -ne 0 ]; then
	echo "Failed to umount SDCard"
	echo "QA_FAIL_SDCARD"
	exit 1
fi

rm -rf $mnt_addr

date
echo "QA_PASS_SDCARD"
