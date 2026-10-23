#!/bin/bash
date

# 初始化GPIO
initialize_gpio() {
    echo "初始化GPIO接口..."

    # 初始化IN1/OUT1
    cvi_pinmux -w I2S0_SCLK/GPIO0 > /dev/null 2>&1
    cvi_pinmux -w I2S0_SDI0/GPIO2 > /dev/null 2>&1
    echo 480 > /sys/class/gpio/export 2>/dev/null
    echo 482 > /sys/class/gpio/export 2>/dev/null
    echo out > /sys/class/gpio/gpio480/direction
    echo in > /sys/class/gpio/gpio482/direction

    # 初始化IN2/OUT2
    cvi_pinmux -w I2S0_WSI/GPIO1 > /dev/null 2>&1
    cvi_pinmux -w I2S0_SDI1/GPIO3 > /dev/null 2>&1
    echo 481 > /sys/class/gpio/export 2>/dev/null
    echo 483 > /sys/class/gpio/export 2>/dev/null
    echo out > /sys/class/gpio/gpio481/direction
    echo in > /sys/class/gpio/gpio483/direction

    sleep 1
}

# 测试单个IO通道
test_io_channel() {
    local out_gpio=$1
    local in_gpio=$2
    local channel_name=$3

    echo "测试$channel_name..."

    # 测试高电平
    echo 1 > /sys/class/gpio/gpio$out_gpio/value
    sleep 0.2
    local in_value=$(cat /sys/class/gpio/gpio$in_gpio/value)

    if [ "$in_value" != "1" ]; then
        echo "$channel_name 高电平测试失败: 输出=1, 输入=$in_value"
        return 1
    fi

    # 测试低电平
    echo 0 > /sys/class/gpio/gpio$out_gpio/value
    sleep 0.2
    in_value=$(cat /sys/class/gpio/gpio$in_gpio/value)

    if [ "$in_value" != "0" ]; then
        echo "$channel_name 低电平测试失败: 输出=0, 输入=$in_value"
        return 1
    fi

    echo "$channel_name 测试成功"
    return 0
}

# 主函数
main() {
    echo "开始IO接口测试"

    # 初始化接口
    initialize_gpio

    # 测试所有IO通道
    local success=0
    local total=0

    if test_io_channel 480 482 "OUT1->IN1"; then
        ((success++))
    fi
    ((total++))

    if test_io_channel 481 483 "OUT2->IN2"; then
        ((success++))
    fi
    ((total++))

    # 输出测试结果
    if [ $success -eq $total ]; then
        echo "QA_PASS_IO"
        exit 0
    else
        echo "QA_FAIL_IO"
        exit 1
    fi
}

# 启动主函数
main
