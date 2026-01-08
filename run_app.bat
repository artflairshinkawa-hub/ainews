@echo off
chcp 65001 > nul
echo ---------------------------------------------------
echo  AI News Pro - ローカル起動スクリプト
echo ---------------------------------------------------

where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Pythonが見つかりません。Pythonをインストールしてください。
    pause
    exit /b
)

if not exist ".venv" (
    echo [INFO] 仮想環境を作成しています...
    python -m venv .venv
)

echo [INFO] 仮想環境を有効化しています...
call .venv\Scripts\activate.bat

echo [INFO] ライブラリをインストール/更新しています...
pip install -r requirements.txt

echo.
echo [INFO] アプリを起動します...
streamlit run app.py

pause
