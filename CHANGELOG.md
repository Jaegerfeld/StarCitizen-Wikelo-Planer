# Changelog

Alle nennenswerten Änderungen an diesem Projekt werden hier dokumentiert.
Format nach [Keep a Changelog](https://keepachangelog.com/de/1.1.0/),
Versionierung nach [Semantic Versioning](https://semver.org/lang/de/).

## [1.6.3] – 2026-11-10

### Geändert
- **„Weitere Tools“ nennt jetzt auch den neuen Schiffskauf-Planer.** Die gemeinsamen Dateien `kopfzeile.py` und `sc_design.py` gelten nun für fünf Tools.

## [1.6.2] – 2026-11-01

### Behoben
- **Erz-Preise werden wieder angezeigt.** Der Build meldete „0 Erz-Preise“, weil er alle Preise über 100 000 aUEC/SCU als Platzhalter verwarf. Jaclium, Saldynium und Sadaryx verkaufen sich aber wirklich für 0,5 bis 34 Mio. aUEC/SCU (Sadaryx am 28.10. per Screenshot in Orison bestätigt).

### Geändert
- **Erz-Preise kommen jetzt von star-head.de** statt von UEX, dieselbe Quelle wie im Handels-Planer. Der Hinweis nennt den besten Verkaufsort mit Datum und die Zahl der Verkaufsorte. Für Carinite meldet keine Quelle einen Preis; dort bleibt der Hinweis leer.
- Die Auswahl „Preise: beide / nur UEX / nur star-head“ ist entfernt. Sie wurde gespeichert, hatte aber keine Wirkung.

## [1.6.1] – 2026-11-01

### Geändert
- **Kommentare und Docstrings** nach dem Standard von [situation-report](https://github.com/Jaegerfeld/situation-report): Kopfblock mit Autor, Lizenz und fachlicher Funktion in jeder Quelldatei, englische Docstrings im Google-Stil mit `Args`/`Returns`/`Raises`, `#:`-Kommentare an Konstanten, ein Satz über jeder JavaScript-Funktion der Seite. Am Verhalten ändert sich nichts.
- `CONTRIBUTING.md` überarbeitet: jetzt mit den gemeinsamen Regeln aller vier SC-Tools (Prüfungen, Kommentare, Versionen, gemeinsame Dateien).

## [1.6.0] – 2026-11-01

### Hinzugefügt
- **Gemeinsames Design** aller vier SC-Tools in `sc_design.py` (in allen vier Repos identisch, wie `kopfzeile.py`): Farben für Hell und Dunkel, Schriften (Rajdhani für Überschriften, Exo 2 für Text), Knöpfe, Eingabefelder, Fokusrahmen, Lösch-Knopf-Stil.
- **Handy und Tablet:** Auf schmalen Bildschirmen (unter 920 px) zeigen Tools mit mehreren Bereichen oben Reiter statt nebeneinanderliegender Spalten; der Hauptinhalt kommt zuerst. Auf Touch-Geräten sind Knöpfe, Felder und Häkchen mindestens 44 px groß. Kein seitliches Scrollen mehr bei 390 px Breite; breite Tabellen scrollen nur in ihrem Rahmen.
- Kopfzeile am Handy kompakter: Einzeiler auf zwei Zeilen gekürzt, „Weitere Tools“ klappt auf.
- **Helles Design** und Hell/Dunkel-Knopf; die Wahl wird gespeichert.
- Reiter am Handy: **Angebote · Mein Bestand**; die passenden Gruppen der Werkzeugleiste wandern mit.

### Geändert
- **Familienfarben und -schriften** statt Navy/Gold und Segoe UI; Hauptknöpfe türkis wie in den anderen Tools, Gold/Amber bleibt Hervorhebungsfarbe.
- **Werkzeugleiste in drei beschrifteten Gruppen:** Ansicht · Bestand · Daten. „leeren“ steht abgesetzt und ist als Löschknopf gestaltet (die Rückfrage bleibt).
- Mengen-Knöpfe auf Touch-Geräten 44 px groß; die Werkzeugleiste läuft auf schmalen Bildschirmen nicht mehr mit.

## [1.5.0] – 2026-11-01

### Hinzugefügt
- **„Was ist neu?“** in der Kopfzeile: zeigt dieses Changelog in einem Dialog, mit der aktuellen Version im Titel und einem Link auf die Datei auf GitHub. Der Text wird beim Bauen aus `CHANGELOG.md` übernommen und funktioniert auch in der Offline-Kopie. Schließen per Esc, Klick daneben oder ✕.

### Geändert
- **Einheitliche Kopfzeile** in allen vier SC-Tools (Bauplan-, Wikelo-, Handels-Planer, Screenshot-Auswerter): Kicker, Titel mit Version, Einzeiler, Aktionszeile (Sprache DE | EN mit sichtbarer aktiver Sprache, Hell/Dunkel, „Was ist neu?“, Tool-Aktionen, „Neuesten Stand laden“), eigene Zeile „Weitere Tools“ mit denselben Zielen in derselben Reihenfolge, Datenzeile. Quelle ist `kopfzeile.py`, in allen vier Repos identisch.
- Die Steuerleiste (Modus, Ruf, Filter, Bestand, Preise) ist eine eigene, mitlaufende Werkzeugleiste unter der Kopfzeile. „Was ist neu?“ nutzt den gemeinsamen Dialog. Kein Hell/Dunkel-Knopf, weil der Wikelo-Planer noch kein helles Design hat.

### Behoben
- Am Knopf „Neuesten Stand laden“ stand im Quelltext ein Rest „lisieren“.

## [1.4.1] – 2026-10-25

### Hinzugefügt
- Kopfzeile: Links zum **Handels-Planer** und zur **Guides-Übersicht** (jaegerfeld.github.io/sc-guides), damit man von jedem Planer zurück zur Übersichtsseite kommt.

## [1.4.0] – 2026-10-25

### Geändert
- **Aktualisierung läuft über GitHub:** Die Online-Version wird täglich (05:00 UTC) per GitHub Actions neu gebaut; dabei entsteht neben der HTML eine `data.json` mit demselben Datenstand (ohne persönlichen Bestand).
- **Knopf „Daten aktualisieren“ → „Neuesten Stand laden (GitHub)“:** lädt die `data.json` des letzten Builds von GitHub Pages statt seeknd, `api.star-head.de/blueprint` und UEX direkt aus dem Browser. Das schont die Community-Quellen (eine Abfrage pro Tag statt eine pro Klick). Funktioniert auch aus der Offline-Kopie; Rechtsklick setzt wie bisher auf die eingebauten Build-Daten zurück. Meldet, wenn der Stand schon aktuell ist.

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
