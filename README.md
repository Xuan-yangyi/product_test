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

### 图片与数据的落盘位置 / 形式

| 内容 | 路径 / 形式 |
|------|-------------|
| 图片文件 | `data/sn_captures/<SN>/<时间戳>.<jpg\|png>`（按 SN 分目录，一张一文件） |
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
| `uploaded_at` | 入库时间（服务器时钟，自动，永不为空）——**日期范围筛选即按此字段** |

### 相关 API（均为新增，加法式）

| 路径 | 方法 | 说明 |
|------|------|------|
| `/api/v1/captures` | POST | SE9 上传：multipart `sn`(必填)、`score`、`ts`、`image`(jpeg/png, <20MB) |
| `/api/v1/captures` | GET | 查询：`sn`、`start`/`end`(入库日期 YYYY-MM-DD，含当天)、`limit`、`offset`；返回 `{total, items[...image_url, uploaded_at]}` |
| `/api/v1/captures/{id}/image` | GET | 返回该条抓拍的设备图文件 |

## License

Internal use — CVITEK.