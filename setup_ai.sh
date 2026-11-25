#!/usr/bin/env bash
# =============================================================================
# AI 分析配置一键脚本
#
# 用法：
#   ./setup_ai.sh                                              # 交互式
#   ./setup_ai.sh --endpoint URL --model NAME --key sk-xxx     # 参数式
#   AI_API_KEY=sk-xxx ./setup_ai.sh --endpoint URL --model NAME --test
#   ./setup_ai.sh --dry-run ...                                # 只校验不写入
#
# 说明：
#   - 写入 cfg/ai_config.json（权限 600），保留已有 system_prompt 等字段
#   - 若服务在 127.0.0.1:8099 运行，会自动热加载配置（无需重启）
#   - 优先使用环境变量 AI_API_KEY，避免密钥出现在 ps 命令行
# =============================================================================
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
CFG="$ROOT/cfg/ai_config.json"
EXAMPLE="$ROOT/cfg/ai_config.json.example"

DEFAULT_ENDPOINT="https://www.sophnet.com/api/open-apis/v1/chat/completions"
DEFAULT_MODEL="DeepSeek-V4.1-Flash-1017"

ENDPOINT="${AI_ENDPOINT:-}"
MODEL="${AI_MODEL:-}"
API_KEY="${AI_API_KEY:-}"
DO_TEST=0
DRY_RUN=0

usage() {
  sed -n '2,16p' "$0" | sed 's/^# \{0,1\}//'
  echo
  echo "参数："
  echo "  --endpoint URL    模型 API 完整地址（默认：$DEFAULT_ENDPOINT）"
  echo "  --model NAME      模型名（默认：$DEFAULT_MODEL）"
  echo "  --key KEY         API Key（也可用环境变量 AI_API_KEY）"
  echo "  --test            写入后调用一次模型验证连通性"
  echo "  --dry-run         只打印将要写入的内容，不落盘"
  echo "  -h, --help        显示帮助"
}

while [ $# -gt 0 ]; do
  case "$1" in
    --endpoint) ENDPOINT="${2:-}"; shift 2 ;;
    --model)    MODEL="${2:-}";    shift 2 ;;
    --key)      API_KEY="${2:-}";  shift 2 ;;
    --test)     DO_TEST=1;         shift ;;
    --dry-run)  DRY_RUN=1;         shift ;;
    -h|--help)  usage; exit 0 ;;
    *) echo "未知参数: $1"; usage; exit 1 ;;
  esac
done

# ---------- 交互式补全 ----------
if [ -z "$ENDPOINT" ]; then
  read -r -p "API 端点 [$DEFAULT_ENDPOINT]: " ENDPOINT || true
  ENDPOINT="${ENDPOINT:-$DEFAULT_ENDPOINT}"
fi
if [ -z "$MODEL" ]; then
  read -r -p "模型名 [$DEFAULT_MODEL]: " MODEL || true
  MODEL="${MODEL:-$DEFAULT_MODEL}"
fi
if [ -z "$API_KEY" ]; then
  if [ -t 0 ]; then
    read -r -s -p "API Key（输入不回显）: " API_KEY
    echo
  else
    echo "错误：缺少 Key。请用 --key 或环境变量 AI_API_KEY 提供。" >&2
    exit 1
  fi
fi

if [ -z "$API_KEY" ]; then
  echo "错误：API Key 不能为空" >&2
  exit 1
fi

# ---------- 写入配置（保留其他字段） ----------
python3 - "$CFG" "$EXAMPLE" "$ENDPOINT" "$MODEL" "$API_KEY" "$DRY_RUN" <<'PY'
import json, os, sys

cfg_path, ex_path, endpoint, model, key, dry = sys.argv[1:7]

base = {}
if os.path.exists(cfg_path):
    try:
        with open(cfg_path) as f:
            base = json.load(f)
    except Exception:
        print("警告：已有 ai_config.json 解析失败，将重建", file=sys.stderr)
if not base and os.path.exists(ex_path):
    with open(ex_path) as f:
        base = json.load(f)

base["api_endpoint"] = endpoint
base["model"] = model
base["api_key"] = key
base.setdefault("max_tokens", 4096)
base.setdefault("temperature", 0.7)
base.setdefault("auto_analyze_on_complete", True)
base.setdefault("auto_analyze_on_error", True)
base.setdefault(
    "system_prompt",
    "你是专业的嵌入式设备产测分析专家。请根据提供的测试日志（整机接口测试或老化测试），"
    "分析测试执行情况、失败根因、硬件异常与优化建议。请用中文回复，结论明确、可操作。",
)

print(f"endpoint : {endpoint}")
print(f"model    : {model}")
print(f"api_key  : 已配置（长度 {len(key)}）")

if dry == "1":
    print("[dry-run] 未写入任何文件")
    sys.exit(0)

os.makedirs(os.path.dirname(cfg_path), exist_ok=True)
with open(cfg_path, "w", encoding="utf-8") as f:
    json.dump(base, f, indent=2, ensure_ascii=False)
os.chmod(cfg_path, 0o600)
print(f"已写入   : {cfg_path}（权限 600）")
PY

# dry-run 且不要求测试 -> 直接结束
if [ "$DRY_RUN" = "1" ] && [ "$DO_TEST" = "0" ]; then
  exit 0
fi

# ---------- 连通性验证 ----------
if [ "$DO_TEST" = "1" ]; then
  echo "验证模型连通性..."
  BODY=$(python3 -c 'import json,sys; print(json.dumps({"messages":[{"role":"user","content":"回复两个字：正常"}],"model":sys.argv[1],"stream":False}, ensure_ascii=False))' "$MODEL")
  RESP=$(curl -s -m 40 -w '\n__HTTP__%{http_code}' -X POST "$ENDPOINT" \
    -H "Authorization: Bearer $API_KEY" \
    -H "Content-Type: application/json" \
    -d "$BODY" || true)
  CODE="${RESP##*__HTTP__}"
  BODY_OUT="${RESP%$'\n'__HTTP__*}"
  echo "HTTP $CODE"
  if [ "$CODE" = "200" ]; then
    echo "✅ 模型可用：$(printf '%s' "$BODY_OUT" | python3 -c 'import json,sys
try:
    d=json.load(sys.stdin); print(d.get("choices",[{}])[0].get("message",{}).get("content","")[:60])
except Exception:
    print("(响应解析失败)")' 2>/dev/null)"
  else
    echo "❌ 调用失败：${BODY_OUT:0:300}"
    echo "   提示：301=端点错误；401/403=Key 无效；404=路径错误；429=限流"
  fi
fi

# ---------- 热加载到运行中的服务 ----------
if [ "$DRY_RUN" = "0" ] && curl -s -m 3 http://127.0.0.1:8099/api/health >/dev/null 2>&1; then
  if curl -s -m 5 -X POST http://127.0.0.1:8099/api/v1/ai/config/reload >/dev/null 2>&1; then
    echo "已热加载到运行中的服务（:8099）"
  else
    echo "提示：热加载失败，可重启服务后生效"
  fi
fi