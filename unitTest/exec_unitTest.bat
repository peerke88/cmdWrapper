@echo off
rem simple batch file that allows mayapy to load all unittests based on this folder

set /P mayaVersion="What version of maya do you want to test? "

FOR %%G IN ("2017" "2018" "2019" "2020" "2022") DO ( IF /I "%mayaVersion%"=="%%~G" GOTO MATCH )

:NOMATCH
echo Mayaversion not found
pause
GOTO :EOF

:MATCH
echo Using maya version: %mayaVersion%!

setlocal enabledelayedexpansion
set baseFolder=%~dp0

set Path2=\unitTest.py
set Path3=\unitTest\log_file.txt

SET testCommand=%baseFolder:~0,-1%%Path2%
SET logFile=%baseFolder:~0,-1%%Path3%

ECHO "running %testCommand%"

"C:\Program Files\Autodesk\Maya%mayaVersion%\bin\mayapy.exe" "%testCommand%"

pause