# =============================================================================
# Autor:          Robert Seebauer
# Repository:     https://github.com/Jaegerfeld/StarCitizen-Wikelo-Planer
# KI-Unterstützung: Erstellt mit Unterstützung von Claude (Anthropic)
# Erstellt:       22.08.2026
# Geändert:       10.11.2026
# Lizenz:         BSD-3-Clause (siehe LICENSE)
#
# Fachliche Funktion:
#   Zentrale Versionsnummer des Wikelo-Planers (SemVer). wikelo_planer_bauen.py
#   liest sie ein und zeigt sie in Kopfzeile und „Was ist neu?“-Dialog;
#   außerdem steht sie als "version" in data.json.
# =============================================================================
"""Single source of the planner's version number."""

#: Current release version (SemVer), shown in the app and written to data.json.
VERSION = "1.6.3"
