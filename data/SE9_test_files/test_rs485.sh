#!/bin/bash
date

# 初始化RS485
initialize_rs485() {
    echo "初始化RS485接口..."
    cvi_pinmux -w UART1_TX/UART1_TX > /dev/null 2>&1
    cvi_pinmux -w UART1_RX/UART1_RX > /dev/null 2>&1
    stty -F /dev/ttyS1 115200 cs8 -cstopb -parenb -crtscts
    exec 3<> "/dev/ttyS1"
    sleep 1
}

# 测试RS485
test_rs485() {
    echo "开始RS485测试..."

    # 测试数据
    TEST_DATA="RS485_TEST"

    # 发送测试数据
    echo "发送测试数据: $TEST_DATA"
    echo "$TEST_DATA" >&3

    # 等待并读取回显
    sleep 0.5
    if read -r -t 2 -u 3 response; then
        receive_data=$(echo "$response" | tr -d '\r')
        echo "接收到回显: $receive_data"

        # 验证回显
        if [ "$receive_data" = "$TEST_DATA" ]; then
            echo "RS485测试成功!"
            return 0
        else
            echo "RS485测试失败: 回显数据不匹配"
            return 1
        fi
    else
        echo "RS485测试失败: 未接收到回显"
        return 1
    fi
}

# 主函数
main() {
    echo "开始RS485接口测试"

    # 初始化接口
    initialize_rs485

    # 执行测试
    if test_rs485; then
        echo "QA_PASS_RS485"
        exec 3<&-
        date
        exit 0
    else
        echo "QA_FAIL_RS485"
        exec 3<&-
        exit 1
    fi
}

# 启动主函数
main
