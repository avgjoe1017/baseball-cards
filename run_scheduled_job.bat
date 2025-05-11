@echo off
REM Batch file to run the scheduled_job.py script
REM Ensure the correct Python path is set below

SET PYTHON_PATH=C:\Python39\python.exe
SET SCRIPT_PATH=C:\Users\joeba\Documents\baseball-cards\scheduled_job.py

%PYTHON_PATH% %SCRIPT_PATH%

REM Pause to keep the terminal open after execution
pause