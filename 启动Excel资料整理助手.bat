@echo off
setlocal EnableExtensions

rem 先在调用方代码页下取得脚本目录，避免中文路径在切换代码页时被重解释。
cd /d "%~dp0"
set "PROJECT_DIRECTORY_STATUS=%ERRORLEVEL%"
chcp 65001 >nul

if not "%PROJECT_DIRECTORY_STATUS%"=="0" (
    echo 无法切换到项目目录：%~dp0
    echo 启动失败
    pause
    exit /b 1
)

set "PYTHON_EXE="
set "PYTHON_ARGS="
set "PYTHON_VERSION="

rem 按推荐顺序选择可执行的 Python 解释器。
if exist "C:\Program Files\Python311\python.exe" (
    "C:\Program Files\Python311\python.exe" --version >nul 2>&1
    if not errorlevel 1 set "PYTHON_EXE=C:\Program Files\Python311\python.exe"
)

if not defined PYTHON_EXE (
    py -3.11 --version >nul 2>&1
    if not errorlevel 1 (
        set "PYTHON_EXE=py"
        set "PYTHON_ARGS=-3.11"
    )
)

if not defined PYTHON_EXE (
    python --version >nul 2>&1
    if not errorlevel 1 set "PYTHON_EXE=python"
)

if not defined PYTHON_EXE (
    echo 未找到可用的 Python。
    echo 请安装 Python 3.11 后再启动本程序。
    echo 启动失败
    pause
    exit /b 1
)

for /f "tokens=2" %%V in ('"%PYTHON_EXE%" %PYTHON_ARGS% --version 2^>^&1') do set "PYTHON_VERSION=%%V"
echo 当前 Python 版本：%PYTHON_VERSION%
if /i not "%PYTHON_VERSION:~0,5%"=="3.11." (
    echo 当前 Python 版本不是推荐的 3.11。
    echo 建议安装或使用 Python 3.11。
)

rem 已有关键依赖时直接启动，避免每次都执行 pip install。
"%PYTHON_EXE%" %PYTHON_ARGS% -c "import PySide6, pandas, openpyxl" >nul 2>&1
if not errorlevel 1 goto :start_application

echo 检测到缺少运行依赖（PySide6、pandas 或 openpyxl）。
set /p "INSTALL_DEPENDENCIES=是否自动安装？[Y/N]: "
if /i not "%INSTALL_DEPENDENCIES%"=="Y" (
    echo 未安装依赖，程序无法启动。
    echo 请稍后运行本脚本并选择 Y，或手动执行：
    echo "%PYTHON_EXE%" %PYTHON_ARGS% -m pip install -r requirements.txt
    pause
    exit /b 1
)

if not exist "requirements.txt" (
    echo 未找到 requirements.txt，无法安装依赖。
    echo 启动失败
    pause
    exit /b 1
)

echo 正在安装运行依赖，请稍候...
"%PYTHON_EXE%" %PYTHON_ARGS% -m pip install -r "requirements.txt"
if errorlevel 1 (
    echo 依赖安装失败，请检查网络、pip 和 Python 环境后重试。
    echo 启动失败
    pause
    exit /b 1
)

"%PYTHON_EXE%" %PYTHON_ARGS% -c "import PySide6, pandas, openpyxl" >nul 2>&1
if errorlevel 1 (
    echo 依赖安装完成后仍无法导入运行依赖。
    echo 启动失败
    pause
    exit /b 1
)

:start_application
"%PYTHON_EXE%" %PYTHON_ARGS% "main.py"
if errorlevel 1 (
    echo.
    echo 启动失败
    pause
    exit /b 1
)

endlocal
