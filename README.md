# Athena2 Web Product Test

> 嵌入式设备产测工具 — 从 QT 桌面应用迁移至 Web 网页方式，支持 SE9/SE12/EVB 等 CVITEK 芯片平台。

## 架构

```
web_product_test/
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
├── data/             # 运行时数据（SQLite 数据库）
├── log/              # 测试日志
└── start.sh          # 一键启动脚本
```

## 技术栈

| 层级 | 技术 |
|------|------|
| 前端 | Vue 3, Element Plus, Pinia, ECharts, Vite |
| 后端 | Python 3.10+, FastAPI, uvicorn |
| 数据库 | SQLite (SQLAlchemy ORM) |
| 设备通信 | paramiko (SSH), pyserial (串口) |
| AI 分析 | DeepSeek API + Claude CLI |
| 实时推送 | WebSocket |

## 功能特性

- **多平台支持**：SE9 (linaro)、SE12、EVB 等 CVITEK 芯片平台
- **测试类型**：老化测试、reboot 测试、CPU/DPU/JPU/TPU/VPU 模块测试
- **集群老化**：多设备并行老化测试，统一管理
- **实时监控**：WebSocket 实时推送测试步骤、日志、状态
- **系统日志**：通过 SSH + journalctl 实时采集设备系统日志
- **AI 分析**：
  - 快速分析（DeepSeek API）— 错误检测、温度分析、性能评估
  - 深度分析（Claude CLI）— 全面日志审查、优化建议
- **历史数据**：SQLite 存储全部测试结果，支持多条件查询和统计
- **SN 抓拍**：SE9 识别到 SN 时抓取设备图入库，前端按 SN / 日期查询并查看
- **调机预览**：板子双路相机实时 MJPEG 画面中继到网页，调镜头时用；只读回显最近抓拍
- **暗色主题**：支持亮色/暗色主题切换

## 快速开始

### 环境要求

- Python 3.10+
- Node.js 18+
- npm 9+

### 1. 克隆仓库

```bash
git clone git@github.com:Xuan-yangyi/product_test.git
cd product_test
```

### 2. 安装后端依赖

```bash
cd backend
pip install -r requirements.txt
```

### 3. 配置 AI 分析（可选）

```bash
cp cfg/ai_config.json.example cfg/ai_config.json
# 编辑 cfg/ai_config.json，填入 API 地址和密钥
```

### 4. 安装前端依赖

```bash
cd frontend
npm install
```

### 5. 启动开发环境

```bash
# 终端 1 — 启动后端 (端口 8080)
cd backend
python3 -m uvicorn main:app --host 0.0.0.0 --port 8080 --reload

# 终端 2 — 启动前端 (端口 5173)
cd frontend
npm run dev
```

### 6. 生产部署

```bash
chmod +x start.sh
./start.sh
```

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
| `/api/v1/ws/{test_id}` | WebSocket | 实时推送 |

## 配置说明

测试配置位于 `cfg/` 目录：

- `test_case_config.ini` — 测试用例定义（步骤、参数、超时）
- `ui_config.ini` — 前端页面配置（步骤标签、分组）
- `show_config.ini` — 显示控制（哪些步骤需要展示）
- `SE9_cfg/` — SE9 平台配置文件
- `ai_config.json` — AI 分析配置（API 地址、密钥、模型）

详细配置格式见各文件注释。

## SN 抓拍（设备图片内容）

SE9 识别到设备 SN 时，把 **SN + 命中帧设备图**推送到本系统入库；前端「SN 抓拍」页可按
**SN + 入库日期范围**查询并查看对应设备图。该特性完全加法式，独立于老化测试（不改
`db_models.py` / `TestRecord` / 老化视图）。

> **v2.1 正/反两面**：SE9 侧可再加一路背面摄像头，一次命中同时抓正、背两张图（同一
> `captured_at`）。上传时多带一个 `side` 字段（`front` / `back`），DB 一行一图，前端按
> `(sn, captured_at)` 归组、**一张卡片并排显示正/背**。旧客户端不带 `side` 也能传，默认按
> 正面处理，完全向后兼容。

### 图片与数据的落盘位置 / 形式

| 内容 | 路径 / 形式 |
|------|-------------|
| 图片文件 | `data/sn_captures/<SN>/<时间戳>_<side>.<jpg\|png>`（按 SN 分目录，一张一文件；`side` 为 `front`/`back`，同一命中正反同秒也不会互相覆盖） |
| 数据库 | `data/results.db`（与老化共用同一 SQLite），独立表 **`sn_captures`** |
| DB 中的图片引用 | 表字段 `image_path` 只存**相对 DATA_DIR 的路径**，取图接口据此拼绝对路径返回文件 |

`sn_captures` 表字段：

| 字段 | 含义 |
|------|------|
| `id` | 主键 |
| `sn` | 设备序列号（索引） |
| `image_path` | 设备图相对路径（相对 `data/`） |
| `score` | 识别置信度 |
| `captured_at` | SE9 实际抓拍时间（板子时钟，可能为空） |
| `source` | 来源，默认 `SE9` |
| `side` | v2.1 正/反面：`front` \| `back`，默认 `front`（旧数据/旧客户端不带即正面） |
| `uploaded_at` | 入库时间（服务器时钟，自动，永不为空）——**日期范围筛选即按此字段** |

> ⚠️ **升级已有部署时需一次性补列**：`side` 是新增列，而 SQLAlchemy 的 `create_all` **只建表不做 ALTER**，
> 已有 `data/results.db` 不会自动多出这一列，接口会报 `no such column: sn_captures.side`。升级步骤：
> ```bash
> cp data/results.db data/results.db.bak_$(date +%Y%m%d_%H%M%S)   # 先备份
> sqlite3 data/results.db "ALTER TABLE sn_captures ADD COLUMN side VARCHAR(8) NOT NULL DEFAULT 'front';"
> ```
> 已存在的行会取默认值 `front`，正好等价于"老数据都是正面"，无需回填。

### 相关 API（均为新增，加法式）

| 路径 | 方法 | 说明 |
|------|------|------|
| `/api/v1/captures` | POST | SE9 上传：multipart `sn`(必填)、`score`、`ts`、`side`(v2.1，`front`/`back`，缺省 `front`；未知值兜底 `front` 不报错)、`image`(jpeg/png, <20MB) |
| `/api/v1/captures` | GET | 查询：`sn`、`start`/`end`(入库日期 YYYY-MM-DD，含当天)、`limit`、`offset`；返回 `{total, items[...image_url, uploaded_at]}` |
| `/api/v1/captures/{id}/image` | GET | 返回该条抓拍的设备图文件 |

## 调机预览（双路摄像头实时画面）

前端「调机预览」页把板子上两路摄像头的实时画面中继到网页，用来**调镜头位置/焦距**；
页面底部只读回显板子最近一次抓拍，方便核对识别结果。与 SN 抓拍一样是**加法式**特性，
不落库、不写文件、不碰 `sn_results`。

### 链路

```
浏览器 <img>  ←→  .57 :8099 /api/v1/camera/stream  ←→  板子 :8090 /stream  ←→  相机
   (同源)                (本模块，纯转发)                  (MJPEG 生成)      (RTSP)
```

中继一跳而不让浏览器直连板子：板子网段对办公网不直接暴露、直连要额外开跨域，
每换一台调机电脑都得改配置。中继后浏览器只说同源的话，换电脑零配置。

板子地址默认 `http://10.80.40.53:8090`，换板子时设环境变量 `PREVIEW_BOARD_BASE` 覆盖。

### 板子侧服务

预览**内嵌在识别服务里**（`sn_monitor.py` + `sn_preview_embed.py`），与 SN 识别
**同进程、共享同一路相机解码**。相机是**单客户端源**，多开一路 RTSP 会把原来那路踢死，
所以共享解码是硬约束，不是优化。

```bash
# 起停预览 = 起停识别服务（无需单独操作预览）
sudo systemctl restart sn-monitor-big     # big 档
sudo systemctl status  sn-monitor-big
tail -f /data/soph_SN/logs/sn_monitor.service.log
```

板子侧详细说明见板子 `/data/soph_SN/README.md` 与同目录 `preview_service_README.md`。
V1/V2 的独立预览服务 `preview_service.py` 已停用保留（不部署）。

### 分辨率档位与延迟

档位 `4k` / `1080p` / `720p` / `360p`，**默认 1080p**，页面上可随时切换
（切档会调 `/api/v1/camera/resolution` 并强制前端重连流）。

| 档位 | 带宽（单路） | 编码耗时 | 实测观感延迟 |
|------|-------------|---------|-------------|
| 4K | ~84 Mbps | ~178 ms/帧（≈5.7 fps，受编码限制未达 8 fps 上限） | 约 1.5–2 s |
| 1080p | ~4.3 MB/s | ~130 ms/帧（≈7.7 fps） | 约 1 s |

> **延迟是链路固有成本，不是缺陷。** 构成：板子解码+JPEG 编码（130–178 ms）
> + 板子→.57 传输（1080p 约 0.4 s）+ 浏览器多部分解码与缓冲。
> 默认取 1080p 是因为它在「细节够核对 SN」和「基本实时」之间最平衡；
> 要看清铭牌小字时临时切 4K，看完切回即可。

### 前端重连机制

`<img>` 一旦 `error` 就不会自己重试，页面靠**每 5s 的 keepAlive** 检查：有失败路才换
`_t` 令牌强制重连（`_t` 是防缓存的一次性令牌，URL 不变浏览器会复用旧连接）。切换档位、
点「重连画面」同样换 `_t`。板子那边 `age > 5s` 会让卡片显示「画面停滞」。

### API（均为新增，加法式）

| 路径 | 方法 | 说明 |
|------|------|------|
| `/api/v1/camera/status` | GET | 双路相机状态：`source_ok`、`frames`、`seq`、`age`、`avg_ms` 等 |
| `/api/v1/camera/stream` | GET | MJPEG 实时流；`cam`(`front`\|`back`)、`res`(档位，缺省板子默认) |
| `/api/v1/camera/snapshot` | GET | 单张抓拍，MJPEG 放不出来时的兜底 |
| `/api/v1/camera/resolution` | GET | 切换分辨率档位，`res` 必填 |
| `/api/v1/camera/latest-capture` | GET | 板子最近一次抓拍元信息；没有时 `has=false`（正常空态） |
| `/api/v1/camera/latest-capture/image` | GET | 回显图本体（直通转发 JPEG 字节） |

板子侧没起服务 / 网络不通时统一返回 **503**（带排查提示），不会把 500 抛给浏览器。

### ⚠️ 中继必须用异步生成器（BUG-001）

`backend/api/camera.py` 的 `/stream` 路由**必须**是 `async def`，内部生成器**必须**是
`async def` + `httpx.AsyncClient`，关闭上游时**必须**用 `anyio.CancelScope(shield=True)`。
写成同步生成器会造成**连接泄漏**，实测可把服务器拖死：

- 原因：同步生成器由 `iterate_in_threadpool` 驱动，即把 `next()` 丢进 anyio 工作线程。
  anyio 3 的 `to_thread.run_sync` 默认 `cancellable=False` —— 浏览器断开触发的取消
  要等那个线程自己返回才落地，而线程正阻塞在 `read=None` 的无限 socket 读上，永不返回。
  取消被无限期推迟 → `finally` 不执行 → 上游 TCP 连接与 httpx 客户端双双泄漏。
- 实测：10 轮「每路拉 2s 后断开」（模拟刷新/切档）后，板子 `:8090` 连接 **0 → 26**
  （积压 38.5 MB，一条不释放），`.57` **FD 38 → 64**、**RSS 234 → 293 MB**；
  干净 `close()` 后 30s 连接仍 `ESTAB`。
- 崩溃现场：`.57` 曾有 17 条这样的 4K 连接（单路 84 Mbps），随后内核报
  `soft lockup - CPU#5 stuck for 22s! [libuv-worker]`，服务器失联需重启。

改动这一处时不要退回同步写法；`shield` 也不能省（取消已在进行中时裸 `await` 会被立刻打断）。

## License

Internal use — CVITEK.