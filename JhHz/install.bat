@echo off
echo ========================================
echo JhHz Python环境管理器 - 安装脚本
echo ========================================
echo.

REM 检查Python是否安装
echo 检查Python环境...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo 错误: 未检测到Python环境
    echo.
    echo 请先安装Python:
    echo 1. 访问 https://www.python.org/downloads/
    echo 2. 下载并安装Python 3.6或更高版本
    echo 3. 安装时请勾选"Add Python to PATH"
    echo.
    pause
    exit /b 1
)

echo ✓ Python环境检测成功
python --version

echo.
echo 检查tkinter...
python -c "import tkinter; print('✓ tkinter可用')" >nul 2>&1
if %errorlevel% neq 0 (
    echo ✗ tkinter不可用，请重新安装Python
    pause
    exit /b 1
)

echo ✓ tkinter可用

echo.
echo 检查pip...
python -m pip --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ✗ pip不可用，请重新安装Python
    pause
    exit /b 1
)

echo ✓ pip可用

echo.
echo ========================================
echo 环境检查完成！
echo ========================================
echo.
echo 现在可以运行JhHz了:
echo 1. 双击 run.bat 启动程序
echo 2. 或者运行: python main.py
echo.
echo 新功能包括:
echo - 检测已安装的包
echo - 显示包大小和安装位置
echo - 右键菜单查看详细信息
echo - 支持卸载包
echo.
pause 