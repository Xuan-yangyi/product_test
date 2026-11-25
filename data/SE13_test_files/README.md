# SE13 基础接口测试脚本

> 快速功能验证，每个脚本 <1 分钟。稳定性压测见 `../stress/`。

## 脚本清单

| 脚本 | 接口 | 运行方式 | 接线要求 |
|------|------|---------|---------|
| `test_io.sh` | GPIO + Relay | 单板 `bash test_io.sh` | DO1↔DI1(Pin176↔184), DO2↔DI2(Pin180↔186) |
| `test_rs232.sh` | RS232 双板 | A端 `echo linaro \| sudo -S bash test_rs232.sh --mode tester [--baudrate 115200] [--batch]`; B端 `bash test_rs232.sh --mode server [--baudrate 115200]` | TX(Pin182)↔RX, RX(Pin178)↔TX 交叉 |
| `test_rs485.sh` | RS485 双板 | A端 `echo linaro \| sudo -S bash test_rs485.sh --mode tester [--baudrate 115200] [--batch]`; B端 `bash test_rs485.sh --mode server [--baudrate 115200]` | A↔A, B↔B 平行 |
| `test_can.sh` | CAN | 自测 `bash test_can.sh --mode loopback`; 双板 `--mode server\|tester` | H↔H, L↔L |
| `test_network.sh` | 以太网 | `bash test_network.sh` | eth0→路由器, eth1→PC直连 |
| `test_wifi.sh` | WiFi (PCIe) | `bash test_wifi.sh [-v] [--scan]` | WiFi天线连接 (扫描需要) |
| `test_memory_storage.sh` | eMMC/内存 | `bash test_memory_storage.sh` | 无 |
| `test_usb.sh` | USB | `bash test_usb.sh` | 插入U盘 |
| `test_usb_flash.sh` | USB 存储设备 (U盘/SD读卡器) | `bash test_usb_flash.sh [-v] [--size N]` | 插入USB存储设备 |
| `test_4g_modem.sh` | 4G 模块 (Fibocom/通用) | `bash test_4g_modem.sh [-v]` | 插入4G模块+SIM卡+天线 |
| `se13_usb_4g_combined.sh` | USB存储+4G模块 合体版 | `bash se13_usb_4g_combined.sh` | 同上 (自包含, 不依赖lib) |
| `test_ssd.sh` | NVMe/SATA SSD | `bash test_ssd.sh` | 安装SSD(裸盘自动分区+格式化) |
| `test_hdmi.sh` | HDMI | `bash test_hdmi.sh` | 接显示器(推荐); 无显示器仅测DRM |
| `test_hdmi_resolution.sh` | HDMI 分辨率切换 | `bash test_hdmi_resolution.sh [--readonly] [--quick]` | 必须接显示器 |
| `test_rtc.sh` | RTC/时间 | `bash test_rtc.sh [--full]` | 无 |
| `hw_status.sh` | 硬件状态采集 (11项) | `bash hw_status.sh [--json]` | 无 |

## 通用参数

| 参数 | 说明 |
|------|------|
| `--help, -h` | 显示帮助 |
| `--verbose, -v` | 详细输出 |

## 快速开始

```bash
# 全部单板测试 (跳过需 sudo 的 RTC 测试)
for t in test_io test_network test_memory_storage test_hdmi test_usb test_ssd; do
    echo "=== $t ===" && bash ${t}.sh 2>&1 | tail -3
done

# RTC 只读检查 (SE13 默认 root, 无需 sudo)
bash test_rtc.sh
```

## 逐脚本说明

### test_io.sh — GPIO + Relay

**测试内容**: GPIO DO↔DI 自回环电平验证, Relay GPIO92 toggle

**接线**: DO1(Pin176)→DI1(Pin184), DO2(Pin180)→DI2(Pin186) 杜邦线跳线

**运行**: `bash test_io.sh`

**判定**: `QA_PASS_IO` / `QA_FAIL_IO`

**原理**: sysfs export GPIO, DO 设为 out 并 toggle 0/1, DI 设为 in 后读取, 验证 DI 值与 DO 输出一致。Relay sysfs 444 toggle 后回读验证。

---

### test_rs232.sh — RS232 双板通信

**测试内容**: 两块 SE13 ttyS4 交叉互连, Server cat+kill 监听, Tester 验证 echo

**接线**: ttyS4 TX(Pin182)→对方RX, RX(Pin178)→对方TX (交叉)

**参数**:

| 参数 | 说明 |
|------|------|
| `--mode server\|tester` | 运行模式 (必选) |
| `--baudrate <rate>` | 波特率 (默认115200, 可选 9600~921600) |
| `--batch` | tester 下依次遍历 8 个波特率并汇总 |
| `--help, -h` | 显示帮助 |

**测试方法** (v3 cat+kill, 无 timeout fd 泄漏):
```bash
# B端 (Device B, root串口): 启动 server
bash test_rs232.sh --mode server --baudrate <rate>

# A端 (Device A, linaro SSH): 运行 tester (需 sudo)
echo linaro | sudo -S bash test_rs232.sh --mode tester --baudrate <rate>
```

**原理**: cat 后台监听 → kill cat 刷新缓冲区 → grep 检测测试帧/echo

**波特率矩阵** (8/8 ✅):

| 速率 | 结果 |
|------|------|
| 9600 | ✅ PASS |
| 19200 | ✅ PASS |
| 38400 | ✅ PASS |
| 57600 | ✅ PASS |
| 115200 | ✅ PASS |
| 230400 | ✅ PASS |
| 460800 | ✅ PASS |
| 921600 | ✅ PASS |

**判定**: `[PASS] RS232 <rate> bps PASS` — 收到 `232_rev_done`

---

### test_rs485.sh — RS485 双板通信

**测试内容**: 两块 SE13 ttyS2 平行互连, 半双工 cat+kill echo 回传

**接线**: ttyS2 A↔A, B↔B (平行, 半双工)

**参数**: 同 test_rs232.sh

**测试方法** (v3, server echo 前延时 0.5s 确保半双工收发切换):
```bash
# B端 (Device B, root串口): 启动 server
bash test_rs485.sh --mode server --baudrate <rate>

# A端 (Device A, linaro SSH): 运行 tester
echo linaro | sudo -S bash test_rs485.sh --mode tester --baudrate <rate>
```

**波特率矩阵** (8/8 ✅):

| 速率 | 结果 |
|------|------|
| 9600 | ✅ PASS |
| 19200 | ✅ PASS |
| 38400 | ✅ PASS |
| 57600 | ✅ PASS |
| 115200 | ✅ PASS |
| 230400 | ✅ PASS |
| 460800 | ✅ PASS |
| 921600 | ✅ PASS |

**注意**: RS485 半双工, server echo 前 0.5s 延时确保总线方向切换

---

### test_can.sh — CAN 通信

**测试内容**: CAN 帧收发, 支持 loopback 自测和双板通信

**自测 (无需接线)**:
```bash
bash test_can.sh --mode loopback
```
自动配置 can0 为 loopback 模式, 发送 `ID=0x55 data=0x12 0x23 0x34`, candump 接收验证。

**双板通信**:
```bash
# B端 (串口): candump 监听
ip link set can0 up type can bitrate 250000
candump can0

# A端 (SSH): 发送
bash test_can.sh --mode tester
```

**接线**: can0 H↔H, L↔L (凤凰端子 Pin14/16)

**判定**: `QA_PASS_CAN` — 收到回环帧 / `QA_FAIL_CAN`

**注意**: SE13 cansend 语法为 `cansend <iface> -i <ID> <hex bytes>`, candump 无 `-n` 选项。

---

### test_network.sh — 以太网

**测试内容**: eth0/eth1 连通性、速率、IP 配置

**运行**: `bash test_network.sh`

**自动检测**:
1. 获取默认网关 (`ip route | grep default`)
2. eth0 ping 网关 10 次 → 0% loss PASS
3. eth1 NO-CARRIER 自动跳过, 有 CARRIER 则 ping
4. ethtool 验证 Speed=1000Mb/s
5. 检查当前 IP (DHCP/静态)

**手动命令**:
```bash
# DHCP
dhclient eth0
# 静态IP
ip addr add 10.80.40.31/24 dev eth0
# 查看IP
ip addr show eth0
# eth1 直连 PC 测试
ping -c5 -I eth1 192.168.150.223
```

**判定**: `QA_PASS_NETWORK` / `QA_FAIL_NETWORK`

---

### test_wifi.sh — WiFi (PCIe)

**测试内容**: PCIe WiFi 模块检测、驱动加载、接口验证、up/down、(可选)扫描

**运行**: `bash test_wifi.sh [-v] [--scan]`

**参数**:

| 参数 | 说明 |
|------|------|
| `--help, -h` | 显示帮助 |
| `--verbose, -v` | 详细输出 |
| `--scan` | 额外执行 WiFi 扫描 (需安装 `iw`) |

**测试流程** (4-5 项):

| # | 测试项 | 验证方法 |
|---|--------|---------|
| 1 | PCIe WiFi 模块检测 | `lspci` 匹配 Realtek 8852BE / Intel AX210 |
| 2 | 驱动加载 | `sudo insmod` 对应 .ko 文件, `lsmod` 验证 |
| 3 | 接口验证 | `ip link show` 查 wlp1s0, 记录 MAC |
| 4 | 接口 up/down | `sudo ip link set wlp1s0 up/down`, 检查 state |
| 5 | 网络扫描 (可选) | `iw dev wlp1s0 scan` (需 --scan 参数) |

**支持的模块和驱动路径**:

| 模块 | lspci ID | 驱动 |
|------|---------|------|
| Realtek 8852BE | b852 | `/mnt/system/ko/3rd/8852be.ko` `rtw_country_code=US` |
| Intel AX210 | ax210/iwl | `/mnt/system/ko/iwlwifi.ko` + `iwlmvm.ko` |

**前置条件**:
- WiFi 天线已连接 (硬件)
- `sudo` 权限 (密码 `linaro`)
- `lspci` 可用
- (可选) `iw` 已安装 (`apt install iw`)

**注意**:
- 接口 UP 后可能因 rfkill 或未配置 wpa_supplicant 而保持 DOWN，属正常
- 驱动路径脚本自动搜索 `/mnt/system/ko/3rd/` 和 `/lib/modules/`

**判定**: `QA_PASS_WIFI` — 模块检测+驱动加载+接口出现 / `QA_FAIL_WIFI`

**实测数据** (10.80.40.68, Realtek 8852BE):

| 项目 | 数据 |
|------|------|
| lspci | `01:00.0 Network controller: Realtek b852` |
| 驱动 | `8852be.ko` (10.5MB) |
| 接口 | `wlp1s0` |
| MAC | `44:90:ba:24:71:48` |

---

### test_memory_storage.sh — eMMC + 内存

**测试内容**: eMMC 分区容量、内存容量、基本读写

**运行**: `bash test_memory_storage.sh`

**自动检测**:
1. eMMC: `df -h | grep mmcblk0p5/p6` → p5≥6GB, p6≥15GB
2. 内存: `free -h` → 检测总容量
3. 读写: dd bs=1M count=10 写入+读取
4. 异常: dmesg 检查 OOM 历史

**eMMC 随机读写**:
```bash
# 自动
bash test_memory_storage.sh   # 包含 dd 随机读写测试
# 手工 fio
fio --filename=/tmp/emmc_test --direct=1 --rw=randrw --bs=4k --size=100M --name=test
```

**判定**: `QA_PASS_MEMORY_STORAGE` / `QA_FAIL_MEMORY_STORAGE`

---

### test_usb.sh — USB

**测试内容**: USB 控制器检测、设备枚举、存储设备挂载读写、文件系统检查、热插拔历史

**运行**: `bash test_usb.sh`

**测试流程** (6 项, v2):

| # | 测试项 | 验证方法 |
|---|--------|---------|
| 1 | USB 控制器检测 | `lsusb` 检查 USB 控制器是否正常初始化 |
| 2 | USB 设备枚举 | 列出所有非 root hub 设备 (VID:PID), 统计数量 |
| 3 | USB 存储设备检测 | `lsblk` + `/sys/block/sd*/removable` 检测 U 盘, 记录容量 |
| 4 | USB 挂载读写 | dd 写入 10MB → sync → md5 → 读取验证 → md5 二次校验 |
| 5 | 文件系统检查 | `fsck -n` 只读检查 (支持 vfat/ext4/ntfs) |
| 6 | USB 热插拔历史 | `dmesg` 查询最近 10 条 USB 连接/断开事件 |

**兼容策略**:
- **自动挂载设备** (如 `/media/storage-hot-sda1`): 先 umount 自动挂载点 → 手动 mount → 测试 → umount 清理
- **无自动挂载**: 手动 mount → 测试 → umount
- **无 U 盘**: 控制器检测通过, 存储测试 SKIP

**快速验证命令**:
```bash
# SSH 远程执行
sshpass -p 'linaro' ssh linaro@<ip> 'bash -s' < test_usb.sh

# 或部署后执行
bash test_usb.sh -v
```

**判定**: `QA_PASS_USB` — 有 U 盘时 6 项全通过 / `QA_SKIP_USB` — 无 U 盘, 控制器检测通过

**已知问题**:
- USB 2.0 Flash Drive + FAT32 写入较慢, dd 不使用 `conv=fsync` (改为 dd 后 `sync`)
- 自动挂载守护进程可能会在 umount 后重新挂载, 不影响测试

**实际测试数据** (10.80.40.42, SanDisk Cruzer Blade 29.3G):

| 项目 | 数据 |
|------|------|
| USB 控制器 | `xhci-hcd` x2 (USB 2.0 + USB 3.1) |
| 设备 | `0781:5567 SanDisk Corp. Cruzer Blade` |
| 分区 | `/dev/sda1` FAT32 (UUID=6792-FAE2) |
| 自动挂载点 | `/media/storage-hot-sda1` |
| 容量 | 29.3 GiB (61341696 sectors × 512B) |

---

### test_usb_flash.sh — USB 存储设备 (U盘/SD读卡器)

**测试内容**: USB 存储设备检测、分区识别、挂载点验证、dd 读写、文件系统检查

**运行**: `bash test_usb_flash.sh [-v] [--size N]`

**参数**:

| 参数 | 说明 |
|------|------|
| `--help, -h` | 显示帮助 |
| `--verbose, -v` | 详细输出 |
| `--size N` | dd 写入大小 MB (默认 10) |

**测试流程** (5 项):

| # | 测试项 | 验证方法 |
|---|--------|---------|
| 1 | USB 控制器检测 | `lsusb` 检查 USB 控制器 |
| 2 | USB 存储设备枚举 | `lsblk -o TRAN=usb` + removable flag |
| 3 | 分区与挂载点 | `blkid` 分区类型 + `mount` 挂载点 |
| 4 | dd 读写验证 | dd 10MB 写入 → sync → md5 → 读取 |
| 5 | 文件系统检查 | `fsck -n` 只读检查 (vfat/ext4) |

**兼容策略**:
- **自动挂载设备** (如 `/media/storage-hot-sda1`): 直接使用已有挂载点
- **无自动挂载**: 手动 mount → 测试 → umount
- **无 USB 存储设备**: 控制器检测 PASS，其余 SKIP

**判定**: `QA_PASS_USB_FLASH` / `QA_FAIL_USB_FLASH`

> 与 `test_usb.sh` 的区别: `test_usb_flash.sh` 专注于 USB 存储设备的挂载读写验证，不包含热插拔历史和通用 USB 设备枚举。`test_usb.sh` 覆盖更广（包含鼠标键盘等 HID 设备），但存储测试深度相同。

---

### test_4g_modem.sh — 4G 模块 (Fibocom/通用 AT 指令)

**测试内容**: 4G 模块 USB 枚举、AT 端口检测、SIM 卡状态、信号强度、网络注册、运营商信息

**运行**: `bash test_4g_modem.sh [-v]`

**前置条件**:
- 4G 模块已插入 USB 口并上电
- SIM 卡已插入
- 天线已连接 (信号测试需要)

**参数**:

| 参数 | 说明 |
|------|------|
| `--help, -h` | 显示帮助 |
| `--verbose, -v` | 详细输出 (含 AT 原始响应) |

**测试流程** (7 项):

| # | 测试项 | AT 指令 | 验证方法 |
|---|--------|---------|---------|
| 1 | 模块 USB 检测 | — | `lsusb` 匹配 Fibocom/Sierra/Huawei/Quectel 等 |
| 2 | ttyUSB 端口枚举 | — | `ls /dev/ttyUSB*` 统计端口数 |
| 3 | AT 基础指令 | `AT` | 返回 `OK`；`ATI` 厂商信息；`AT+CGSN` IMEI |
| 4 | SIM 卡状态 | `AT+CPIN?` | 返回 `READY` (SIM 正常) |
| 5 | 信号强度 | `AT+CSQ` | 解析 RSSI (0-31=有信号, 99=无信号) |
| 6 | 网络注册 | `AT+CREG?` | stat=1(已注册归属)/5(已注册漫游) |
| 7 | 运营商信息 | `AT+COPS?` | 提取运营商名称 |

**AT 端口探测**: 脚本自动遍历 `/dev/ttyUSB*` 发送 `AT` 检测 `OK` 响应来定位 AT 端口。Fibocom L610 典型端口分配: ttyUSB0=DM, ttyUSB1=GPS, ttyUSB2=AT, ttyUSB3=PPP。

**RSSI 解读**:

| RSSI | 信号强度 | dBm 范围 |
|------|---------|---------|
| 0-9 | 弱 | ≤-97 dBm |
| 10-19 | 中 | -93 ~ -73 dBm |
| 20-31 | 强 | ≥-69 dBm |
| 99 | 无信号 | 未知/未检测 |

**判定**: `QA_PASS_4G_MODEM` — 模块枚举正常 + AT 指令响应 OK + SIM READY / `QA_FAIL_4G_MODEM`

> **常见问题排查**:
> - `lsusb` 无模块: 检查模块是否上电、USB 线是否插好
> - AT 无响应: 尝试其他 ttyUSB 端口，确认模块未进入休眠
> - SIM 非 READY: 检查 SIM 卡方向、是否欠费、PIN 码状态
> - RSSI=99: 检查天线是否连接、是否在信号覆盖区

---

### se13_usb_4g_combined.sh — 合体版 (自包含)

**测试内容**: 上述两个测试的合并版本，**不依赖 lib/test_common.sh**，适合通过串口直接运行。

**运行**: `bash se13_usb_4g_combined.sh`

**适用场景**: 跳板机串口连接时，将单个脚本 base64 上传后直接运行，无需处理库依赖。

**判定**: `QA_PASS_SE13_USB_4G` — 两个模块均无 FAIL / `QA_FAIL_SE13_USB_4G`

---

### test_ssd.sh — NVMe/SATA SSD

**测试内容**: SSD 检测、自动分区初始化、挂载读写

**运行**: `bash test_ssd.sh`

**自动流程**:
1. 检测 `/dev/nvme0n1` → 有分区直接挂载, 无分区自动 `fdisk + mkfs.ext4` 初始化
2. 挂载后 dd bs=1M count=100 写入+读取
3. 5 轮挂载-读写-卸载循环

**手动分区** (裸盘):
```bash
echo -e "n\np\n1\n\n\nw" | fdisk /dev/nvme0n1
mkfs.ext4 -F /dev/nvme0n1p1
mount /dev/nvme0n1p1 /mnt/ssd
```

**判定**: `QA_PASS_SSD` — 检测+挂载+读写全部通过 / `QA_SKIP_SSD` — 无 SSD (含详细日志)

---

### test_hdmi.sh — HDMI 显示

**测试内容**: DRM 设备检测、连接状态、驱动模块

**运行**: `bash test_hdmi.sh`

**自动检测**:
1. `/dev/dri/` — DRM 设备存在性
2. `/sys/class/drm/card0-*/status` — HDMI 连接状态 (connected/disconnected)
3. `/dev/fb0` — Framebuffer 设备
4. lsmod — 检查 soph_drm 驱动加载

**无显示器**: DRM 设备+驱动验证通过, 显示输出跳过

**判定**: `QA_PASS_HDMI` — DRM 正常 / `QA_SKIP_HDMI` — 无显示器

---

### test_hdmi_resolution.sh — HDMI 分辨率切换

**测试内容**: HDMI 显示器在不同分辨率模式下的显示能力验证

**运行**:
```bash
# 完整测试 (sysfs 只读 + fbset 模式切换)
bash test_hdmi_resolution.sh

# 只读检查 (不执行分辨率切换)
bash test_hdmi_resolution.sh --readonly

# 快速模式 (仅测试最佳+最低分辨率)
bash test_hdmi_resolution.sh --quick
```

**自动检测**:
1. HDMI 连接状态 (`/sys/class/drm/card0-HDMI-A-1/status`)
2. 分辨率模式枚举 (34 种模式，来自显示器 EDID)
3. EDID 元数据解析 (厂商/产品/年份/checksum 验证)
4. 当前显示模式读取 (sysfs mode / fbset)
5. 分辨率切换 (需要 fbset，逐一切换→读回验证→恢复最佳)

**无显示器**: 所有测试标记 SKIP

**无 fbset**: Phase 2 (模式切换) 标记 SKIP，Phase 1 (只读检查) 正常执行

**平台适配** (SE13 BM1688 实测):
- `fbset` 默认不可用 → 模式切换测试自动 SKIP
- sysfs `mode` 文件不存在 (cvitek DRM 未暴露)
- EDID 解析正常 (厂商=DEL, 产品=8204, 年份=2021)
- modes 文件格式为 `WxH` (无刷新率字段)

**判定**: `QA_PASS_HDMI_RESOLUTION` — 只读检查全部通过 / `QA_SKIP_HDMI_RESOLUTION` — 无显示器

---

### test_rtc.sh — RTC/时间 基础功能

**测试内容**: 验证系统时间/时区/硬件时钟的读取、手动设置、软硬件时钟互相同步共 8 项操作。

**平台适配** (SE13 实测):
- 系统为 root, 无需 `sudo`
- **无 `ntpdate`** — 改用 `timedatectl` 检测 systemd-timesyncd 状态
- `/etc/timezone` (=Etc/UTC) 与 `timedatectl` (=Asia/Shanghai) 可能不一致 — **以 timedatectl 为准**
- --full 模式修改时间后, systemd-timesyncd 会在数秒~数分钟内自动恢复正确时间, 无需手动干预

**运行**:

```bash
# 只读检查 (默认, 不修改时间)
bash test_rtc.sh

# 完整测试 (含写入和同步操作, systemd-timesyncd 自动恢复)
bash test_rtc.sh --full
```

**8 项测试明细**:

| # | 测试项 | 命令 | 默认 | --full | SE13 实测 |
|---|--------|------|------|--------|-----------|
| 1 | 查看系统时间 | `date`, `date -Iseconds` | ✅ | ✅ | `Thu Nov  5 14:25:42 CST 2026` |
| 2 | 查看系统时区 | `timedatectl show Timezone` / `date +%Z` | ✅ | ✅ | `Asia/Shanghai` |
| 3 | 查看硬件时间 | `hwclock -r` | ✅ | ✅ | `2026-11-05 14:26:26+08:00` |
| 4 | 网络时间同步状态 | `timedatectl show --property=NTP` | ✅ | ✅ | `yes` (systemd-timesyncd) |
| 5 | 手动设置系统时间 | `date -s "2026-01-01 12:00:00"` | ❌ | ✅ | 设置成功, date 跳变 |
| 6 | 手动设置硬件时间 | `hwclock --set --date="2026-01-01 12:00:00"` | ❌ | ✅ | 设置成功, hwclock -r 确认 |
| 7 | 硬件时钟→系统时钟 | `hwclock --hctosys` | ❌ | ✅ | 执行成功; timesyncd 可能立刻修正回当前时间 (预期行为) |
| 8 | 系统时钟→硬件时钟 | `hwclock --systohc` | ❌ | ✅ | 执行成功, hwclock -r 确认同步 |

**前置依赖**:
- `hwclock` 命令 (util-linux, 系统自带)
- `timedatectl` (systemd, 系统自带)
- root 权限 (SE13 默认 root)

**无接线要求** — 纯软件测试。

**判定**:
- 默认模式: `QA_PASS_RTC` (1-4 项全部通过) / `QA_FAIL_RTC`
- --full 模式: `QA_PASS_RTC` (8 项全部通过) / `QA_FAIL_RTC`

**手工逐项命令速查**:

```bash
# 1. 查看系统时间
date
date -Iseconds

# 2. 查看系统时区 (以 timedatectl 为准)
timedatectl show --property=Timezone --value
date +%Z

# 3. 查看硬件时间
hwclock -r

# 4. 网络时间同步状态
timedatectl show --property=NTP

# 5. 手动设置系统时间
date -s "2026-01-01 12:00:00"

# 6. 手动设置硬件时间
hwclock --set --date="2026-01-01 12:00:00"

# 7. 硬件时钟 → 系统时钟
hwclock --hctosys

# 8. 系统时钟 → 硬件时钟
hwclock --systohc
```

---

### hw_status.sh — 硬件状态采集

**测试内容**: 一键采集 CPU/NPU/内存/存储/温度/占用率共 10 项硬件状态, 用于验收前快速巡检和故障定位。

**采样项目**:

| 类别 | 采样项 | 数据源 |
|------|--------|--------|
| 存储 | eMMC 生命周期/容量 | `/sys/block/mmcblk0/device/life_time` |
| 存储 | NVMe SSD 健康/容量 | `nvme smart-log /dev/nvme0` |
| 存储 | TF 卡检测 | `/dev/mmcblk1*` |
| 内存 | 内存总量/使用率 | `free -h` |
| 内存 | ION 内存占用 | `/sys/kernel/debug/ion/` |
| CPU | 温度 | `/sys/class/thermal/thermal_zone*/temp` |
| CPU | 使用率 | `top -bn1` |
| NPU | 芯片温度 | `/proc/bmsophon/<card>/<chip>/chip_temp` |
| NPU | 板卡温度 | `/proc/bmsophon/<card>/board_temp` |
| NPU | 板卡功耗 | `/proc/bmsophon/<card>/board_power` |
| NPU | TPU 功耗/频率 | `/proc/bmsophon/<card>/<chip>/tpu_power` `/tpu_freq` |
| NPU | NPU 占用率 | `/sys/class/bm-sophon/bm-sophon0/device/npu_usage` |
| 板级 | 加热电阻温度 | 自动扫描 `/sys/class/hwmon/` `/sys/bus/i2c/` 等路径 |

**运行**: `bash hw_status.sh`

**前置依赖**:
- `soph_base.ko` + `soph_sys.ko` 已加载
- bm-sophon 驱动已加载 (NPU/板卡数据依赖)
- `nvme` 命令可用 (SSD 健康数据依赖)
- debugfs 已挂载: `mount -t debugfs none /sys/kernel/debug` (ION 数据依赖)

**无接线要求** — 纯软件读取, 单板即可运行。

**输出示例**:
```
=============== SE13 硬件状态 ===============
时间: 2026-11-05 10:30:00

--- 存储 ---
  eMMC 生命周期: 0x01 0x01
  NVMe SSD 健康: critical_warning: 0, temperature: 38°C, percentage_used: 0%
  TF卡: 未插入

--- 内存 ---
Mem:          2.6Gi       312Mi       1.8Gi       3.0Mi       556Mi       2.1Gi
  ION 内存: ION debugfs 不可用

--- CPU ---
  CPU 温度: soc_thermal_0=42000°mC  soc_thermal_1=43500°mC  soc_thermal_2=41000°mC
  CPU 使用率: CPU: 2% usr 1% sys 0% nic 96% idle 0% io 0% irq 0% sirq

--- NPU ---
  NPU 芯片温度: 45 C
  板卡温度: 38 C
  板卡功耗: 12 W
  TPU 功耗: 8.5
  TPU 频率: 900
  NPU 占用率: 0%

--- 加热电阻温度 ---
  未找到加热电阻温度接口 (需板端确认)
```

**判定**: 无统一的 PASS/FAIL — 脚本用于信息采集, 由验收人员逐项对照预期范围判断。异常项标注 `N/A` 并提示原因 (驱动未加载 / 命令缺失 / 接口不可用)。