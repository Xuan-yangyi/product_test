#!/bin/bash
date
echo "eth0 test start"
ip link set eth1 down
sleep 10
ping 192.168.1.1 -c 10
if [ $? -ne 0 ];then
	echo "eth0 test failed"
	echo "QA_FAIL_ETH"
	exit 1
fi

speed0=$(ethtool eth0 | grep Speed | awk '{print $2}')
echo "eth0 Speed=$speed0"
if [ $speed0 != "1000Mb/s" ];then
	echo "eth0 net speed check failed"
	echo "QA_FAIL_ETH"
	exit 1
fi

echo "eth0 test pass"

echo "eth1 test start"
ip link set eth0 down
ip link set eth1 up
dhclient eth1 -r
dhclient eth1
sleep 10
ping 192.168.1.1 -c 10
if [ $? -ne 0 ];then
  echo "eth1 test failed"
  echo "QA_FAIL_ETH"
  exit 1
fi

speed1=$(ethtool eth1 | grep Speed | awk '{print $2}')
echo "eth1 Speed=$speed1"
if [ $speed1 != "1000Mb/s" ];then
	echo "eth0 net speed check failed"
	echo "QA_FAIL_ETH"
	exit 1
fi

echo "eth1 test pass"

ip link set eth1 down
ip link set eth0 up
ip link set eth1 up

date
echo "QA_PASS_ETH"
