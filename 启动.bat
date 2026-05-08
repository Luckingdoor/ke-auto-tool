@echo off
chcp 65001 >/dev/null
cd /d "%~dp0"

echo ========================================
echo   贝壳工作台自动化查询工具
echo ========================================
echo.

where python >/dev/null 2>/dev/null
if %errorlevel% neq 0 (
    echo ❌ 未找到 Python，请先安装：
    echo    https://www.python.org/downloads/
    echo.
    pause
    exit /b 1
)

echo ✅ Python 已就绪
echo 📦 检查依赖...

python -m pip install -q streamlit pandas openpyxl python-dotenv playwright 2>/dev/null

echo 📥 检查 Chromium...
python -m playwright install chromium 2>/dev/null

echo 🚀 启动服务...
echo.
echo   浏览器访问：http://localhost:8501
echo   按 Ctrl+C 停止
echo ========================================
timeout /t 2 >/dev/null
start http://localhost:8501

python -m streamlit run app.py --server.port 8501 --server.headless false

pause
