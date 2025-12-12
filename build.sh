#!/bin/bash

# Navigate to the application directory
cd cdc

# Create and activate a virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies, including PyInstaller
pip install -r requirements.txt

# --- Build for Linux ---
echo "Building for Linux..."
pyinstaller --onefile --name "Commander Deck Check" --add-data "../AllPrintings.json:." cdc.py

echo "Linux build complete. Executable is in the 'dist' directory."

# --- Instructions for Windows build ---
echo ""
echo "To build for Windows, please run the following commands on a Windows machine:"
echo "1. Install Python 3."
echo "2. Navigate to the 'cdc' directory."
echo "3. python -m venv venv"
echo "4. .\venv\Scripts\activate"
echo "5. pip install -r requirements.txt"
echo "6. pyinstaller --onefile --windowed --name \"Commander Deck Check\" --add-data \"..\AllPrintings.json;.\" cdc.py"
echo "   (Note: Use ';' as separator for --add-data on Windows)"

deactivate
