# VRising Calculator

A desktop calculator built with Python and PySimpleGUI that parses in-game crafting data from the included markdown files.

## Installation

```bash
pip install -r requirements.txt
```

## Usage

Run the GUI directly with Python:

```bash
python main.py
```

## Building a Windows executable

PyInstaller can bundle the script into a single `.exe` file. Use the `Export .exe` button in the application or run:

```bash
pyinstaller --onefile main.py
```

