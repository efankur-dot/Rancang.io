"""
Rancang.io — Entry point streamlit_app.py
Mengarahkan langsung ke aplikasi utama Rancang.io (app.py)
"""
import runpy
from pathlib import Path

# Jalankan app.py secara langsung
app_path = Path(__file__).parent / "app.py"
runpy.run_path(str(app_path), run_name="__main__")
