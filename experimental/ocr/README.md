# Experimentell: Inventar per OCR auslesen

Ziel war, den Ressourcen-Bestand **automatisch** aus dem Spiel zu lesen, statt ihn
im Planer einzutippen. Dieser Ordner dokumentiert die Vorarbeit.

## Stand: blockiert (bewusst zurückgestellt)

Das Star-Citizen-Inventar ist ein **reines Icon-Raster** – es zeigt nur Symbole und
Mengen-Badges, **keine Item-Namen** (Namen erscheinen nur beim Hovern als Tooltip).
Damit kann OCR zwar die *Mengen* lesen, aber nicht, **um welches Item** es sich handelt.
Ohne Namenszuordnung sind die Zahlen wertlos.

Ergänzend geprüft an echten `Game.log`-Dateien: Der Ressourcen-Bestand (mit Mengen) und
der Wikelo-Ruf stehen **nicht** im Log – Bestand wird per `QueryInventory` vom Server
geholt, die Antwort landet nie im Log; Reputation ist ein reiner Server-Dienst.

**Nächster sinnvoller Schritt** wäre Icon-Bilderkennung (Perceptual-Hash gegen eine
selbst aufgebaute Referenz-Bibliothek). Das ist zurückgestellt, weil das Inventar-UI
voraussichtlich noch überarbeitet wird – jede Icon-Arbeit wäre bis dahin Wegwerf-Aufwand.

## Was funktioniert (`wikelo_ocr_dump.ps1`)

Nachgewiesen: Die **eingebaute Windows-OCR** (`Windows.Media.Ocr`, offline, ohne
Installation) erkennt Text zuverlässig. Das Skript liest alle `inventar*.png` in einem
Ordner und schreibt jedes erkannte Wort mit Position/Größe nach `SC_Wikelo_OCR_words.json`
(Rohdaten-Basis für einen späteren Matcher).

```powershell
powershell -ExecutionPolicy Bypass -File wikelo_ocr_dump.ps1 -Folder "<Screenshot-Ordner>"
```

Voraussetzung: Windows 10/11 mit installiertem OCR-Sprachpaket (Standard vorhanden).
Bridge-Hinweis (PS 5.1): `System.Runtime.WindowsRuntime` wird für die async-Aufrufe geladen.
