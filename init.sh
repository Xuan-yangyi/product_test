#!/bin/bash
# webserver 一键部署脚本
# 用法: git clone https://github.com/Xuan-yangyi/product_test.git
#       cd product_test && ./init.sh
set -e

RED="\033[0;31m"; GREEN="\033[0;32m"; YELLOW="\033[1;33m"; NC="\033[0m"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ENV_FILE="$SCRIPT_DIR/cfg/webserver.env"
START_SH="$SCRIPT_DIR/start.sh"

echo "============================================"
echo "  WebServer 一键部署"
echo "============================================"
echo ""

# ── Phase 0: 网络自检 ──
echo "── Phase 0: 网络检查 ──"
MY_IP=$(ip -4 -br addr show eth0 2>/dev/null | awk "{print \$3}" || echo "未知")
echo "  本机 IP: ${MY_IP:-未知}"
ping -c1 -W2 114.114.114.114 >/dev/null 2>&1 && echo -e "  ${GREEN}✅ 互联网连通${NC}" || echo -e "  ${YELLOW}⚠ 无互联网${NC}"

# ── Phase 1: 环境安装 ──
echo ""
echo "── Phase 1: 环境安装 ──"
cd "$SCRIPT_DIR"
if [ ! -f "backend/main.py" ]; then
    echo -e "  ${RED}backend/main.py 不存在，请先在项目根目录执行本脚本${NC}"
    exit 1
fi

# Python 依赖
echo "  安装 Python 依赖 ..."
pip3 install -r backend/requirements.txt 2>/dev/null || {
    echo -e "  ${RED}pip install 失败，请检查 eth0 是否已联网${NC}"; exit 1;
}
echo -e "  ${GREEN}✅ Python 依赖${NC}"

# npm 依赖
if [ -d "frontend/node_modules" ]; then
    echo "  node_modules: 已存在, 跳过 npm install"
else
    echo "  安装前端依赖 (npm install) ..."
    cd frontend && npm install || { echo -e "  ${RED}npm install 失败，请检查 eth0 是否已联网${NC}"; exit 1; }
    cd "$SCRIPT_DIR"
fi
echo -e "  ${GREEN}✅ 前端依赖${NC}"

# MediaMTX
if [ -x "/opt/mediamtx/mediamtx" ]; then
    echo "  MediaMTX: 已安装"
else
    echo "  下载 MediaMTX ..."
    cd /tmp
    wget -q https://github.com/bluenviron/mediamtx/releases/download/v1.8.0/mediamtx_v1.8.0_linux_amd64.tar.gz || {
        echo -e "  ${RED}MediaMTX 下载失败，请检查 eth0 是否已联网${NC}"; exit 1;
    }
    sudo tar -xzf mediamtx_v1.8.0_linux_amd64.tar.gz -C /opt/
    sudo mv /opt/mediamtx_v1.8.0_linux_amd64 /opt/mediamtx 2>/dev/null || sudo mkdir -p /opt/mediamtx && sudo mv /opt/mediamtx /opt/mediamtx/mediamtx
    sudo chmod +x /opt/mediamtx/mediamtx
    rm -f mediamtx_v1.8.0_linux_amd64.tar.gz
    cd "$SCRIPT_DIR"
fi
echo -e "  ${GREEN}✅ MediaMTX${NC}"

echo -e "  ${GREEN}✅ 环境安装完成${NC}"

# ── Phase 2: 配置 ──
echo ""
echo "── Phase 2: 配置确认 ──"
mkdir -p "$SCRIPT_DIR/cfg"
if [ -f "$ENV_FILE" ]; then
    echo "  webserver.env 已存在，当前配置:"
    cat "$ENV_FILE"
    read -rp "  是否修改？[y/N] " mod
    if [ "${mod:-n}" != "y" ] && [ "${mod:-n}" != "Y" ]; then
        echo "  保持现有配置。"
    else
        rm -f "$ENV_FILE"
    fi
fi
if [ ! -f "$ENV_FILE" ]; then
    read -rp "  板子 SE9 IP [10.80.40.68]: " bd_ip; bd_ip=${bd_ip:-10.80.40.68}
    read -rp "  预览端口 [8091]: " pv_port; pv_port=${pv_port:-8091}
    cat > "$ENV_FILE" <<EOF
# webserver 侧配置（由 init.sh 生成）
WS_BOARD_IP=${bd_ip}
WS_PREVIEW_PORT=${pv_port}
PREVIEW_BOARD_BASE=http://\${WS_BOARD_IP}:\${WS_PREVIEW_PORT}
EOF
    echo -e "  ${GREEN}已写入 $ENV_FILE${NC}"
fi

# ── Phase 2.5: 板子连通性验证 ──
echo ""
echo "── Phase 2.5: 板子连通性验证 ──"
source "$ENV_FILE"
ping -c1 -W2 "${WS_BOARD_IP:-10.80.40.68}" >/dev/null 2>&1 && \
    echo -e "  ${GREEN}✅ 板子 IP (${WS_BOARD_IP}) 连通正常${NC}" || \
    echo -e "  ${YELLOW}⚠ 板子 IP 不可达，请确认 SE9 板子已开机且 IP 正确${NC}"

# ── Phase 3: 启动 ──
echo ""
echo "── Phase 3: 启动 ──"
chmod +x "$START_SH" 2>/dev/null
echo "  执行 start.sh ..."
"$START_SH" &
sleep 3

echo "  检查端口 ..."
for p in 8099 1935 8889; do
    ss -tlnp 2>/dev/null | grep -q ":$p " && echo -e "  ${GREEN}✅ :$p 监听${NC}" || echo -e "  ${YELLOW}⚠ :$p 未监听${NC}"
done

# ── Phase 4: 验证 ──
echo ""
echo "── Phase 4: 验证 ──"
sleep 2
curl -s -m5 -o /dev/null -w "  API :8099 → HTTP %{http_code}\n" http://127.0.0.1:8099/api/v1/captures?limit=1 2>/dev/null || echo -e "  ${YELLOW}⚠ API 未响应${NC}"

echo ""
echo "============================================"
echo -e "  ${GREEN}部署完成！${NC}"
echo "  后续操作:"
echo "    · 更新代码:  cd $(pwd) && git pull && ./start.sh"
echo "    · 修改配置:  vi $ENV_FILE"
echo "============================================"
