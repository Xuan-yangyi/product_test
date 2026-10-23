#!/bin/bash
date

pushd test_4g

function test_fail()
{
	echo "QA_FAIL_4G"
	exit 1
}

lsusb | grep "1508:"
if [ $? -ne 0 ]; then
	echo "check 4g device failed"
	test_fail
fi

sudo ifconfig eth0 down && sudo ifconfig eth1 down
if [ $? -ne 0 ]; then
	echo "pull down eth0&eth1 failed"
	test_fail
fi

sudo systemctl start lteModemManager
if [ $? -ne 0 ]; then
	echo "start 4g service failed"
	test_fail
fi
sleep 20

values=$(sudo python3 get_signal.py)
if [ $? -ne 0 ]; then
	echo "4g signal check failed"
	test_fail
fi

values=(${values})
echo "signal strength: ${values[0]}"
echo "signal quality:  ${values[1]}"
echo "signal power:    ${values[2]}"
signal_flag=0
if [ "${values[0]}" -lt 20 -o "${values[0]}" -gt 31 ]; then
   echo "signal strength anomaly"
   signal_flag=1
elif [ "${values[1]}" -lt 20 -o "${values[1]}" -gt 34 ]; then
   echo "signal strength anomaly"
   signal_flag=1
elif [ "${values[2]}" -lt 50 -o "${values[2]}" -gt 97 ]; then
   echo "signal strength anomaly"
   signal_flag=1
fi

if [ $signal_flag -ne 0 ]; then
	test_fail
fi

ping 8.8.8.8 -c 10
if [ $? -ne 0 ]; then
	sudo systemctl restart lteModemManager
	if [ $? -ne 0 ]; then
		echo "restart 4g service failed"
		test_fail
	fi
	sleep 20
	ping 8.8.8.8 -c 10
	if [ $? -ne 0 ]; then
		echo "4g network test failed"
		test_fail
	fi
fi

sudo systemctl stop lteModemManager
if [ $? -ne 0 ]; then
	echo "stop 4g service failed"
	test_fail
fi

sudo ifconfig eth0 up && sudo ifconfig eth1 up
if [ $? -ne 0 ]; then
	echo "pull up eth0&eth1 failed"
	test_fail
fi

popd
date
echo "QA_PASS_4G"
