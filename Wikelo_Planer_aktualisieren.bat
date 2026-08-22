@echo off
REM Wikelo-Planer: zieht Angebote (seeknd.github.io) + Bauplaene (star-head.de)
REM und baut die offline lauffaehige App SC_Wikelo_Planer.html neu.
echo Baue Star Citizen Wikelo Ressourcen-Planer ...
py "%~dp0wikelo_planer_bauen.py"
echo.
echo Fertig. SC_Wikelo_Planer.html per Doppelklick im Browser oeffnen.
pause
