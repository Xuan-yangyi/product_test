#!/bin/bash
date

sudo chmod +x /usr/sbin/cvi_pinmux

# open 485
cvi_pinmux -w UART1_TX/UART1_TX > /dev/null
cvi_pinmux -w UART1_RX/UART1_RX > /dev/null
stty -F /dev/ttyS1 115200 cs8 -cstopb -parenb -crtscts

# open 232
cvi_pinmux -w PWR_UART_TX/UART3_TX > /dev/null
cvi_pinmux -w PWR_UART_RX/UART3_RX > /dev/null
stty -F /dev/ttyS3 115200 cs8 -cstopb -parenb -crtscts

# open can
ip link set can0 up type can bitrate 250000

sleep 5

# check can send to 485/232
cat /dev/ttyS1 &
pid_485=$!
cat /dev/ttyS3 &
pid_232=$!
rx_485_0=$(cat /proc/tty/driver/serial | grep "1:" | awk -F '[: ,]' '{ print $12 }')
rx_232_0=$(cat /proc/tty/driver/serial | grep "3:" | awk -F '[: ,]' '{ print $12 }')
cansend can0 -i 0x00 0x31 0x32 0x31 0x32 0x0a 0x0d
sleep 1
kill -9 $pid_485
kill -9 $pid_232
rx_485_1=$(cat /proc/tty/driver/serial | grep "1:" | awk -F '[: ,]' '{ print $12 }')
rx_232_1=$(cat /proc/tty/driver/serial | grep "3:" | awk -F '[: ,]' '{ print $12 }')
bytes_can_485=`expr $rx_485_1 - $rx_485_0`
bytes_can_232=`expr $rx_232_1 - $rx_232_0`
if [ $bytes_can_485 -ne 6 ]; then
	echo "check can send to 485 failed"
	echo "QA_FAIL_PHOENIX"
	exit 1
fi
if [ $bytes_can_232 -ne 6 ]; then
	echo "check can send to 232 failed"
	echo "QA_FAIL_PHOENIX"
	exit 1
fi

# check 485/232 send to can
ifconfig can0 down
ifconfig can0 up
candump can0 &
busybox devmem 0x292400a0 8 0x7
sleep 1
busybox devmem 0x292400a0 8 0
pid_can=$!
rx_can_0=$(ifconfig can0 | grep "RX packets" | awk '{print $5}')
echo 121212 > /dev/ttyS1
sleep 1
rx_can_1=$(ifconfig can0 | grep "RX packets" | awk '{print $5}')
echo 343434 > /dev/ttyS3
sleep 1
kill -9 $pid_can
rx_can_2=$(ifconfig can0 | grep "RX packets" | awk '{print $5}')
bytes_485_can=`expr $rx_can_1 - $rx_can_0`
bytes_232_can=`expr $rx_can_2 - $rx_can_1`
if [ $bytes_485_can -ne 8 ]; then
	echo "check 485 send to can failed"
	echo "QA_FAIL_PHOENIX"
	exit 1
fi
if [ $bytes_232_can -ne 8 ]; then
	echo "check 232 send to can failed"
	echo "QA_FAIL_PHOENIX"
	exit 1
fi

# initialize relay
cvi_pinmux -w PAD_VIVO0_D13/GPIO131
echo 355 > /sys/class/gpio/export
echo out > /sys/class/gpio/gpio355/direction
echo 0 > /sys/class/gpio/gpio355/value

# open IN1/OUT1
cvi_pinmux -w I2S0_SCLK/GPIO0
cvi_pinmux -w I2S0_SDI0/GPIO2
echo 480 > /sys/class/gpio/export
echo 482 > /sys/class/gpio/export
echo out > /sys/class/gpio/gpio480/direction
echo in > /sys/class/gpio/gpio482/direction

# check IN1/OUT1
echo 1 > /sys/class/gpio/gpio480/value
ret11=$(cat /sys/class/gpio/gpio482/value)
if [ $ret11 -ne 1 ]; then
	echo "check IN1/OUT1 failed"
	echo "QA_FAIL_PHOENIX"
	exit 1
fi
echo 0 > /sys/class/gpio/gpio480/value
ret10=$(cat /sys/class/gpio/gpio482/value)
if [ $ret10 -ne 0 ]; then
	echo "check IN1/OUT1 failed"
	echo "QA_FAIL_PHOENIX"
	exit 1
fi

# open IN2/OUT2
cvi_pinmux -w I2S0_WSI/GPIO1
cvi_pinmux -w I2S0_SDI1/GPIO3
echo 481 > /sys/class/gpio/export
echo 483 > /sys/class/gpio/export
echo out > /sys/class/gpio/gpio481/direction
echo in > /sys/class/gpio/gpio483/direction

# check IN1/OUT1
echo 1 > /sys/class/gpio/gpio481/value
ret21=$(cat /sys/class/gpio/gpio483/value)
if [ $ret21 -ne 1 ]; then
	echo "check IN2/OUT2 failed"
	echo "QA_FAIL_PHOENIX"
	exit 1
fi
echo 0 > /sys/class/gpio/gpio481/value
ret20=$(cat /sys/class/gpio/gpio483/value)
if [ $ret20 -ne 0 ]; then
	echo "check IN2/OUT2 failed"
	echo "QA_FAIL_PHOENIX"
	exit 1
fi

# check relay
for i in {1..3}; do
	echo 1 > /sys/class/gpio/gpio355/value
	sleep 1
	echo 0 > /sys/class/gpio/gpio355/value
	sleep 0.5
done

date
echo "QA_PASS_PHOENIX"
