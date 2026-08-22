# StarCitizen-Wikelo-Planer

**Version 1.0.0**

Ein Ressourcen-Planer für **Wikelo's Emporium** in *Star Citizen*: Du trägst deinen
Ressourcen-Bestand ein und siehst sofort, **welche Wikelo-Angebote du bekommst** –
zuoberst die sofort verfügbaren, darunter nach **Beschaffungsaufwand gestaffelt**.

> *A resource planner for Wikelo's Emporium in Star Citizen. Enter your stock and instantly
> see which Wikelo rewards you can get — available first, then ranked by how much effort the
> missing ingredients take. Single self-contained HTML file, offline, no install.*

**▶ Online nutzen:** https://jaegerfeld.github.io/StarCitizen-Wikelo-Planer/
**▶ Offline nutzen:** [`SC_Wikelo_Planer.html`](SC_Wikelo_Planer.html) herunterladen und per Doppelklick öffnen.

![Übersicht](docs/screenshots/planer_uebersicht.png)

---

## Was es kann

- **Bestand eintragen** – links alle Zutaten, gruppiert nach Beschaffungsquelle
  (Währung / Mining / Creature-Loot / Contested Zone / craftbar …).
  Menge per **+/−**, **Mausrad**, **Rechtsklick** oder **Modifier-Klick**
  (Klick +1 · Shift +10 · Strg +50 · Alt +100).
- **Schnell-Eingabe** – Kommando-Leiste: `carinite 50` setzt, `name +10` addiert,
  mit Autovervollständigung und Tastatur-Auswahl.
- **Angebote gestaffelt nach Aufwand** – *Sofort verfügbar → 1 Zutat fehlt → 2 fehlen → 3+*.
  Wahlweise gruppiert nach Artikelgruppe (Schiff / Fahrzeug / Waffe / Rüstung / …).
- **Aufwand-Sterne (1–5)** – mengengewichtet: Summe aus *fehlender Menge × Beschaffungskosten
  je Quelle*, log-gestaucht. „Wikelo Arrive" ≈ 1★, eine Idris ≈ 5★.
- **Fehlendes beschaffen** – je Angebot ausklappbar: Bauplan-Rezepte für craftbare Zutaten,
  Wikelo-Favor-/Währungs-Umrechnung, Erz-Preis-/Kaufort-Hinweise.
- **Reputations-Filter** und Ausblenden zurückgezogener Angebote.
- **Bestand speichern/laden** als `SC_Wikelo_Bestand.json` (plus automatisches
  Merken im Browser). Die Bestandsdatei wird beim Neubau automatisch vorgeladen.

## Selbst neu bauen / aktualisieren

Die App bündelt die Daten beim Erzeugen ein. Zum Aktualisieren:

- **Windows:** [`Wikelo_Planer_aktualisieren.bat`](Wikelo_Planer_aktualisieren.bat) doppelklicken
- **Linux/macOS:** `./Wikelo_Planer_aktualisieren.sh`
- **direkt:** `python wikelo_planer_bauen.py`

Voraussetzung: **Python 3.9+** – **keine** externen Pakete (nur Standardbibliothek).
Erzeugt `SC_Wikelo_Planer.html` im selben Ordner.

## Datenquellen & Credits

- **Wikelo-Angebote:** community-gepflegte Datenbank *Wikelo's Emporium Reference*
  ([seeknd.github.io/Wikelo](https://seeknd.github.io/Wikelo/))
- **Bauplan-Rezepte & Erz-Preise:** [star-head.de](https://star-head.de) (offene API)

Die Daten sind patch-abhängig und rotieren – im Zweifel im Spiel gegenprüfen.

## Experimentell

[`experimental/ocr/`](experimental/ocr/) – Vorarbeit, um den Inventar-Bestand automatisch
per OCR zu lesen. Derzeit zurückgestellt, weil das SC-Inventar nur Icons ohne Namen zeigt –
Details und Begründung im dortigen README.

## Haftung

Inoffizielles Fan-Tool. Nicht mit der Cloud Imperium Games Corporation verbunden oder von ihr
unterstützt. Star Citizen® ist eine Marke von CIG. Alle Angaben ohne Gewähr.

## KI-Hinweis

> Dieses Projekt entstand als Erkundung KI-gestützter Softwareentwicklung.
> Der Code wurde weit überwiegend mit [Claude Code](https://claude.com/claude-code) (Anthropic) erstellt.

## Lizenz

[BSD-3-Clause](LICENSE) · © 2026 Robert Seebauer
