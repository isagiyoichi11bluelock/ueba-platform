Write-Host "UEBA Platform Demo Launcher" -ForegroundColor Cyan
try { $v = python --version 2>&1; Write-Host "Found: $v" -ForegroundColor Green }
catch { Write-Host "ERROR: Python not found" -ForegroundColor Red; exit 1 }
if (-not (Test-Path ".venv\Scripts\Activate.ps1")) { python -m venv .venv }
& .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt --quiet
if (-not (Test-Path ".env")) { Copy-Item .env.example .env }
python -m src.ueba.generator.build_dataset
python -m src.ueba.pipeline
streamlit run app/streamlit_app.py --server.address localhost --server.port 8501
