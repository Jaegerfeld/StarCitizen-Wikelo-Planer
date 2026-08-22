#!/usr/bin/env bash
# Wikelo-Planer neu bauen (Linux/macOS). Zieht Angebote + Baupläne und
# erzeugt SC_Wikelo_Planer.html im selben Ordner.
cd "$(dirname "$0")" || exit 1
if command -v python3 >/dev/null 2>&1; then PY=python3; else PY=python; fi
"$PY" wikelo_planer_bauen.py
echo
echo "Fertig. SC_Wikelo_Planer.html im Browser oeffnen."
