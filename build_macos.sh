#!/bin/zsh
set -euo pipefail

cd "$(dirname "$0")"

if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3 is required. Install it with: brew install python"
  exit 1
fi

python3 -m pip install --upgrade pip
python3 -m pip install --upgrade -r requirements.txt

python3 -m py_compile \
  config_manager.py verilog_parser.py verilog_runner.py package_manager.py \
  updater.py welcome.py intellisense.py ui_components.py main.py

python3 -m PyInstaller --noconfirm --clean --windowed \
  --name "VeriFlow Studio" \
  --collect-data customtkinter \
  --hidden-import pygments.lexers.hdl \
  --add-data "sample_project:sample_project" \
  main.py

echo "Built macOS app: dist/VeriFlow Studio.app"
