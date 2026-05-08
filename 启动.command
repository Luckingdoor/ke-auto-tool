#!/bin/bash
cd "$(dirname "$0")"
DIR="$(pwd)"

echo "========================================"
echo "  贝壳工作台自动化查询工具"
echo "  目录: $DIR"
echo "========================================"
echo ""

# 确认 app.py 存在
if [ ! -f "app.py" ]; then
    echo "❌ 未找到 app.py，请确保启动脚本和 app.py 在同一目录"
    echo "   当前目录: $DIR"
    read -p "按回车退出..."
    exit 1
fi

# 检查 Python
if ! command -v python3 &> /dev/null; then
    echo "❌ 未找到 Python3，请先安装："
    echo "   https://www.python.org/downloads/"
    read -p "按回车退出..."
    exit 1
fi
echo "✅ Python3: $(python3 --version)"

# 安装依赖
echo "📦 检查依赖..."
python3 -m pip install -q streamlit pandas openpyxl python-dotenv playwright

# 安装 Chromium（首次较慢，约 150MB）
echo "📥 检查 Chromium..."
python3 -m playwright install chromium 2>/dev/null

echo ""
echo "🚀 启动服务..."
echo "   浏览器访问: http://localhost:8501"
echo "   按 Ctrl+C 停止"
echo "========================================"

sleep 2
open http://localhost:8501 2>/dev/null

python3 -m streamlit run app.py --server.port 8501 --server.headless false
