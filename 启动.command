#!/bin/bash
cd "$(dirname "$0")"

echo "========================================"
echo "  贝壳工作台自动化查询工具"
echo "========================================"
echo ""

# 检查 Python
if ! command -v python3 &> /dev/null; then
    echo "❌ 未找到 Python3，请先安装："
    echo "   https://www.python.org/downloads/"
    echo ""
    read -p "按回车退出..."
    exit 1
fi

echo "✅ Python3 已就绪"

# 安装依赖
echo "📦 检查依赖..."
python3 -m pip install -q streamlit pandas openpyxl python-dotenv playwright 2>/dev/null

# 安装 Chromium（首次较慢，约 150MB）
if ! python3 -c "from playwright.sync_api import sync_playwright; sync_playwright().start().chromium.launch()" 2>/dev/null; then
    echo "📥 首次运行，正在下载 Chromium（约 150MB，需等待 1-2 分钟）..."
    python3 -m playwright install chromium
fi

echo "🚀 启动服务..."
echo ""
echo "  浏览器将自动打开，如未打开请访问："
echo "  http://localhost:8501"
echo ""
echo "  按 Ctrl+C 停止服务"
echo "========================================"

# 打开浏览器
sleep 2
open http://localhost:8501 2>/dev/null

# 启动 Streamlit
python3 -m streamlit run app.py --server.port 8501 --server.headless false
