@echo off
echo ============================================
echo  UEBA Platform Demo Launcher (Windows)
echo ============================================

python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found. Please install Python 3.11+
    exit /b 1
)

if not exist ".venv\Scripts\activate.bat" (
    echo Creating virtual environment...
    python -m venv .venv
)

call .venv\Scripts\activate.bat

echo Installing requirements...
pip install -r requirements.txt --quiet

if not exist ".env" (
    copy .env.example .env
    echo WARNING: Using default PSEUDONYM_SALT
)

echo Generating synthetic data...
python -m src.ueba.generator.build_dataset

echo Running analysis pipeline...
python -m src.ueba.pipeline

echo Launching Casebook GUI at http://localhost:8501...
echo (To run the legacy Streamlit app instead: streamlit run app_legacy/streamlit_app.py)
python -m gui.server
