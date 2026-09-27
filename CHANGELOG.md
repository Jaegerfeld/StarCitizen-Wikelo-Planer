# Changelog

Alle nennenswerten Änderungen an diesem Projekt werden hier dokumentiert.
Format nach [Keep a Changelog](https://keepachangelog.com/de/1.1.0/),
Versionierung nach [Semantic Versioning](https://semver.org/lang/de/).

## [1.3.1] – 2026-09-27

### Hinzugefügt
- **Wechsel-Button** in der Kopfzeile zum [Bauplan-Planer](https://jaegerfeld.github.io/StarCitizen-Bauplan-Planer/) (Schwester-Tool für craftbare Baupläne).

## [1.3.0] – 2026-09-12

### Hinzugefügt
- **In-App-Changelog:** Button „🆕 Was ist neu?" öffnet ein Fenster mit dieser
  Änderungshistorie – offline in die HTML eingebacken (Generator liest `CHANGELOG.md`),
  plus Link zur vollständigen Fassung auf GitHub.

### Behoben
- Beschaffungs-Hinweis für Erze versprach „(Preis siehe unten)", obwohl aktuell kein
  Preis vorliegt (UEX liefert für die neuen Erze nur Platzhalter, die der
  Plausibilitätsfilter verwirft). Der Zusatz entfällt; ein Preis wird nur noch
  angezeigt, wenn tatsächlich einer vorhanden ist.

## [1.2.0] – 2026-09-11

### Hinzugefügt
- **Erworbene Angebote markieren & ausblenden:** Button „✓ erworben" auf jeder Angebots-Karte
  markiert ein bereits erhaltenes Wikelo-Produkt und blendet es aus. Persistiert (eigener
  `localStorage`-Schlüssel) und wird in der Bestandsdatei mitgespeichert. Kopfzeilen-Schalter
  „erworbene zeigen" holt sie zum Aufheben der Markierung zurück. Identität über den stabilen
  `mission_name` (nicht die positionsabhängige `id`), damit die Markierung eine
  In-App-Aktualisierung übersteht; nach Refresh nicht mehr auffindbare Einträge bleiben erhalten
  und werden als Tooltip angezeigt statt still verworfen.
- **Freier Speicherort:** Speichern/Laden nutzt – wo verfügbar (Chromium, sicherer Kontext) –
  die File System Access API, sodass Ort und Dateiname frei wählbar sind und ein geladenes File
  beim erneuten Speichern zurückgeschrieben wird (Rechtsklick auf „Speichern" = Ort neu wählen).
  Fallback auf Download/Datei-Auswahl, wo die API fehlt (z. B. Firefox, `file://`).

### Geändert
- Bestandsdatei-Format erweitert auf `{schema, inventory, acquired}`; altes flaches
  `{name: menge}` wird weiterhin gelesen (abwärtskompatibel). Generator und App lesen beide
  Formate.

## [1.1.1] – 2026-08-22

### Geändert
- Ruf-Badges eindeutiger beschriftet: Belohnung „Belohnung +N Ruf" (grün) vs.
  Voraussetzung „braucht Ruf N ⚠" (rot) – vorher beide nur „Ruf N". DE + EN.

## [1.1.0] – 2026-08-22

### Hinzugefügt
- **In-App-Datenaktualisierung:** Button „Daten aktualisieren" lädt Angebote (seeknd),
  Baupläne (star-head) und Erz-Preise (UEX) live im Browser nach – ohne Neu-Build.
  Ergebnis wird schema-versioniert in `localStorage` gecacht (getrennt vom Bestand);
  non-fatal (bei Fehler bleiben die bestehenden Daten). Rechtsklick = auf Build-Daten
  zurücksetzen. Preisquelle wählbar (beide / UEX / star-head).
- **Zweisprachige Oberfläche (DE/EN)** mit Umschalter im Header; Kategorien, Quellen und
  Status als stabile Keys, Labels nur beim Rendern lokalisiert.
- **Erz-Preise via UEX** (füllt die star-head-Lücke) mit Plausibilitäts-Filter.

### Geändert
- Aufbereitungslogik lebt jetzt einmalig im Browser (`transform()`); der Generator
  bündelt nur noch Rohdaten. Golden-Diff bestätigt identische Ausgabe zur Vorversion.

## [1.0.0] – 2026-08-22

### Hinzugefügt
- Erste öffentliche Version des **StarCitizen-Wikelo-Planers**.
- Eigenständige Offline-GUI (`SC_Wikelo_Planer.html`) – eine Datei, kein Server, keine Installation.
- Ressourcen-Bestand anklickbar; Menge per +/−-Knopf, Mausrad, Rechtsklick sowie
  Modifier-Schritten (Klick +1 · Shift +10 · Strg +50 · Alt +100).
- **Schnell-Eingabe** (Kommando-Leiste): z. B. `carinite 50` setzt, `name +10` addiert,
  mit Autovervollständigung und Tastatur-Auswahl.
- Wikelo-Angebote **gestaffelt nach Aufwand** (Sofort / 1 fehlt / 2 fehlen / 3+ fehlen),
  wahlweise gruppiert nach Artikelgruppe.
- **Mengengewichtete Aufwand-Sterne** (1–5): Summe aus fehlender Menge × Beschaffungskosten
  je Quelle, log-gestaucht (kalibriert: „Wikelo Arrive" ≈ 1★, Idris ≈ 5★).
- Detailansicht „Fehlendes beschaffen" je Angebot: Bauplan-Rezepte für craftbare Zutaten,
  Wikelo-Favor-/Währungs-Umrechnung, Erz-Preis-/Kaufort-Hinweise.
- Reputations-Filter und Ausblenden zurückgezogener Angebote.
- Bestand-Persistenz: Browser-`localStorage` + **Speichern/Laden als `SC_Wikelo_Bestand.json`**;
  vorhandene Bestandsdatei wird beim Neubau automatisch vorgeladen.
- Generator `wikelo_planer_bauen.py` zieht Angebote (community-Wikelo-DB) und
  Bauplan-Rezepte (star-head.de) und backt sie in die HTML.

### Experimentell
- `experimental/ocr/` – Windows-OCR-Vorarbeit zum Auslesen des Inventars.
  Derzeit blockiert, weil das SC-Inventar nur Icons ohne Namen zeigt (siehe README dort).

[1.3.0]: https://github.com/Jaegerfeld/StarCitizen-Wikelo-Planer/releases/tag/v1.3.0
[1.2.0]: https://github.com/Jaegerfeld/StarCitizen-Wikelo-Planer/releases/tag/v1.2.0
[1.1.1]: https://github.com/Jaegerfeld/StarCitizen-Wikelo-Planer/releases/tag/v1.1.1
[1.1.0]: https://github.com/Jaegerfeld/StarCitizen-Wikelo-Planer/releases/tag/v1.1.0
[1.0.0]: https://github.com/Jaegerfeld/StarCitizen-Wikelo-Planer/releases/tag/v1.0.0
