# Athena2 Web Product Test

> 嵌入式设备产测工具 — 从 QT 桌面应用迁移至 Web 网页方式，支持 SE9/SE12/EVB 等 CVITEK 芯片平台。


[![Release](https://img.shields.io/badge/release-v2.0.1-blue)](https://github.com/Xuan-yangyi/product_test/releases)
[![Main](https://img.shields.io/badge/main-development-orange)](https://github.com/Xuan-yangyi/product_test)

> **生产部署（Release）**: `git clone https://github.com/Xuan-yangyi/product_test.git && cd product_test && git checkout v2.0.1 && ./init.sh`
>
> **开发调试（main）**: `git clone https://github.com/Xuan-yangyi/product_test.git && cd product_test && ./init.sh`

> ⚠️ **老化测试**: Release 不包含老化二进制（约 5.2GB），请从 [Wiki](https://wiki.sophgo.com/pages/viewpage.action?pageId=163064732) 下载并解压到 `data/AGING_test_files/soc_aging/`。

## 架构

```
product_test/
├── backend/          # FastAPI 后端 (Python)
│   ├── api/          # REST API 路由
│   ├── engine/       # SSH/串口/SCP 设备通信层
│   ├── models/       # SQLAlchemy 数据模型
│   ├── services/     # 业务逻辑层
│   └── tests/        # 后端测试
├── frontend/         # Vue 3 + Element Plus 前端
│   └── src/
│       ├── api/      # HTTP 客户端
│       ├── components/ # 公共组件
│       ├── views/    # 页面视图
│       └── stores/   # Pinia 状态管理
├── cfg/              # 测试配置（产品型号、测试用例）
├── data/             # 运行时数据（SQLite 数据库、SN 抓拍图）
├── mediamtx.yml      # MediaMTX 配置（WebRTC 预览中继）
└── start.sh          # 一键启动脚本（前端构建 + MediaMTX + 后端）
```

## 技术栈

| 层级 | 技术 |
|------|------|
| 前端 | Vue 3, Element Plus, Pinia, ECharts, Vite |
| 后端 | Python 3.10+, FastAPI, uvicorn |
| 数据库 | SQLite (SQLAlchemy ORM) |
| 设备通信 | paramiko (SSH), pyserial (串口) |
| 实时推送 | WebSocket |
| 预览中继 | MediaMTX (RTMP → WebRTC) |
| AI 分析 | DeepSeek API + Claude CLI |

## 功能特性

- **多平台支持**：SE9 (linaro)、SE12、EVB 等 CVITEK 芯片平台
- **测试类型**：老化测试、reboot 测试、CPU/DPU/JPU/TPU/VPU 模块测试
- **集群老化**：多设备并行老化测试，统一管理
- **实时监控**：WebSocket 实时推送测试步骤、日志、状态
- **系统日志**：通过 SSH + journalctl 实时采集设备系统日志
- **AI 分析**：快速分析（DeepSeek API）/ 深度分析（Claude CLI）
- **历史数据**：SQLite 存储全部测试结果，支持多条件查询和统计
- **SN 抓拍**：SE9 识别到 SN 时抓取设备图入库，前端按 SN / 日期查询查看（详见下方「SN 抓拍」节）
- **调机预览**：板子双路相机实时画面中继到网页，调镜头时用（详见下方「调机预览」节）
- **暗色主题**：亮色/暗色主题切换

---

## 环境部署

### 环境要求

- Python 3.10+
- Node.js 18+ / npm 9+
- MediaMTX（WebRTC 预览用，见下方 §MediaMTX 部署）

### 1. 克隆 + 安装依赖

```bash
git clone git@github.com:Xuan-yangyi/product_test.git
cd product_test

# 后端依赖
cd backend && pip install -r requirements.txt && cd ..

# 前端依赖
cd frontend && npm install && cd ..

# AI 分析配置（可选）
cp cfg/ai_config.json.example cfg/ai_config.json
# 编辑 cfg/ai_config.json，填入 API 地址和密钥
```

### 2. MediaMTX 部署

调机预览链路是：**板子 ffmpeg 推 RTMP → 本机 MediaMTX 转 WebRTC → 浏览器 `<video>`**。MediaMTX 做纯协议转换（零编码），由 `start.sh` 自动拉起。

**安装（仅首次，本机 x86_64）**：

```bash
cd /tmp && wget https://github.com/bluenviron/mediamtx/releases/download/v1.8.0/mediamtx_v1.8.0_linux_amd64.tar.gz
sudo mkdir -p /opt/mediamtx && sudo tar xzf mediamtx_v1.8.0_linux_amd64.tar.gz -C /opt/mediamtx/
```

**配置 `mediamtx.yml`（可修改说明）**：

```yaml
rtmp: yes
rtmpAddress: :1935          # 板子推流入口；改端口要同步改板子侧 deploy/preview_supervisor.sh 的 RTMP 目标
webrtc: yes
webrtcAddress: :8889        # 浏览器 WHEP 端点；改端口要同步改 backend/api/camera.py 的 WHEP 代理目标
api: yes                    # :9997，查流状态：curl 127.0.0.1:9997/v3/paths/list
srt: no                     # 故意关掉，避端口 8000 冲突
logLevel: info
paths:
  cam_front:                # 增加相机就加一个 path
    source: publisher
    sourceOnDemand: no      # 常驻等推流（no = 不按需启动）
  cam_back:
    source: publisher
    sourceOnDemand: no
```

> 改任意端口/path 后，板子侧推流地址与后端 WHEP 代理目标要对应改。板子侧部署见 SN 抓拍板子仓库（链接见下方「SN 抓拍」节）。

### 3. 启动

```bash
# 开发模式（前后端分离，热重载）
cd backend && python3 -m uvicorn main:app --host 0.0.0.0 --port 8080 --reload   # 终端1
cd frontend && npm run dev                                                       # 终端2，端口 5173

# 生产模式（一键：构建前端 + 起 MediaMTX + 起后端 :8099）
chmod +x start.sh && ./start.sh
```

`start.sh` 依次做：① `npm run build` 构建前端 → ② `pkill -f mediamtx` 后用 `mediamtx.yml` 起 MediaMTX（`trap` 随脚本退出清理）→ ③ `uvicorn backend.main:app --port 8099`。
日志：MediaMTX → `mediamtx_run.log`，后端 → `uvicorn_8099.log`。

---

## SN 抓拍

SE9 识别到设备 SN 时，把 **SN + 命中帧设备图**推送到本系统入库；前端「SN 抓拍」页按 **SN + 入库日期范围**查询查看。v2.1 起支持正/反两面（一次命中同时抓正、背两张图，前端一张卡片并排显示）。该特性加法式，独立于老化测试。

- **落盘**：图片 `data/sn_captures/<SN>/<时间戳>_<side>.<jpg|png>`；元数据入 `data/results.db` 的独立表 `sn_captures`。
- **上传接口**：`POST /api/v1/captures`（multipart：`sn` 必填、`score`、`ts`、`side`、`image`）。
- **查询接口**：`GET /api/v1/captures`（`sn` / `start` / `end` / `limit` / `offset`）、`GET /api/v1/captures/{id}/image`。

> **板子侧（抓拍来源）部署与原理**不在本仓库，见 SN 抓拍板子端项目：
> <https://github.com/jokerliu223/sn_monitor_bm1688>
> 该仓库 README 讲板子侧环境部署、相机接法、systemd 单元、IP 改动对照；DB 表字段、`side` 列升级（`ALTER TABLE`）等细节见其 `docs/features/dual-camera.md`。

---

## 调机预览

前端「调机预览」页把板子两路相机的实时画面中继到网页，用来**调镜头位置/焦距**。链路：

```
浏览器 <video>  ←WebRTC←  本机 MediaMTX :8889  ←RTMP←  板子 ffmpeg(h264_bm)  ←RTSP←  相机
```

后端只做 WHEP 代理（`/api/v1/camera/webrtc/*` → `127.0.0.1:8889`），不让浏览器直连板子——板子网段对办公网不直接暴露，中继后换调机电脑零配置。板子地址默认 `http://10.80.40.68:8090`（环境变量 `PREVIEW_BOARD_BASE` 可覆盖，见下方 IP 表）。

### 相关 API

| 路径 | 方法 | 说明 |
|------|------|------|
| `/api/v1/camera/webrtc/config` | GET | 返回 WebRTC 配置 |
| `/api/v1/camera/webrtc/whep/{cam}` | POST | WHEP 代理：转发浏览器 SDP offer 到本地 MediaMTX |
| `/api/v1/camera/status` | GET | 双路相机状态 |
| `/api/v1/camera/latest-capture` | GET | 板子最近一次抓拍元信息（只读回显） |

> ⚠️ **中继路由必须用异步生成器**：`backend/api/camera.py` 的 MJPEG 中继路由与内部生成器必须 `async def` + `httpx.AsyncClient`，关闭上游用 `anyio.CancelScope(shield=True)`。写成同步生成器会在浏览器断开时泄漏上游连接，实测可把服务器拖死（soft lockup）。改这块时不要退回同步写法。

---

## API 概览

| 路径 | 方法 | 说明 |
|------|------|------|
| `/api/v1/tests` | GET/POST | 测试任务管理 |
| `/api/v1/tests/{id}/start` | POST | 启动测试 |
| `/api/v1/tests/{id}/stop` | POST | 停止测试 |
| `/api/v1/results` | GET | 查询历史结果 |
| `/api/v1/results/statistics` | GET | 结果统计 |
| `/api/v1/results/{id}/logs` | GET | 获取老化日志 |
| `/api/v1/results/{id}/syslog` | GET | 获取系统日志 |
| `/api/v1/ai/chat` | POST | AI 对话 |
| `/api/v1/ai/analyze/{id}` | POST | AI 快速分析 |
| `/api/v1/ai/claude-analyze/{id}` | POST | Claude 深度分析 |
| `/api/v1/cluster` | GET/POST | 集群管理 |
| `/api/v1/captures` | GET/POST | SN 抓拍（见上） |
| `/api/v1/camera/*` | GET/POST | 调机预览（见上） |
| `/api/v1/ws/{test_id}` | WebSocket | 实时推送 |

## 配置说明

测试配置位于 `cfg/` 目录：

- `test_case_config.ini` — 测试用例定义（步骤、参数、超时）
- `ui_config.ini` — 前端页面配置（步骤标签、分组）
- `show_config.ini` — 显示控制（哪些步骤需要展示）
- `SE9_cfg/` / `SE12_cfg/` / `EVB_cfg/` — 各平台配置文件
- `ai_config.json` — AI 分析配置（API 地址、密钥、模型）
- `network_config.yaml` — 产测网段

详细配置格式见各文件注释。

---

## IP / 配置改动对照表

| 改什么 | 文件 : 位置 | 现默认值 | 备注 |
|--------|-------------|----------|------|
| **板子 IP（预览中继源）** | `backend/api/camera.py:35` | `http://10.80.40.68:8090` | 环境变量 `PREVIEW_BOARD_BASE` 可覆盖；**此值为预览链路实际连的板子** |
| **后端监听端口** | `start.sh` 末行（生产）/ uvicorn 命令（开发） | `8099`（开发 `8080`） | |
| **前端开发端口** | Vite 默认 `5173`（未在 `vite.config.ts` 显式设置） | `5173` | 仅开发模式 |
| **前端→后端代理目标（开发）** | `frontend/vite.config.ts`（`server.proxy` 的 `/api`、`/ws`） | `http://localhost:8080` | 改开发后端端口要同步改这里 |
| **MediaMTX 端口** | `mediamtx.yml` | RTMP `:1935` / WebRTC `:8889` / API `:9997` | 改端口要同步改板子侧推流 + 后端 WHEP 代理 |
| **集群 / 接口测试扫描网段** | `frontend/src/views/ClusterAgingView.vue`<br>`frontend/src/views/InterfaceTestView.vue` | `10.80.40.1` ~ `10.80.40.254` | 扫描表单默认值 |
| **产测网段** | `cfg/network_config.yaml` | `192.168.1.0` | |

> **换 MediaMTX / 本服务器 IP**：本机 IP（`.57`）本身不写在本仓库，而写在**板子侧**仓库：RTMP 推流目标在 `deploy/preview_supervisor.sh`，上传目标在 `deploy/sn-uploader.service` / `tools/sn_uploader.py`。换服务器要改板子那边。

## License

Internal use — CVITEK.
