# SC Wikelo-Planer – Anleitung

## Kurzanleitung

Der Wikelo-Planer zeigt dir, welche Angebote von **Wikelo's Emporium** du mit deinem Ressourcen-Bestand erfüllen kannst und was dir noch fehlt. Du trägst links ein, was du hast, rechts sortieren sich die Angebote danach.

### Bereiche

- **Kopfzeile:** Sprache **DE | EN**, **Hell / Dunkel**, **🆕 Was ist neu?**, **🔄 Neuesten Stand laden (GitHub)** und **Weitere Tools**. Die Datenzeile nennt Patch, Datenstand und Zahl der Angebote.
- **Ansicht:** **Nach Aufwand** oder **Nach Artikelgruppe**, dein Ruf unter **Mein Wikelo-Ruf:**, die Häkchen **nur erfüllbarer Ruf**, **zurückgezogene zeigen**, **erworbene zeigen** und das Feld **Angebote filtern…**.
- **Bestand:** **💾 Bestand speichern**, **📂 Bestand laden** und **leeren** (mit Rückfrage).
- **Mein Ressourcen-Bestand** (links): alle Zutaten, gruppiert nach Beschaffung, z. B. Wikelo/Währung, Mining/Erz, Creature/Loot, Craftbar (Bauplan). Dazu die **Schnell-Eingabe**, **Ressource suchen…** und **nur „hab ich" zeigen**.
- **Angebote** (rechts): Karten mit allen Zutaten. Grüne Chips hast du, rote fehlen noch (mit „hast/braucht").
- Am Handy (schmale Fenster) wechselst du oben zwischen den Reitern **Angebote** und **Mein Bestand**.

### Häufige Handgriffe

- Menge ändern: **+** und **−** neben der Zutat. Mit Shift +10, mit Strg +50, mit Alt +100.
- Mausrad über einer Zutat zählt hoch oder runter, Rechtsklick zieht ab.
- Klick auf den Namen einer Zutat schaltet zwischen 0 und 1 um.
- Schnell-Eingabe: `carinite 50` setzt auf 50, `carinite +10` addiert 10, nur `carinite` addiert 1. Mit ↑↓ wählen, Enter übernimmt.
- Klick auf einen roten Chip in einer Karte addiert 1 (mit Shift, Strg oder Alt mehr).
- **Fehlendes beschaffen ▾** klappt auf, woher die fehlenden Zutaten kommen.
- **✓ erworben** blendet ein Angebot aus, **↩ zurück** holt es wieder.

### Bänder und Aufwand

- In **Nach Aufwand** stehen oben **Sofort verfügbar**, darunter **1 Zutat fehlt**, **2 Zutaten fehlen**, **3+ Zutaten fehlen**.
- Die Punkte bei **Aufwand** (1 bis 5) schätzen, wie viel Arbeit das Fehlende macht: fehlende Menge mal Beschaffungsaufwand der Quelle.

### Daten und Speicherung

- Angebote kommen von der Community-Datenbank [seeknd.github.io/Wikelo](https://seeknd.github.io/Wikelo/), Baupläne und Erz-Preise von [star-head.de](https://star-head.de). Die Daten können sich mit jedem Patch ändern. Prüfe im Spiel gegen.
- **🔄 Neuesten Stand laden (GitHub)** holt den täglich gebauten Datenstand. Rechtsklick darauf setzt auf die eingebauten Daten zurück.
- Bestand, „erworben"-Markierungen und Einstellungen bleiben nur in diesem Browser (localStorage). Für ein Backup oder einen anderen Rechner nutzt du **💾 Bestand speichern** (Datei `SC_Wikelo_Bestand.json`).
- Offline: Lade `SC_Wikelo_Planer.html` herunter und öffne sie per Doppelklick. Sie braucht kein Internet.

## Tutorial: Was kann ich holen?

Ziel: Du trägst deinen Bestand ein und findest das Angebot, das dir am wenigsten Arbeit macht.

1. Stelle in der Gruppe **Ansicht** auf **Nach Aufwand**.
2. Trage unter **Mein Wikelo-Ruf:** deinen Ruf bei Wikelo ein.
3. Setze das Häkchen **nur erfüllbarer Ruf**. Dann siehst du nur Angebote, für die dein Ruf reicht.
4. Klicke links in das Feld **Schnell-Eingabe** und tippe z. B. `carinite 50`. Drücke Enter. Die Zutat steht jetzt auf 50.
5. Trage so alle Zutaten ein, die du im Spiel hast. Für kleine Mengen reichen **+** und **−** neben der Zutat.
6. Setze das Häkchen **nur „hab ich" zeigen**. Die Liste zeigt jetzt nur, was du eingetragen hast. So prüfst du die Zahlen.
7. Schau rechts ins Band **Sofort verfügbar**. Diese Angebote kannst du jetzt bei Wikelo abholen.
8. Ist das Band leer, schau in **1 Zutat fehlt**. Innerhalb eines Bands stehen die Angebote mit wenig Aufwand oben.
9. Klicke auf einer Karte auf **Fehlendes beschaffen ▾**. Du siehst je fehlender Zutat die Quelle und einen Hinweis, z. B. ein Bauplan-Rezept, einen Wikelo-Tausch oder einen Erz-Preis.
10. Hast du ein Angebot im Spiel abgeholt, klicke oben auf der Karte auf **✓ erworben**. Die Karte verschwindet.
11. Klicke auf **💾 Bestand speichern**, damit du eine Sicherung als Datei hast.

### Tipps

- Mit **Angebote filtern…** findest du ein Angebot schnell. Der Filter sucht auch in den Zutaten.
- **Nach Artikelgruppe** sortiert nach Schiff, Fahrzeug, Waffe, Rüstung, Ausrüstung und Freischaltung.
- Ein rotes Schild **braucht Ruf … ⚠** heißt: dein eingetragener Ruf reicht noch nicht.
- **erworbene zeigen** holt ausgeblendete Angebote zurück. Daneben steht, wie viele du markiert hast.

## Tutorial: Bestand sichern

Ziel: Du speicherst deinen Bestand als Datei und lädst ihn auf einem anderen Rechner oder in einem anderen Browser wieder.

1. Trage deinen Bestand ein, wie in der Kurzanleitung beschrieben.
2. Klicke in der Gruppe **Bestand** auf **💾 Bestand speichern**.
3. Je nach Browser öffnet sich ein Speicherdialog, oder die Datei `SC_Wikelo_Bestand.json` landet in deinen Downloads.
4. Willst du einen anderen Speicherort wählen, klicke mit der rechten Maustaste auf **💾 Bestand speichern**.
5. Kopiere die Datei auf den anderen Rechner, z. B. per USB-Stick oder Cloud-Ordner.
6. Öffne dort den Wikelo-Planer und klicke auf **📂 Bestand laden**.
7. Wähle die Datei `SC_Wikelo_Bestand.json`. Unten erscheint kurz „Bestand geladen" mit der Zahl der Ressourcen.
8. Prüfe links unter **Mein Ressourcen-Bestand** die Mengen. Auch deine „erworben"-Markierungen sind wieder da.

### Tipps

- Laden ersetzt den aktuellen Bestand und die Markierungen komplett. Speichere vorher, wenn du den alten Stand behalten willst.
- Hast du die Datei geladen, schreibt ein Klick auf **💾 Bestand speichern** in manchen Browsern direkt in diese Datei zurück.
- **leeren** löscht nur den Bestand im Browser. Die „erworben"-Markierungen bleiben.

## Fragen

### Warum stimmt ein Angebot nicht mit dem Spiel überein?

Die Angebote stammen aus einer Community-Datenbank. Wikelo rotiert Angebote, und Patches ändern Rezepte. Klicke auf **🔄 Neuesten Stand laden (GitHub)** und prüfe im Spiel gegen.

### Sind meine Daten weg, wenn ich den Browser wechsle?

Ja. Der Bestand liegt nur im localStorage dieses Browsers. Nimm ihn mit **💾 Bestand speichern** und **📂 Bestand laden** mit.

### Was heißt „zurückgezogen"?

Das Angebot gibt es bei Wikelo nicht mehr regulär. Mit **zurückgezogene zeigen** blendest du solche Angebote ein. Sie tragen ein lila Schild.

### Wie bekomme ich die eingebauten Daten zurück?

Klicke mit der rechten Maustaste auf **🔄 Neuesten Stand laden (GitHub)** und bestätige die Rückfrage.
