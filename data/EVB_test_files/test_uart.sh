#!/bin/bash
date

sudo chmod +x /usr/sbin/cvi_pinmux

# open uart1
cvi_pinmux -w UART1_TX/UART1_TX > /dev/null
cvi_pinmux -w UART1_RX/UART1_RX > /dev/null
stty -F /dev/ttyS1 115200 cs8 -cstopb -parenb -crtscts

# open pwr_uart
cvi_pinmux -w PWR_UART_TX/UART3_TX > /dev/null
cvi_pinmux -w PWR_UART_RX/UART3_RX > /dev/null
stty -F /dev/ttyS3 115200 cs8 -cstopb -parenb -crtscts

sleep 5

# check uart1 send to pwr_uart
cat /dev/ttyS3 &
pid_pwr_uart=$!
rx_pwr_uart_0=$(cat /proc/tty/driver/serial | grep "3:" | awk -F '[: ,]' '{ print $12 }')
echo 121212 > /dev/ttyS1
sleep 1
kill -9 $pid_pwr_uart
rx_pwr_uart_1=$(cat /proc/tty/driver/serial | grep "3:" | awk -F '[: ,]' '{ print $12 }')
bytes_pwr_uart=`expr $rx_pwr_uart_1 - $rx_pwr_uart_0`
if [ $bytes_pwr_uart -ne 8 ]; then
	echo "check uart1 send to pwr_uart failed"
	echo "QA_FAIL_UART"
	exit 1
fi

# check pwr_uart send to uart1
cat /dev/ttyS1 &
pid_uart1=$!
rx_uart1_0=$(cat /proc/tty/driver/serial | grep "1:" | awk -F '[: ,]' '{ print $12 }')
echo 343434 > /dev/ttyS3
sleep 1
kill -9 $pid_uart1
rx_uart1_1=$(cat /proc/tty/driver/serial | grep "1:" | awk -F '[: ,]' '{ print $12 }')
bytes_uart1=`expr $rx_uart1_1 - $rx_uart1_0`
if [ $bytes_uart1 -ne 8 ]; then
	echo "check pwr_uart send to uart1 failed"
	echo "QA_FAIL_UART"
	exit 1
fi

date
echo "QA_PASS_UART"
