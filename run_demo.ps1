Write-Host "UEBA Platform Demo Launcher" -ForegroundColor Cyan
try { $v = python --version 2>&1; Write-Host "Found: $v" -ForegroundColor Green }
catch { Write-Host "ERROR: Python not found" -ForegroundColor Red; exit 1 }
if (-not (Test-Path ".venv\Scripts\Activate.ps1")) { python -m venv .venv }
& .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt --quiet
if (-not (Test-Path ".env")) { Copy-Item .env.example .env }
python -m src.ueba.generator.build_dataset
python -m src.ueba.pipeline
Write-Host "Launching Casebook GUI at http://localhost:8501..." -ForegroundColor Green
Write-Host "(Legacy Streamlit app available via: streamlit run app_legacy/streamlit_app.py)" -ForegroundColor Yellow
python -m gui.server
