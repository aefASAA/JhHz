@echo off
echo 正在启动JhHz Python环境管理器...
echo.

REM 检查Python是否安装
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo 错误: 未检测到Python环境
    echo 请先安装Python: https://www.python.org/downloads/
    pause
    exit /b 1
)

echo Python环境检测成功
echo 正在启动JhHz...
echo.

REM 运行主程序
python main.py

REM 如果程序异常退出，暂停显示错误信息
if %errorlevel% neq 0 (
    echo.
    echo 程序运行出现错误，错误代码: %errorlevel%
    pause
) 