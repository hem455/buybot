@echo off
echo ==========================================
echo Generating Sample Chart Data
echo ==========================================
echo.

REM Activate virtual environment
call venv\Scripts\activate

echo Creating realistic demo data for charts...
echo.

REM Generate sample data
python scripts\generate_sample_data.py

echo.
echo Sample data generated successfully!
echo.
echo You can now:
echo 1. Start the Modern UI: start_modern_ui.bat
echo 2. View beautiful charts with realistic data
echo.
pause
