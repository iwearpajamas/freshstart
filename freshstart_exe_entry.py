"""Entry point for building the standalone executable with PyInstaller.

Run: ``python -m PyInstaller --onefile --name freshstart freshstart_exe_entry.py``
"""

from freshstart.cli import app

if __name__ == "__main__":
    app()
