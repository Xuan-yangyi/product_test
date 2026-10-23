#!/bin/bash

# 设置日志文件
LOG_FILE="/var/log/echo_service.log"
exec > >(tee -a "$LOG_FILE") 2>&1

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1"
}

# 初始化函数
initialize_interfaces() {
    log "开始初始化接口..."

    # 初始化RS485
    log "初始化RS485接口..."
    cvi_pinmux -w UART1_TX/UART1_TX > /dev/null 2>&1
    cvi_pinmux -w UART1_RX/UART1_RX > /dev/null 2>&1
    stty -F /dev/ttyS1 115200 cs8 -cstopb -parenb -crtscts

    # 初始化RS232
    log "初始化RS232接口..."
    cvi_pinmux -w PWR_UART_TX/UART3_TX > /dev/null 2>&1
    cvi_pinmux -w PWR_UART_RX/UART3_RX > /dev/null 2>&1
    stty -F /dev/ttyS3 115200 cs8 -cstopb -parenb -crtscts

    # 初始化IN1/OUT1
    log "初始化IN1/OUT1接口..."
    cvi_pinmux -w I2S0_SCLK/GPIO0 > /dev/null 2>&1
    cvi_pinmux -w I2S0_SDI0/GPIO2 > /dev/null 2>&1
    echo 480 > /sys/class/gpio/export 2>/dev/null
    echo 482 > /sys/class/gpio/export 2>/dev/null
    echo out > /sys/class/gpio/gpio480/direction
    echo in > /sys/class/gpio/gpio482/direction

    # 初始化IN2/OUT2
    log "初始化IN2/OUT2接口..."
    cvi_pinmux -w I2S0_WSI/GPIO1 > /dev/null 2>&1
    cvi_pinmux -w I2S0_SDI1/GPIO3 > /dev/null 2>&1
    echo 481 > /sys/class/gpio/export 2>/dev/null
    echo 483 > /sys/class/gpio/export 2>/dev/null
    echo out > /sys/class/gpio/gpio481/direction
    echo in > /sys/class/gpio/gpio483/direction

    log "所有接口初始化完成"
}

# 清理函数
cleanup() {
    log "接收到停止信号，清理资源..."
    kill $RS232_PID $RS485_PID $GPIO_PID 2>/dev/null
    exit 0
}

# 设置信号处理
trap cleanup SIGTERM SIGINT

# 主函数
main() {
    log "启动回显服务..."

    # 初始化接口
    initialize_interfaces

    # RS232回显处理
    log "启动RS232回显..."
    while true; do
        if read -r -t 1 line < /dev/ttyS3; then
            log "RS232接收到: $line"
            echo "$line" > /dev/ttyS3
            log "RS232回显: $line"
        fi
    done &
    RS232_PID=$!

    # RS485回显处理
    log "启动RS485回显..."
    while true; do
        if read -r -t 1 line < /dev/ttyS1; then
            log "RS485接收到: $line"
            echo "$line" > /dev/ttyS1
            log "RS485回显: $line"
        fi
    done &
    RS485_PID=$!

    # GPIO回显处理
    log "启动GPIO回显..."
    (
        # 保存上一次的值
        LAST_IN1=""
        LAST_IN2=""

        while true; do
            # 读取IN1状态并设置OUT1
            IN1_VALUE=$(cat /sys/class/gpio/gpio482/value 2>/dev/null)
            if [ -n "$IN1_VALUE" ] && [ "$IN1_VALUE" != "$LAST_IN1" ]; then
                echo $IN1_VALUE > /sys/class/gpio/gpio480/value
                log "GPIO IN1->OUT1: $IN1_VALUE"
                LAST_IN1=$IN1_VALUE
            fi

            # 读取IN2状态并设置OUT2
            IN2_VALUE=$(cat /sys/class/gpio/gpio483/value 2>/dev/null)
            if [ -n "$IN2_VALUE" ] && [ "$IN2_VALUE" != "$LAST_IN2" ]; then
                echo $IN2_VALUE > /sys/class/gpio/gpio481/value
                log "GPIO IN2->OUT2: $IN2_VALUE"
                LAST_IN2=$IN2_VALUE
            fi

            sleep 0.1
        done
    ) &
    GPIO_PID=$!

    # 等待所有子进程
    wait
}

# 启动主函数
main
