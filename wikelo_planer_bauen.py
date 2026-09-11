"""
Wikelo Ressourcen-Planer  ->  SC_Wikelo_Planer.html  (eine eigenstaendige Datei)

Baut eine offline lauffaehige GUI (im Browser) aus:
  - Wikelo-Angebote:  https://seeknd.github.io/Wikelo/data/wikelo_data.json
  - Bauplan-Rezepte:  https://api.star-head.de/blueprint   (fuer craftbare Zutaten)
  - Erz-Preise/Orte:  https://api.star-head.de/{commodity,shop,shopitem/price}

Bedienung der fertigen App:
  * Links: Ressourcen-Bestand. Zutat anklicken = "hab ich".
    Menge: [+]/[-]-Knopf, Mausrad ueber der Zeile, Rechtsklick = -1, oder Zahl tippen.
  * Rechts: Wikelo-Angebote, gestaffelt nach Aufwand:
       Sofort verfuegbar  ->  1 Zutat fehlt  ->  2 fehlen  ->  3+ fehlen
    Innerhalb der Baender zusaetzlich nach Beschaffungs-Aufwand sortiert
    (Erz leicht, Creature/Contested-Zone schwer). Umschaltbar auf Artikelgruppe.
  * "Fehlendes beschaffen" je Angebot: Bauplan-Rezept, Favor-Tausch, Erz-Preis/Kaufort.
  * Bereits erhaltene Angebote per "erworben" markieren = ausblenden (persistiert).
  * Bestand + Erworben-Markierungen bleiben im Browser (localStorage) und lassen sich als
    Datei speichern/laden (Format {schema, inventory, acquired}; freier Speicherort per
    File System Access API, sonst Download). Eine vorhandene SC_Wikelo_Bestand.json wird
    beim Neubau automatisch vorgeladen (altes flaches {name: menge} wird weiter gelesen).

Start:  py "wikelo_planer_bauen.py"   (oder Wikelo_Planer_aktualisieren.bat)
"""
import datetime
import http.client
import json
import pathlib
import re
import ssl
import sys
import time
import urllib.request

HOST     = "seeknd.github.io"
BASEPATH = "/Wikelo/"
OUTDIR   = pathlib.Path(__file__).resolve().parent   # Skript-Ordner (laeuft auf jedem PC / in CI)
OUTHTML  = OUTDIR / "SC_Wikelo_Planer.html"
BESTAND  = OUTDIR / "SC_Wikelo_Bestand.json"
STAMP    = datetime.date.today().isoformat()
try:
    from version import VERSION
except Exception:
    VERSION = "0.0.0"

PAT = re.compile(r'^\s*(\d+)\s*x\s+(.*\S)\s*$')

# Die Aufbereitungslogik (Kategorien, Quellen-Klassifikation, Angebote, Waehrungs-Tausch,
# Aufwand-Gewichte) lebt jetzt EINMALIG im Browser (transform() im HTML) \u2013 damit der
# In-App-Refresh dieselbe Logik nutzt wie der Offline-Build. Python buendelt nur die Rohdaten.

# Erz-Zutaten -> Commodity-Basisname (Suffixe (Ore)/(Pure) normalisiert) fuer Preis-Lookup
def ore_commodity(name):
    base = re.sub(r'\s*\((Ore|Pure)\)$', '', str(name).strip()).strip()
    if base in ("Carinite", "Jaclium", "Saldynium", "Sadaryx"):
        return base
    return None


# ----------------------------------------------------------------- Netzwerk
class SiteClient:
    """Eine wiederverwendete HTTPS-Verbindung (Keep-Alive) mit Auto-Reconnect."""
    def __init__(self, host):
        self.host = host; self.ctx = ssl.create_default_context(); self._connect()
    def _connect(self):
        self.conn = http.client.HTTPSConnection(self.host, timeout=30, context=self.ctx)
    def get(self, path, retries=4):
        for _ in range(retries):
            try:
                self.conn.request("GET", path, headers={"User-Agent": "Mozilla/5.0 sc-wikelo-planer"})
                r = self.conn.getresponse(); body = r.read()
                return r.status, body
            except (http.client.HTTPException, OSError):
                try: self.conn.close()
                except Exception: pass
                time.sleep(0.5); self._connect()
        return None, b""
    def close(self):
        try: self.conn.close()
        except Exception: pass


def netzfehler_exit(quelle, grund):
    print(); print("=" * 64)
    print(f" Datenquelle ({quelle}) ist gerade NICHT erreichbar.")
    print(" Grund:", grund)
    print(" Das liegt fast immer an der Quelle/am Netz, nicht an dir.")
    print(" Bitte spaeter nochmal ausfuehren. Die bestehende HTML-Datei")
    print(" bleibt unveraendert erhalten.")
    print("=" * 64); sys.exit(1)


def get_json_url(url, timeout=90):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 sc-wikelo-planer"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


# ----------------------------------------------------------------- Helfer
def parse_recipe(recipe):
    out = []
    for part in str(recipe).split(";"):
        part = part.strip()
        if not part: continue
        m = PAT.match(part)
        if m:
            out.append({"name": m.group(2), "qty": int(m.group(1))})
        else:
            out.append({"name": part, "qty": 1})
    return out


# ----------------------------------------------------------------- Erz-Preise (UEX)
def fetch_prices_uex(need_bases):
    """Erz-Preise (aUEC/SCU) je Commodity-Basisname aus der UEX-API.
    UEX liefert flache price_buy/price_sell (kein Terminal/Ort) -> loc bleibt None."""
    out = {}
    if not need_bases:
        return out
    try:
        res = get_json_url("https://api.uexcorp.space/2.0/commodities")
    except Exception as e:
        print("  Hinweis: UEX-Preise nicht erreichbar -> ohne Erz-Preise.", e)
        return out
    CAP = 100000   # Plausibilitaet: aUEC/SCU; UEX hat fuer neue Erze teils Platzhalter (0 oder Millionen)
    data = res.get("data") if isinstance(res, dict) else res
    for c in (data or []):
        nm = (c.get("name") or "").strip()
        base = re.sub(r'\s*\((Ore|Pure|Raw)\)$', '', nm).strip()
        if base not in need_bases:
            continue
        pb = c.get("price_buy") or 0
        ps = c.get("price_sell") or 0
        entry = out.get(base, {"buy": None, "sell": None, "src": "uex"})
        if 0 < pb <= CAP and (entry["buy"] is None or pb < entry["buy"]["price"]):
            entry["buy"] = {"price": round(pb), "loc": None}
        if 0 < ps <= CAP and (entry["sell"] is None or ps > entry["sell"]["price"]):
            entry["sell"] = {"price": round(ps), "loc": None}
        if entry["buy"] or entry["sell"]:
            out[base] = entry
    return out


# ----------------------------------------------------------------- Rohdaten buendeln
def recipe_names(recipe):
    """Nur die Zutat-Namen aus einem Rezept-String (fuer Bauplan-Filter)."""
    out = []
    for part in str(recipe).split(";"):
        part = part.strip()
        if not part: continue
        m = PAT.match(part)
        out.append(m.group(2) if m else part)
    return out


def load_saved(path):
    """Bestandsdatei einlesen -> (saved_inv, saved_acq).
    Format v2 = {"inventory": {...}, "acquired": {...}}; altes flaches {name: menge}
    wird weiterhin als reiner Bestand gelesen (Abwaertskompatibilitaet)."""
    saved_inv, saved_acq = {}, {}
    if not path.exists():
        return saved_inv, saved_acq
    try:
        b = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        print("  Hinweis: SC_Wikelo_Bestand.json nicht lesbar.", e)
        return saved_inv, saved_acq
    if isinstance(b, dict) and isinstance(b.get("inventory"), dict):
        stock = b["inventory"]
        acquired = b.get("acquired") if isinstance(b.get("acquired"), dict) else {}
    else:
        stock = b if isinstance(b, dict) else {}
        acquired = {}
    for k, v in stock.items():
        try:
            q = max(0, int(round(float(v))))
        except (TypeError, ValueError):
            continue
        if q > 0:
            saved_inv[k] = q
    for k, v in acquired.items():
        if isinstance(v, dict):
            saved_acq[str(k)] = {"reward": str(v.get("reward", k)), "ts": str(v.get("ts", ""))}
        elif v:
            saved_acq[str(k)] = {"reward": str(k), "ts": ""}
    print(f"  Bestand vorgeladen aus {path.name}: {len(saved_inv)} Ressourcen"
          f"{f', {len(saved_acq)} erworben' if saved_acq else ''}.")
    return saved_inv, saved_acq


def build_raw():
    client = SiteClient(HOST)
    print("Lade Wikelo-Daten ...")
    try:
        status, body = client.get(BASEPATH + "data/wikelo_data.json")
    except Exception as e:
        netzfehler_exit("seeknd.github.io/Wikelo", e)
    if status != 200 or not body:
        netzfehler_exit("seeknd.github.io/Wikelo", f"HTTP {status}")
    d = json.loads(body.decode("utf-8"))
    client.close()
    allrecs = list(d["ships"]) + list(d["items"]) + [d["intro_mission"]]
    print(f"  {len(d['ships'])} Schiffe/Fahrzeuge, {len(d['items'])} Items.")

    # Zutat-Namen (fuer Bauplan-Filter + Erz-Bedarf)
    ingredient_names = set()
    for rec in allrecs:
        for nm in recipe_names(rec.get("recipe", "")):
            ingredient_names.add(nm)

    # Baupläne: nur die, deren Name eine Wikelo-Zutat ist (haelt die Datei klein)
    print("Lade Bauplan-Rezepte (star-head.de) ...")
    blueprints = []
    try:
        bp = get_json_url("https://api.star-head.de/blueprint")
        for b in bp:
            nm = b.get("name", "")
            if nm not in ingredient_names:
                continue
            costs = []
            for c in (b.get("costs") or []):
                rn = (c.get("commodity") or {}).get("name")
                if not rn: continue
                costs.append({"name": rn, "qty": c.get("quantity") or 0})
            if costs:
                blueprints.append({"name": nm, "costs": costs})
        print(f"  {len(blueprints)} passende Baupläne.")
    except Exception as e:
        print("  Hinweis: Baupläne nicht erreichbar.", e)

    # Erz-Preise (UEX)
    print("Lade Erz-Preise (uexcorp.space) ...")
    need_ore = {oc for nm in ingredient_names if (oc := ore_commodity(nm))}
    prices = fetch_prices_uex(need_ore)
    print(f"  Preise fuer {sum(1 for v in prices.values() if v.get('buy') or v.get('sell'))} Erz(e).")

    # Gespeicherten Bestand (falls vorhanden) als Vorbelegung
    saved_inv, saved_acq = load_saved(BESTAND)

    return {
        "schema": 2,
        "version": VERSION,
        "generated": STAMP,
        "source": "build",       # wird beim In-App-Refresh ueberschrieben
        "wikelo": {
            "meta": d.get("meta", {}),
            "ships": d.get("ships", []),
            "items": d.get("items", []),
            "intro_mission": d.get("intro_mission", {}),
            "currency_exchanges": d.get("currency_exchanges", []),
        },
        "blueprints": blueprints,
        "prices": prices,
        "saved_inv": saved_inv,
        "saved_acq": saved_acq,   # {mission_name: {reward, ts}} – als erworben markierte Angebote
    }


# ----------------------------------------------------------------- HTML
HTML_TEMPLATE = r"""<!doctype html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>SC Wikelo Ressourcen-Planer</title>
<style>
:root{
  --navy:#0b3d5c; --navy2:#0e4d73; --ink:#0b1620; --panel:#132635; --panel2:#0f1e2b;
  --line:#26445c; --txt:#e7eef4; --dim:#9db4c6; --gold:#ffcf5c; --gold2:#f6b93b;
  --ok:#37c98a; --okbg:#123a2d; --miss:#ff7a7a; --missbg:#3a1c1f; --chip:#1c384c;
}
*{box-sizing:border-box}
html,body{margin:0;background:var(--ink);color:var(--txt);
  font-family:'Segoe UI',Roboto,Arial,sans-serif;font-size:14px}
a{color:var(--gold)}
header{background:linear-gradient(180deg,var(--navy),var(--navy2));padding:10px 16px;
  border-bottom:2px solid var(--gold2);position:sticky;top:0;z-index:20}
.hrow{display:flex;flex-wrap:wrap;gap:10px 18px;align-items:center}
h1{font-size:18px;margin:0;letter-spacing:.3px}
h1 .sub{color:var(--gold);font-weight:600}
.meta{color:var(--dim);font-size:12px}
.controls{display:flex;flex-wrap:wrap;gap:8px 14px;align-items:center;margin-top:8px}
.controls label{font-size:12.5px;color:var(--dim);display:flex;gap:6px;align-items:center}
input[type=text],input[type=number]{background:var(--panel2);border:1px solid var(--line);
  color:var(--txt);border-radius:6px;padding:6px 8px;font-size:13px}
input[type=number]{width:64px}
select{background:var(--panel2);border:1px solid var(--line);color:var(--txt);border-radius:6px;padding:5px 6px;font-size:12.5px}
.btn[disabled]{opacity:.5;cursor:progress}
.btn{background:var(--chip);border:1px solid var(--line);color:var(--txt);border-radius:6px;
  padding:6px 10px;font-size:12.5px;cursor:pointer}
.btn:hover{border-color:var(--gold2)}
.btn.prim{background:var(--gold2);color:#221a00;font-weight:700;border-color:var(--gold2)}
.seg{display:inline-flex;border:1px solid var(--line);border-radius:6px;overflow:hidden}
.seg button{background:var(--panel2);border:0;color:var(--dim);padding:6px 10px;cursor:pointer;font-size:12.5px}
.seg button.on{background:var(--gold2);color:#221a00;font-weight:700}
main{display:grid;grid-template-columns:340px 1fr;gap:14px;padding:14px;align-items:start}
.panel{background:var(--panel);border:1px solid var(--line);border-radius:10px}
.panel > .ph{padding:9px 12px;border-bottom:1px solid var(--line);display:flex;
  justify-content:space-between;align-items:center;gap:8px}
.ph b{font-size:13px}
.side{position:sticky;top:96px;max-height:calc(100vh - 112px);display:flex;flex-direction:column}
.side .scroll{overflow:auto;padding:6px 6px 10px}
.grp{margin:6px 4px 2px;color:var(--gold);font-size:11.5px;text-transform:uppercase;
  letter-spacing:.5px;padding:6px 8px 2px;border-top:1px solid var(--line)}
.grp:first-child{border-top:0}
.res{display:flex;align-items:center;gap:8px;padding:5px 8px;border-radius:7px;cursor:pointer;
  user-select:none}
.res:hover{background:#17303f}
.res.have{background:var(--okbg)}
.res .nm{flex:1;line-height:1.15}
.res .nm small{color:var(--dim);display:block;font-size:10.5px}
.res.have .nm{color:#c9f6e2}
.qbox{display:flex;align-items:center;gap:3px}
.qbtn{width:22px;height:22px;border-radius:5px;border:1px solid var(--line);background:var(--panel2);
  color:var(--txt);cursor:pointer;font-size:14px;line-height:1;display:flex;align-items:center;justify-content:center}
.qbtn:hover{border-color:var(--gold2)}
.qval{min-width:26px;text-align:center;font-variant-numeric:tabular-nums;font-weight:700}
.qval.z{color:var(--dim);font-weight:400}
.qadd{position:relative;padding:8px 8px 2px}
#quickAdd{width:100%;border-color:var(--gold2)}
.qhint{padding:0 12px;color:#7d95a8;font-size:10.5px}
.qsug{position:absolute;left:8px;right:8px;top:calc(100% - 2px);z-index:18;background:var(--panel2);
  border:1px solid var(--gold2);border-top:0;border-radius:0 0 8px 8px;max-height:280px;overflow:auto;display:none;
  box-shadow:0 10px 24px rgba(0,0,0,.4)}
.qsug.open{display:block}
.qsug .s{display:flex;justify-content:space-between;gap:8px;padding:6px 10px;cursor:pointer;font-size:12.5px}
.qsug .s:hover,.qsug .s.act{background:#17303f}
.qsug .s .src2{color:var(--gold);font-size:9.5px;text-transform:uppercase}
.qsug .s .sq{color:var(--ok);font-variant-numeric:tabular-nums;font-weight:700}
.qsug .s small{color:var(--dim)}
.band{margin:0 0 14px}
.band > .bh{display:flex;align-items:center;gap:10px;margin:2px 2px 8px;padding:6px 4px;
  border-bottom:1px solid var(--line)}
.band > .bh .dot{width:11px;height:11px;border-radius:50%}
.band > .bh b{font-size:14px}
.band > .bh .cnt{color:var(--dim);font-size:12px}
.cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(310px,1fr));gap:10px}
.card{background:var(--panel2);border:1px solid var(--line);border-radius:9px;padding:10px 11px;
  border-left:4px solid var(--line);position:relative}
.card.b0{border-left-color:var(--ok)}
.card.b1{border-left-color:var(--gold2)}
.card.b2{border-left-color:#e69138}
.card.b3{border-left-color:#c0392b}
.card.locked{opacity:.62}
.card.acquired{opacity:.6}
.acq-btn{position:absolute;top:8px;right:8px;z-index:2;background:var(--chip);border:1px solid var(--line);
  color:var(--dim);border-radius:6px;padding:2px 7px;font-size:11px;cursor:pointer;line-height:1.4}
.acq-btn:hover{border-color:var(--gold2);color:var(--txt)}
.acq-btn.on{background:var(--okbg);border-color:#2b6b52;color:#bff3dd}
.card h3{margin:0 0 3px;font-size:14px;line-height:1.2;padding-right:78px}
.card .cat{display:inline-block;font-size:10.5px;color:var(--dim);border:1px solid var(--line);
  border-radius:20px;padding:1px 8px;margin-bottom:6px}
.card .mission{color:var(--dim);font-size:11.5px;margin:0 0 7px;font-style:italic}
.chips{display:flex;flex-wrap:wrap;gap:5px}
.chip{font-size:11.5px;border-radius:6px;padding:3px 7px;border:1px solid var(--line);
  background:var(--chip);display:flex;gap:5px;align-items:center;cursor:default}
.chip.ok{background:var(--okbg);border-color:#2b6b52;color:#bff3dd}
.chip.miss{background:var(--missbg);border-color:#6b2f34;color:#ffd0d0;cursor:pointer}
.chip .q{font-weight:700;font-variant-numeric:tabular-nums}
.chip .cr{color:var(--gold);font-size:10px}
.card .foot{display:flex;justify-content:space-between;align-items:center;margin-top:8px;
  color:var(--dim);font-size:11px;gap:8px}
.effort{display:flex;align-items:center;gap:4px;color:var(--dim);font-size:10.5px}
.edot{width:7px;height:7px;border-radius:50%;background:#2f4a5e;display:inline-block}
.edot.on{background:var(--gold2)}
.badge{border-radius:5px;padding:1px 6px;font-size:10.5px;border:1px solid var(--line)}
.badge.rep{color:var(--gold)}
.badge.lock{background:#3a1c1f;border-color:#6b2f34;color:#ffd0d0}
.badge.ret{background:#2a2333;border-color:#4a3d5c;color:#c9b6e6}
.det{margin-top:7px;border-top:1px dashed var(--line);padding-top:7px;display:none}
.det.open{display:block}
.det .row{margin:4px 0;font-size:11.5px;line-height:1.35}
.det .row b{color:var(--txt)}
.det .src{color:var(--gold);font-size:10px;text-transform:uppercase;letter-spacing:.4px}
.det .sub{color:var(--dim)}
.det .opt{display:inline-block;background:var(--chip);border:1px solid var(--line);border-radius:5px;
  padding:1px 6px;margin:2px 4px 0 0;font-size:11px}
.tog{cursor:pointer;color:var(--gold)}
.empty{color:var(--dim);padding:18px;text-align:center}
.legend{display:flex;flex-wrap:wrap;gap:10px;color:var(--dim);font-size:11px;margin-top:6px;align-items:center}
.legend span{display:flex;gap:5px;align-items:center}
.sw{width:10px;height:10px;border-radius:3px;display:inline-block}
.toast{position:fixed;bottom:16px;left:50%;transform:translateX(-50%);background:var(--navy2);
  border:1px solid var(--gold2);color:var(--txt);padding:9px 16px;border-radius:8px;z-index:50;
  opacity:0;transition:opacity .2s;pointer-events:none}
.toast.show{opacity:1}
/* Responsive-Overrides ganz am Ende, damit sie die Basis-Regeln ueberschreiben */
@media(max-width:900px){
  main{grid-template-columns:1fr}
  .side{position:static;max-height:none}
  .side .scroll{max-height:52vh}
}
</style>
</head>
<body>
<header>
  <div class="hrow">
    <h1>SC <span class="sub">Wikelo</span> Ressourcen-Planer</h1>
    <span class="meta" id="meta"></span>
    <span style="flex:1 1 auto"></span>
    <div class="seg" id="langSeg"><button data-lang="de">DE</button><button data-lang="en">EN</button></div>
  </div>
  <div class="controls">
    <div class="seg" id="modeSeg">
      <button data-mode="aufwand" class="on" data-i18n="modeEffort">Nach Aufwand</button>
      <button data-mode="gruppe" data-i18n="modeGroup">Nach Artikelgruppe</button>
    </div>
    <label><span data-i18n="repLabel">Mein Wikelo-Ruf:</span>
      <input type="number" id="myRep" min="0" step="5" value="0" style="width:72px">
    </label>
    <label><input type="checkbox" id="onlyRep"> <span data-i18n="onlyRep">nur erfüllbarer Ruf</span></label>
    <label><input type="checkbox" id="showRetired"> <span data-i18n="showRetired">zurückgezogene zeigen</span></label>
    <label><input type="checkbox" id="showAcquired"> <span data-i18n="showAcquired">erworbene zeigen</span> <span class="meta" id="acqCount"></span></label>
    <input type="text" id="offerSearch" data-i18n-ph="offerSearchPh" placeholder="Angebote filtern…" style="min-width:150px">
    <button class="btn prim" id="btnSave" data-i18n="btnSave" data-i18n-title="btnSaveTitle" title="Klick: speichern · Rechtsklick: Speicherort neu wählen">💾 Bestand speichern</button>
    <button class="btn" id="btnLoad" data-i18n="btnLoad">📂 Bestand laden</button>
    <button class="btn" id="btnReset" data-i18n="btnReset">leeren</button>
    <input type="file" id="fileInput" accept=".json,application/json" style="display:none">
    <span style="flex:1 1 auto"></span>
    <label><span data-i18n="priceLabel">Preise:</span>
      <select id="priceSrc">
        <option value="beide" data-i18n="priceBoth">beide (star-head + UEX)</option>
        <option value="uex" data-i18n="priceUex">nur UEX</option>
        <option value="starhead" data-i18n="priceSh">nur star-head</option>
      </select>
    </label>
    <button class="btn" id="btnRefresh" data-i18n="btnRefresh" data-i18n-title="btnRefreshTitle" title="Angebote + Baupläne + Preise live neu laden">🔄 Daten aktualisieren</button>
  </div>
</header>

<main>
  <aside class="panel side">
    <div class="ph">
      <b data-i18n="panelTitle">Mein Ressourcen-Bestand</b>
      <span class="meta" id="haveCount"></span>
    </div>
    <div class="qadd">
      <input type="text" id="quickAdd" autocomplete="off" data-i18n-ph="quickPh" placeholder='⚡ Schnell-Eingabe: z. B. „carinite 50" · Enter'>
      <div class="qsug" id="quickSug"></div>
    </div>
    <div class="qhint" data-i18n="quickHint">„name zahl" setzt · „name +zahl" addiert · nur „name" = +1 · ↑↓ wählen, Enter übernehmen</div>
    <div style="padding:8px 8px 0"><input type="text" id="resSearch" data-i18n-ph="resSearchPh" placeholder="Ressource suchen…" style="width:100%"></div>
    <div style="padding:5px 12px 0;color:var(--dim);font-size:11px;line-height:1.4">
      <span data-i18n="qtyHint">Menge: Klick +1 · Shift +10 · Strg +50 · Alt +100</span>
      <span style="color:#7d95a8" data-i18n="qtyHint2">(Mausrad = hoch/runter, Rechtsklick = minus, gleiche Modifier)</span>
    </div>
    <label style="padding:6px 12px;color:var(--dim);font-size:12px;display:flex;gap:6px;align-items:center">
      <input type="checkbox" id="onlyHave"> <span data-i18n="onlyHave">nur „hab ich" zeigen</span>
    </label>
    <div class="scroll" id="resList"></div>
  </aside>

  <section>
    <div class="legend">
      <span><i class="sw" style="background:var(--ok)"></i> <span data-i18n="lgNow">sofort</span></span>
      <span><i class="sw" style="background:var(--gold2)"></i> <span data-i18n="lg1">1 fehlt</span></span>
      <span><i class="sw" style="background:#e69138"></i> <span data-i18n="lg2">2 fehlen</span></span>
      <span><i class="sw" style="background:#c0392b"></i> <span data-i18n="lg3">3+ fehlen</span></span>
      <span>· <span data-i18n="lgEffort">Aufwand = Gesamtaufwand des Fehlenden (Menge × Beschaffung)</span></span>
      <span style="margin-left:auto" data-i18n="tip">Menge links: Klick +1 · Shift +10 · Strg +50 · Alt +100 (Mausrad/Rechtsklick ebenso)</span>
    </div>
    <div id="offers" style="margin-top:12px"></div>
  </section>
</main>

<div class="toast" id="toast"></div>

<script id="wikelo-raw" type="application/json">/*__RAW__*/</script>
<script>
const LS_INV = 'sc_wikelo_inv_v1', LS_PREF = 'sc_wikelo_pref_v1', LS_RAW = 'sc_wikelo_raw_v2';
const LS_ACQ = 'sc_wikelo_acq_v1';   // als erworben markierte Angebote (Schluessel = mission_name, stabil)
const RAW_BAKED = JSON.parse(document.getElementById('wikelo-raw').textContent);

// ===== Aufbereitungslogik – EINZIGE Quelle der Wahrheit (Offline-Build wie In-App-Refresh) =====
const CAT_ORDER = {ship:0,vehicle:1,weapon:2,armor:3,gear:4,intro:5};
const SRC_UNIT  = {currency:4,mining:1,creature:2,salvage:2,cz:3,loot:3,craft:2,item:1};
const SRC_ORDER = ['currency','mining','creature','salvage','cz','loot','craft','item'];

// ===== Zweisprachigkeit (DE/EN) =====
let LANG = 'de';
const CAT_LABEL = {
  de:{ship:'Schiff',vehicle:'Fahrzeug',weapon:'Waffe',armor:'Rüstung',gear:'Ausrüstung',intro:'Freischaltung'},
  en:{ship:'Ship',vehicle:'Vehicle',weapon:'Weapon',armor:'Armor',gear:'Gear',intro:'Unlock'}};
const STATUS_LABEL = {
  de:{active:'aktiv','retired-loot':'zurückgezogen (Loot)','retired-store':'zurückgezogen (Store)'},
  en:{active:'active','retired-loot':'retired (loot)','retired-store':'retired (store)'}};
const SRC_LABEL = {
  de:{currency:'Wikelo/Währung',mining:'Mining/Erz',creature:'Creature/Loot',salvage:'Salvage/Vanduul',cz:'CZ/Tech-Loot',loot:'Missions-/Beute-Item',craft:'Craftbar (Bauplan)',item:'Item/Sonstiges'},
  en:{currency:'Wikelo/Currency',mining:'Mining/Ore',creature:'Creature/Loot',salvage:'Salvage/Vanduul',cz:'Contested Zone/Tech Loot',loot:'Mission/Rare Loot',craft:'Craftable (Blueprint)',item:'Item/Other'}};
const SRC_HINT = {
  de:{currency:'Wikelo-Favor/Scrip – per Tausch (siehe unten)',mining:'Mining / teils kaufbar (Preis siehe unten)',creature:'Creature-Jagd (Valakkar / Kopion / Yormandi)',salvage:'Salvage / Vanduul-Gebiete',cz:'Contested Zones / Tech-Loot (PvP-Risiko)',loot:'Missionsbelohnung / seltener Loot',craft:'Craften – Rezept siehe unten',item:'Kauf / Loot'},
  en:{currency:'Wikelo Favor/Scrip – via exchange (see below)',mining:'Mining / partly buyable (price below)',creature:'Creature hunt (Valakkar / Kopion / Yormandi)',salvage:'Salvage / Vanduul areas',cz:'Contested Zones / tech loot (PvP risk)',loot:'Mission reward / rare loot',craft:'Craft it – recipe below',item:'Buy / loot'}};
const BAND_LABEL = {
  de:['Sofort verfügbar','1 Zutat fehlt','2 Zutaten fehlen','3+ Zutaten fehlen'],
  en:['Available now','1 ingredient missing','2 ingredients missing','3+ ingredients missing']};
const I18N = {
  de:{ modeEffort:'Nach Aufwand', modeGroup:'Nach Artikelgruppe', repLabel:'Mein Wikelo-Ruf:',
    onlyRep:'nur erfüllbarer Ruf', showRetired:'zurückgezogene zeigen', showAcquired:'erworbene zeigen',
    offerSearchPh:'Angebote filtern…',
    btnSave:'💾 Bestand speichern', btnSaveTitle:'Klick: speichern · Rechtsklick: Speicherort neu wählen',
    btnLoad:'📂 Bestand laden', btnReset:'leeren', priceLabel:'Preise:',
    priceBoth:'beide (star-head + UEX)', priceUex:'nur UEX', priceSh:'nur star-head',
    btnRefresh:'🔄 Daten aktualisieren', btnRefreshTitle:'Angebote + Baupläne + Preise live neu laden',
    panelTitle:'Mein Ressourcen-Bestand', quickPh:'⚡ Schnell-Eingabe: z. B. „carinite 50" · Enter',
    quickHint:'„name zahl" setzt · „name +zahl" addiert · nur „name" = +1 · ↑↓ wählen, Enter übernehmen',
    resSearchPh:'Ressource suchen…', onlyHave:'nur „hab ich" zeigen',
    qtyHint:'Menge: Klick +1 · Shift +10 · Strg +50 · Alt +100', qtyHint2:'(Mausrad = hoch/runter, Rechtsklick = minus, gleiche Modifier)',
    lgNow:'sofort', lg1:'1 fehlt', lg2:'2 fehlen', lg3:'3+ fehlen',
    lgEffort:'Aufwand = Gesamtaufwand des Fehlenden (Menge × Beschaffung)',
    tip:'Menge links: Klick +1 · Shift +10 · Strg +50 · Alt +100 (Mausrad/Rechtsklick ebenso)',
    marked:'{n} markiert', inOffers:'in {n} Angebot', inOffersPl:'in {n} Angeboten', craftTag:'craftbar', oreTag:'Erz',
    acqBtnMark:'✓ erworben', acqBtnUnmark:'↩ zurück',
    acqBtnMarkTitle:'Als erworben markieren und ausblenden', acqBtnUnmarkTitle:'Markierung entfernen (wieder einblenden)',
    acqCount:'({n} erworben)', acqOrphan:'{n} erworben, aber nicht mehr in den Daten',
    toastAcq:'als erworben markiert – ausgeblendet', toastUnacq:'wieder eingeblendet',
    getMissing:'Fehlendes beschaffen', complete:'✓ komplett', effort:'Aufwand', repNeed:'braucht Ruf {n}', repRew:'Belohnung +{n} Ruf',
    haveShort:'hast {have}/{need}', offer:'Angebot', offers:'Angebote', noRes:'Keine Ressource gefunden.', noOffers:'Keine Angebote für diese Filter.',
    exchange:'Tausch:', priceBuy:'kaufbar ≈ {p} aUEC/SCU', priceSell:'Verkaufswert ≈ {p} aUEC/SCU', avgUex:'Ø UEX', avgMarket:'Ø Markt',
    confirmClear:'Wirklich den ganzen Bestand leeren?', confirmReset:'Auf die eingebauten Build-Daten zurücksetzen (gecachte Aktualisierung verwerfen)?',
    toastReset:'Auf Build-Daten zurückgesetzt', toastRefreshed:'Daten aktualisiert · {n} Angebote, Patch {p}',
    toastRefreshFail:'Aktualisierung fehlgeschlagen (Quelle offline?) – bestehende Daten bleiben',
    toastBpFail:'Baupläne (star-head) nicht erreichbar', toastPriceFail:'Preise (UEX) nicht erreichbar',
    toastSaved:'Bestand gespeichert', toastLoaded:'Bestand geladen: {n} Ressourcen',
    toastBadFile:'Ungültige Datei (kein Bestand-JSON)', toastPreload:'Bestand aus SC_Wikelo_Bestand.json vorgeladen',
    loading:'⏳ lädt…', metaBuilt:'gebaut {d}', metaRefreshed:'aktualisiert {d}',
    metaLine:'v{v} · Patch {patch} · Daten {data} · {no} Angebote · {ni} Ressourcen · {fresh}' },
  en:{ modeEffort:'By effort', modeGroup:'By category', repLabel:'My Wikelo reputation:',
    onlyRep:'only reachable rep', showRetired:'show retired', showAcquired:'show acquired',
    offerSearchPh:'Filter offers…',
    btnSave:'💾 Save stock', btnSaveTitle:'Click: save · Right-click: choose new location',
    btnLoad:'📂 Load stock', btnReset:'clear', priceLabel:'Prices:',
    priceBoth:'both (star-head + UEX)', priceUex:'UEX only', priceSh:'star-head only',
    btnRefresh:'🔄 Refresh data', btnRefreshTitle:'Reload offers + blueprints + prices live',
    panelTitle:'My resource stock', quickPh:'⚡ Quick entry: e.g. "carinite 50" · Enter',
    quickHint:'"name number" sets · "name +number" adds · just "name" = +1 · ↑↓ to choose, Enter to apply',
    resSearchPh:'Search resource…', onlyHave:'show only "have"',
    qtyHint:'Amount: click +1 · Shift +10 · Ctrl +50 · Alt +100', qtyHint2:'(wheel = up/down, right-click = minus, same modifiers)',
    lgNow:'now', lg1:'1 missing', lg2:'2 missing', lg3:'3+ missing',
    lgEffort:'Effort = total effort for the missing (amount × sourcing)',
    tip:'Amount on the left: click +1 · Shift +10 · Ctrl +50 · Alt +100 (wheel/right-click too)',
    marked:'{n} marked', inOffers:'in {n} offer', inOffersPl:'in {n} offers', craftTag:'craftable', oreTag:'ore',
    acqBtnMark:'✓ acquired', acqBtnUnmark:'↩ undo',
    acqBtnMarkTitle:'Mark as acquired and hide', acqBtnUnmarkTitle:'Remove mark (show again)',
    acqCount:'({n} acquired)', acqOrphan:'{n} acquired but no longer in the data',
    toastAcq:'marked as acquired – hidden', toastUnacq:'shown again',
    getMissing:'Get missing', complete:'✓ complete', effort:'Effort', repNeed:'needs rep {n}', repRew:'reward +{n} rep',
    haveShort:'have {have}/{need}', offer:'offer', offers:'offers', noRes:'No resource found.', noOffers:'No offers for these filters.',
    exchange:'Exchange:', priceBuy:'buyable ≈ {p} aUEC/SCU', priceSell:'sell value ≈ {p} aUEC/SCU', avgUex:'UEX avg', avgMarket:'market avg',
    confirmClear:'Really clear the entire stock?', confirmReset:'Reset to the built-in build data (discard cached refresh)?',
    toastReset:'Reset to build data', toastRefreshed:'Data refreshed · {n} offers, patch {p}',
    toastRefreshFail:'Refresh failed (source offline?) – existing data kept',
    toastBpFail:'Blueprints (star-head) unreachable', toastPriceFail:'Prices (UEX) unreachable',
    toastSaved:'Stock saved', toastLoaded:'Stock loaded: {n} resources',
    toastBadFile:'Invalid file (not a stock JSON)', toastPreload:'Stock preloaded from SC_Wikelo_Bestand.json',
    loading:'⏳ loading…', metaBuilt:'built {d}', metaRefreshed:'refreshed {d}',
    metaLine:'v{v} · patch {patch} · data {data} · {no} offers · {ni} resources · {fresh}' }
};
function t(k,p){ let s=(I18N[LANG]&&I18N[LANG][k]!=null)?I18N[LANG][k]:(I18N.de[k]!=null?I18N.de[k]:k);
  if(p) for(const key in p) s=s.split('{'+key+'}').join(p[key]); return s; }
const catLabel=k=>(CAT_LABEL[LANG][k]||CAT_LABEL.de[k]||k);
const srcLabel=k=>(SRC_LABEL[LANG][k]||SRC_LABEL.de[k]||k);
const srcHint =k=>(SRC_HINT[LANG][k]||SRC_HINT.de[k]||'');
const statusLabel=k=>(STATUS_LABEL[LANG][k]||STATUS_LABEL.de[k]||k);
const bandLabel=i=>(BAND_LABEL[LANG][i]||BAND_LABEL.de[i]);
const RECIPE_RE = /^\s*(\d+)\s*x\s+(.*\S)\s*$/;
const cmp = (a,b)=> a<b?-1:a>b?1:0;   // code-point-Vergleich wie Python (kein localeCompare)

function parseRecipe(s){
  const out=[];
  for(let part of String(s==null?'':s).split(';')){
    part=part.trim(); if(!part) continue;
    const m=part.match(RECIPE_RE);
    out.push(m ? {name:m[2], qty:parseInt(m[1],10)} : {name:part, qty:1});
  }
  return out;
}
function nameOf(rec){ return String(rec.reward||rec.name||rec.mission_name||'').trim(); }
function oreCommodity(name){
  const base=String(name).trim().replace(/\s*\((Ore|Pure)\)$/,'').trim();
  return ['Carinite','Jaclium','Saldynium','Sadaryx'].includes(base)?base:null;
}
function classify(name, craftable){
  const n=String(name).toLowerCase();
  if(['Wikelo Favor','Polaris Bit','MG Scrip','Council Scrip'].includes(name)) return 'currency';
  if(['(ore)','(pure)','saldynium','jaclium','carinite','sadaryx','quantanium fuel'].some(w=>n.includes(w))) return 'mining';
  if(['valakkar','kopion','yormandi','grazer','fungus'].some(w=>n.includes(w))) return 'creature';
  if(['medal','marker','badge','artifact fragment','metamaterial','test #'].some(w=>n.includes(w))) return 'loot';
  if(n.includes('vanduul')) return 'salvage';
  if(['rcmbnt','comp-board','secure drive','drive'].some(w=>n.includes(w))) return 'cz';
  if(craftable) return 'craft';
  return 'item';
}
function transform(raw){
  const w = raw.wikelo||{};
  const allrecs = [...(w.ships||[]), ...(w.items||[]), ...(w.intro_mission?[w.intro_mission]:[])];
  const bpMap={};
  for(const b of (raw.blueprints||[])) if(b && b.name && b.costs && b.costs.length) bpMap[b.name]=b.costs;
  const catRank=a=> (CAT_ORDER[a]!=null?CAT_ORDER[a]:9);
  const offers = allrecs.map(rec=>({
    id: rec.id||'', reward: nameOf(rec), artkey: rec.category||'',
    mission: String(rec.mission_name||'').trim(), recipe: parseRecipe(rec.recipe||''),
    rep_req: rec.reputation_required||0, rep_rew: rec.reputation_reward||0,
    status: rec.status||'active',
  })).sort((a,b)=> (catRank(a.artkey)-catRank(b.artkey)) || cmp(a.reward.toLowerCase(), b.reward.toLowerCase()));
  const currency_map={};
  for(const c of (w.currency_exchanges||[])){
    const rew=String(c.reward||'').trim(); if(!rew) continue;
    (currency_map[rew]=currency_map[rew]||[]).push({recipe:parseRecipe(c.recipe||''), recipe_raw:String(c.recipe||'').trim(), mission:c.mission_name||''});
  }
  const freq={};
  for(const o of offers) for(const it of o.recipe) freq[it.name]=(freq[it.name]||0)+1;
  const names=Object.keys(freq).sort((a,b)=> (freq[b]-freq[a]) || cmp(a.toLowerCase(), b.toLowerCase()));
  const ingredients={};
  for(const nm of names) ingredients[nm]={ src:classify(nm, nm in bpMap), n_offers:freq[nm], blueprint:bpMap[nm]||null, ore:oreCommodity(nm) };
  return {
    meta:{ version:raw.version||'0.0.0', patch:(w.meta||{}).current_patch||'?', data_updated:(w.meta||{}).data_updated||'?',
           generated:raw.generated||'', source:raw.source||'build', n_offers:offers.length, n_ingredients:names.length },
    offers, currency_map, prices:raw.prices||{}, ingredients,
    src_order:SRC_ORDER, cat_order:CAT_ORDER, saved_inv:raw.saved_inv||{}, saved_acq:raw.saved_acq||{},
  };
}

// Aktive Rohdaten: gecachter Refresh (falls Schema passt) sonst eingebackene Build-Daten
function loadRaw(){
  try{ const c=JSON.parse(localStorage.getItem(LS_RAW)||'null');
    if(c && c.schema===RAW_BAKED.schema && c.wikelo) return c; }catch(e){}
  return RAW_BAKED;
}
let RAW = loadRaw();
let DATA = transform(RAW);

// ---- state ----
let inv = {};
let acq = {};   // {mission_name: {reward, ts}} – erworben markiert (per mission_name, refresh-stabil)
let pref = {mode:'aufwand', myRep:0, onlyRep:false, showRetired:false, showAcquired:false, onlyHave:false, priceSrc:'beide', lang:'de'};
let lsInv = null;
try{ lsInv = JSON.parse(localStorage.getItem(LS_INV)||'null'); }catch(e){}
if(lsInv && Object.keys(lsInv).length){ inv = lsInv; }
else { inv = Object.assign({}, DATA.saved_inv||{}); }   // Vorbelegung aus SC_Wikelo_Bestand.json
let lsAcq = null;
try{ lsAcq = JSON.parse(localStorage.getItem(LS_ACQ)||'null'); }catch(e){}
if(lsAcq && Object.keys(lsAcq).length){ acq = lsAcq; }
else { acq = Object.assign({}, DATA.saved_acq||{}); }    // gleiche Vorbelegungs-Logik wie Bestand
try{ Object.assign(pref, JSON.parse(localStorage.getItem(LS_PREF)||'{}')||{}); }catch(e){}

function saveInv(){ try{localStorage.setItem(LS_INV, JSON.stringify(inv));}catch(e){} }
function saveAcq(){ try{localStorage.setItem(LS_ACQ, JSON.stringify(acq));}catch(e){} }
function savePref(){ try{localStorage.setItem(LS_PREF, JSON.stringify(pref));}catch(e){} }
function have(n){ return inv[n]||0; }
function setHave(n,q){ q=Math.max(0,Math.round(q||0)); if(q<=0) delete inv[n]; else inv[n]=q; saveInv(); rerenderAll(); }
// Erworben-Markierung per mission_name (stabiler als die positionsabhaengige offer.id)
function isAcq(o){ return !!(o && o.mission && acq[o.mission]); }
function toggleAcq(mkey){
  if(!mkey) return;
  if(acq[mkey]){ delete acq[mkey]; toast(t('toastUnacq')); }
  else { const o=DATA.offers.find(x=>x.mission===mkey); acq[mkey]={reward:o?o.reward:mkey, ts:new Date().toISOString()}; toast(t('toastAcq')); }
  saveAcq(); rerenderAll();
}

// ---- helpers ----
const $=s=>document.querySelector(s), $$=s=>[...document.querySelectorAll(s)];
function toast(m){ const t=$('#toast'); t.textContent=m; t.classList.add('show'); clearTimeout(t._t); t._t=setTimeout(()=>t.classList.remove('show'),1800); }
function esc(s){ return (s||'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c])); }
function fmt(n){ return Math.round(n).toLocaleString('de-DE'); }
function unitOf(name){ const info=DATA.ingredients[name]||{}; return SRC_UNIT[info.src]||2; }
// Aufwand (mengengewichtet) -> 1..5 Sterne, log-gestaucht (kalibriert: Wikelo Arrive≈1★, Idris≈5★)
function starsOf(raw){ if(raw<=0) return 0; const l=Math.log10(raw);
  return l<1?1 : l<1.6?2 : l<2.1?3 : l<2.7?4 : 5; }

// offer analysis
function analyze(o){
  let missTypes=0, missQty=0, missing=[], effort=0;
  for(const it of o.recipe){
    const need=it.qty, has=have(it.name), gap=Math.max(0,need-has);
    if(gap>0){ missTypes++; missQty+=gap; effort+=gap*unitOf(it.name); missing.push({name:it.name, gap, need, has}); }
  }
  const band = missTypes>=3?3:missTypes;
  const stars = starsOf(effort);                          // Gesamt-Beschaffungsaufwand des Fehlenden
  const repOk = (pref.myRep||0) >= (o.rep_req||0);
  return {missTypes, missQty, missing, band, effort, stars, repOk};
}

const BANDS=[ {k:0,dot:'var(--ok)'}, {k:1,dot:'var(--gold2)'}, {k:2,dot:'#e69138'}, {k:3,dot:'#c0392b'} ];

// ---- inventory panel ----
function renderRes(){
  const q=($('#resSearch').value||'').toLowerCase();
  const onlyHave=pref.onlyHave;
  const groups={};
  for(const [nm,info] of Object.entries(DATA.ingredients)){
    if(q && !nm.toLowerCase().includes(q)) continue;
    if(onlyHave && !have(nm)) continue;
    (groups[info.src]=groups[info.src]||[]).push([nm,info]);
  }
  let html='';
  for(const src of DATA.src_order){
    const arr=groups[src]; if(!arr||!arr.length) continue;
    html+=`<div class="grp">${esc(srcLabel(src))}</div>`;
    for(const [nm,info] of arr){
      const v=have(nm);
      const sub = (info.n_offers>1? t('inOffersPl',{n:info.n_offers}) : t('inOffers',{n:info.n_offers}))
        + (info.blueprint?' · '+t('craftTag'):'') + (info.ore?' · '+t('oreTag'):'');
      html+=`<div class="res ${v?'have':''}" data-n="${esc(nm)}">
        <div class="qbox">
          <button class="qbtn" data-a="dec">−</button>
          <span class="qval ${v?'':'z'}">${v}</span>
          <button class="qbtn" data-a="inc">+</button>
        </div>
        <div class="nm">${esc(nm)}<small>${esc(sub)}</small></div>
      </div>`;
    }
  }
  $('#resList').innerHTML = html || `<div class="empty">${t('noRes')}</div>`;
  const hc=Object.keys(inv).length;
  $('#haveCount').textContent = hc? t('marked',{n:hc}) : '';
}

// ---- procurement hint for a missing ingredient ----
function hintFor(name){
  const info=DATA.ingredients[name]||{};
  let extra='';
  if(info.blueprint){
    extra = '🔨 '+info.blueprint.map(c=>`${c.qty}× ${esc(c.name)}`).join(', ');
  }
  else if(DATA.currency_map[name]){
    const opts=DATA.currency_map[name].map(o=> `<span class="opt">${esc(o.recipe_raw||o.mission||'')}</span>`).join('');
    extra = t('exchange')+' '+opts;
  }
  else if(info.ore && DATA.prices[info.ore]){
    const p=DATA.prices[info.ore], q=p.src==='uex'?t('avgUex'):t('avgMarket');
    if(p.buy) extra = t('priceBuy',{p:fmt(p.buy.price)}) + (p.buy.loc?` (${esc(p.buy.loc)})`:` (${q})`);
    else if(p.sell) extra = t('priceSell',{p:fmt(p.sell.price)}) + (p.sell.loc?` (${esc(p.sell.loc)})`:` (${q})`);
  }
  return {src:info.src, hint:srcHint(info.src), extra};
}

// ---- offers ----
function offerCard(o){
  const a=analyze(o);
  const retired = o.status!=='active';
  const locked = !a.repOk;
  const chips = o.recipe.map(it=>{
    const need=it.qty, has=have(it.name), ok=has>=need;
    const info=DATA.ingredients[it.name]||{};
    const cr = info.blueprint? '<span class="cr" title="craftbar">🔨</span>':'';
    return `<span class="chip ${ok?'ok':'miss'}" data-n="${esc(it.name)}" ${ok?'':'data-miss="1"'}>
      <span class="q">${need}×</span>${esc(it.name)}${cr}${ok?'':` <small>(${has}/${need})</small>`}</span>`;
  }).join('');
  // Details: alle fehlenden Zutaten mit Beschaffungs-Hinweis
  let detHtml='';
  if(a.missing.length){
    detHtml = `<div class="det">`+ a.missing.map(m=>{
        const h=hintFor(m.name);
        return `<div class="row"><span class="src">${esc(srcLabel(h.src))}</span>
          <b>${m.gap}× ${esc(m.name)}</b>${m.has?` <span class="sub">(${t('haveShort',{have:m.has,need:m.need})})</span>`:''}
          <div class="sub">${h.extra||esc(h.hint)}</div></div>`;
      }).join('') + `</div>`;
  }
  // Aufwand-Sterne (1..5) – mengengewichtet
  const eff = a.stars;
  const dots = a.missTypes? `<span class="effort">${t('effort')} `+
    [1,2,3,4,5].map(i=>`<i class="edot ${i<=eff?'on':''}"></i>`).join('')+`</span>` : '';
  const repBadge = o.rep_req? `<span class="badge ${locked?'lock':'rep'}">${t('repNeed',{n:o.rep_req})}${locked?' ⚠':''}</span>`:'';
  const rewBadge = o.rep_rew? `<span class="badge rep">${t('repRew',{n:o.rep_rew})}</span>`:'';
  const retBadge = retired? `<span class="badge ret">${esc(statusLabel(o.status))}</span>`:'';
  const acqd = isAcq(o);
  const acqBtn = `<button class="acq-btn${acqd?' on':''}" data-acq="1" title="${esc(t(acqd?'acqBtnUnmarkTitle':'acqBtnMarkTitle'))}">${t(acqd?'acqBtnUnmark':'acqBtnMark')}</button>`;
  return `<div class="card b${a.band} ${locked?'locked':''}${acqd?' acquired':''}" data-mkey="${esc(o.mission)}">
    ${acqBtn}
    <h3>${esc(o.reward||o.mission)}</h3>
    <span class="cat">${esc(catLabel(o.artkey))}</span>
    ${o.mission&&o.mission!==o.reward?`<div class="mission">„${esc(o.mission)}"</div>`:''}
    <div class="chips">${chips}</div>
    ${detHtml}
    <div class="foot">
      <span>${a.missing.length?`<span class="tog">${t('getMissing')} ▾</span>`:`<span style="color:var(--ok)">${t('complete')}</span>`}</span>
      <span style="display:flex;gap:8px;align-items:center">${dots} ${retBadge} ${rewBadge} ${repBadge}</span>
    </div>
  </div>`;
}

function passFilter(o,a){
  if(isAcq(o) && !pref.showAcquired) return false;   // erworben -> ausgeblendet (ausser Anzeige aktiv)
  if(o.status!=='active' && !pref.showRetired) return false;
  if(pref.onlyRep && !a.repOk) return false;
  const q=($('#offerSearch').value||'').toLowerCase();
  if(q){
    const hay=(o.reward+' '+o.mission+' '+catLabel(o.artkey)+' '+o.artkey+' '+o.recipe.map(r=>r.name).join(' ')).toLowerCase();
    if(!hay.includes(q)) return false;
  }
  return true;
}

function sortCmp(p,q){
  const A=[p.a.band, p.a.repOk?0:1, p.a.effort, p.a.missQty, p.o.reward.toLowerCase()];
  const B=[q.a.band, q.a.repOk?0:1, q.a.effort, q.a.missQty, q.o.reward.toLowerCase()];
  for(let i=0;i<A.length;i++){ if(A[i]<B[i])return -1; if(A[i]>B[i])return 1; } return 0;
}

function renderOffers(){
  const rows=DATA.offers.map(o=>({o,a:analyze(o)})).filter(x=>passFilter(x.o,x.a));
  let html='';
  if(pref.mode==='aufwand'){
    for(const b of BANDS){
      const items=rows.filter(x=>x.a.band===b.k).sort(sortCmp);
      if(!items.length) continue;
      const cnt=items.length+' '+(items.length>1?t('offers'):t('offer'));
      html+=`<div class="band"><div class="bh"><span class="dot" style="background:${b.dot}"></span>
        <b>${esc(bandLabel(b.k))}</b><span class="cnt">${cnt}</span></div>
        <div class="cards">${items.map(x=>offerCard(x.o)).join('')}</div></div>`;
    }
  } else {
    const cats=Object.keys(DATA.cat_order).sort((a,b)=>DATA.cat_order[a]-DATA.cat_order[b]);
    for(const cat of cats){
      const items=rows.filter(x=>x.o.artkey===cat).sort(sortCmp);
      if(!items.length) continue;
      html+=`<div class="band"><div class="bh"><span class="dot" style="background:var(--navy2)"></span>
        <b>${esc(catLabel(cat))}</b><span class="cnt">${items.length}</span></div>
        <div class="cards">${items.map(x=>offerCard(x.o)).join('')}</div></div>`;
    }
  }
  $('#offers').innerHTML = html || `<div class="empty">${t('noOffers')}</div>`;
}

function updateAcqCount(){
  const el=$('#acqCount'); if(!el) return;
  const total=Object.keys(acq).length;
  el.textContent = total? t('acqCount',{n:total}) : '';
  // Orphans = erworbene Angebote, deren mission_name in den aktuellen Daten fehlt (nach Refresh moeglich)
  const present=new Set(DATA.offers.map(o=>o.mission));
  const orphans=Object.entries(acq).filter(([k])=>!present.has(k)).map(([,v])=>v.reward);
  el.title = orphans.length? t('acqOrphan',{n:orphans.length})+': '+orphans.join(', ') : '';
}
function rerenderAll(){ renderRes(); renderOffers(); updateAcqCount(); }

// ---- Schnell-Eingabe (Kommando-Leiste) ----
let quickMatches=[], quickIndex=0;
function parseQuick(raw){
  const m=raw.match(/^(.*?)\s+([+]?\d+)\s*$/);
  return m ? {query:m[1].trim(), num:m[2]} : {query:raw.trim(), num:null};
}
function qMatch(q){
  q=q.toLowerCase().trim(); if(!q) return [];
  const toks=q.split(/\s+/), out=[];
  for(const name of Object.keys(DATA.ingredients)){
    const ln=name.toLowerCase();
    if(!toks.every(t=>ln.includes(t))) continue;
    let score=0;
    if(ln.startsWith(q)) score-=100;
    const idx=ln.indexOf(q); if(idx>=0) score-=(50-Math.min(idx,49));
    score-=(DATA.ingredients[name].n_offers||0)*0.2;   // häufige Zutaten bevorzugen
    score+=ln.length*0.02;
    out.push({name,score});
  }
  out.sort((a,b)=>a.score-b.score);
  return out.slice(0,8);
}
function renderQuick(){
  const raw=$('#quickAdd').value; const {query,num}=parseQuick(raw);
  quickMatches=qMatch(query);
  if(quickIndex>=quickMatches.length) quickIndex=0;
  const box=$('#quickSug');
  if(!raw.trim() || !quickMatches.length){ box.classList.remove('open'); box.innerHTML=''; return; }
  box.innerHTML=quickMatches.map((m,i)=>{
    const cur=have(m.name), info=DATA.ingredients[m.name]||{};
    let tgt=''; if(num!=null){ const n=+num.replace('+',''); tgt = num[0]==='+'?`→ ${cur+n}`:`→ ${n}`; }
    return `<div class="s ${i===quickIndex?'act':''}" data-i="${i}">
      <span><span class="src2">${esc(srcLabel(info.src))}</span> ${esc(m.name)} <small>(${cur})</small></span>
      <span class="sq">${tgt}</span></div>`;
  }).join('');
  box.classList.add('open');
}
function applyQuick(i){
  const idx=(i!=null)?i:quickIndex, m=quickMatches[idx]; if(!m) return;
  const {num}=parseQuick($('#quickAdd').value);
  if(num==null){ setHave(m.name, have(m.name)+1); toast('+1 '+m.name); }
  else if(num[0]==='+'){ const n=+num.slice(1)||0; setHave(m.name, have(m.name)+n); toast(m.name+' +'+n); }
  else { const n=+num||0; setHave(m.name, n); toast(m.name+' = '+n); }
  $('#quickAdd').value=''; quickIndex=0; renderQuick(); $('#quickAdd').focus();
}

// ---- Schrittweite per Modifier: Klick +1 · Shift +10 · Strg +50 · Alt +100 ----
function stepOf(e){ if(e.altKey) return 100; if(e.ctrlKey||e.metaKey) return 50; if(e.shiftKey) return 10; return 1; }

// ---- events: inventory ----
$('#resList').addEventListener('click', e=>{
  const row=e.target.closest('.res'); if(!row) return;
  const n=row.dataset.n, s=stepOf(e);
  const btn=e.target.closest('.qbtn');
  if(btn){ setHave(n, have(n)+(btn.dataset.a==='inc'?s:-s)); return; }
  // Zeilenklick: mit Modifier +Schritt, sonst an/aus (0<->1)
  if(s>1) setHave(n, have(n)+s);
  else setHave(n, have(n)>0?0:1);
});
$('#resList').addEventListener('contextmenu', e=>{
  const row=e.target.closest('.res'); if(!row) return;
  e.preventDefault(); setHave(row.dataset.n, have(row.dataset.n)-stepOf(e));
});
$('#resList').addEventListener('wheel', e=>{
  const row=e.target.closest('.res'); if(!row) return;
  e.preventDefault(); const s=stepOf(e); setHave(row.dataset.n, have(row.dataset.n)+(e.deltaY<0?s:-s));
},{passive:false});

// ---- events: offers ----
$('#offers').addEventListener('click', e=>{
  const ab=e.target.closest('.acq-btn');
  if(ab){ const card=ab.closest('.card'); if(card) toggleAcq(card.dataset.mkey); return; }
  const tog=e.target.closest('.tog');
  if(tog){ const d=tog.closest('.card').querySelector('.det'); if(d){ d.classList.toggle('open');
    tog.textContent = t('getMissing')+(d.classList.contains('open')?' ▴':' ▾'); } return; }
  const chip=e.target.closest('.chip[data-miss]');
  if(chip){ const s=stepOf(e); setHave(chip.dataset.n, have(chip.dataset.n)+s); toast('+'+s+' '+chip.dataset.n); }
});

// ---- events: filters ----
// ---- events: Schnell-Eingabe ----
$('#quickAdd').addEventListener('input', renderQuick);
$('#quickAdd').addEventListener('keydown', e=>{
  if(e.key==='ArrowDown'){ e.preventDefault(); quickIndex=Math.min(quickIndex+1, quickMatches.length-1); renderQuick(); }
  else if(e.key==='ArrowUp'){ e.preventDefault(); quickIndex=Math.max(quickIndex-1, 0); renderQuick(); }
  else if(e.key==='Enter'){ e.preventDefault(); applyQuick(); }
  else if(e.key==='Escape'){ $('#quickAdd').value=''; renderQuick(); }
});
$('#quickSug').addEventListener('mousedown', e=>{ const s=e.target.closest('.s'); if(s){ e.preventDefault(); applyQuick(+s.dataset.i); } });
document.addEventListener('click', e=>{ if(!e.target.closest('.qadd')) $('#quickSug').classList.remove('open'); });

$('#resSearch').addEventListener('input', renderRes);
$('#offerSearch').addEventListener('input', renderOffers);
$('#onlyHave').addEventListener('change', e=>{pref.onlyHave=e.target.checked; savePref(); renderRes();});
$('#myRep').addEventListener('input', e=>{pref.myRep=+e.target.value||0; savePref(); renderOffers();});
$('#onlyRep').addEventListener('change', e=>{pref.onlyRep=e.target.checked; savePref(); renderOffers();});
$('#showRetired').addEventListener('change', e=>{pref.showRetired=e.target.checked; savePref(); renderOffers();});
$('#showAcquired').addEventListener('change', e=>{pref.showAcquired=e.target.checked; savePref(); renderOffers();});
$('#modeSeg').addEventListener('click', e=>{
  const b=e.target.closest('button[data-mode]'); if(!b) return;
  pref.mode=b.dataset.mode; savePref();
  $$('#modeSeg button').forEach(x=>x.classList.toggle('on',x===b)); renderOffers();
});

// ---- Bestand speichern / laden (Datei, freier Speicherort) ----
// Speicherformat v2: {schema, inventory:{name:menge}, acquired:{mission:{reward,ts}}}.
// Wo verfuegbar (Chromium, sicherer Kontext) nutzt Speichern/Laden die File System Access API,
// sodass der Ort frei waehlbar ist und ein geladenes File beim naechsten Speichern zurueckgeschrieben
// wird. Sonst Fallback auf Download / Datei-Auswahl. Unter file:// ist die API oft gesperrt -> Fallback.
let fileHandle = null;   // zuletzt gewaehltes File (nur waehrend der Sitzung), fuer Wiederspeichern
const FS_TYPES = [{description:'Wikelo-Bestand (JSON)', accept:{'application/json':['.json']}}];
function buildSaveObject(){ return {schema:2, inventory:inv, acquired:acq}; }

function downloadStock(text){
  const blob=new Blob([text],{type:'application/json'});
  const url=URL.createObjectURL(blob);
  const a=document.createElement('a'); a.href=url; a.download='SC_Wikelo_Bestand.json';
  document.body.appendChild(a); a.click(); a.remove();
  setTimeout(()=>URL.revokeObjectURL(url),1000);
  toast(t('toastSaved'));
}
async function saveStock(){
  const text=JSON.stringify(buildSaveObject(),null,1);
  if(window.showSaveFilePicker){
    try{
      if(!fileHandle) fileHandle=await window.showSaveFilePicker({suggestedName:'SC_Wikelo_Bestand.json', types:FS_TYPES});
      const w=await fileHandle.createWritable(); await w.write(text); await w.close();
      toast(t('toastSaved')); return;
    }catch(err){
      fileHandle=null;
      if(err && err.name==='AbortError') return;   // Nutzer hat Dialog abgebrochen -> NICHT herunterladen
      // andere Fehler (kein Zugriff / file://): Fallback auf Download
    }
  }
  downloadStock(text);
}
function applyLoaded(text){
  try{
    const o=JSON.parse(text);
    if(typeof o!=='object'||o===null||Array.isArray(o)) throw 0;
    // v2 mit inventory/acquired, sonst altes flaches {name:menge} = nur Bestand
    const stock = (o.inventory && typeof o.inventory==='object') ? o.inventory : o;
    const acquired = (o.inventory && o.acquired && typeof o.acquired==='object') ? o.acquired : {};
    inv={}; for(const [k,v] of Object.entries(stock)){ const q=Math.max(0,Math.round(+v||0)); if(q>0) inv[k]=q; }
    acq={}; for(const [k,v] of Object.entries(acquired)){
      if(v && typeof v==='object') acq[k]={reward:v.reward||k, ts:v.ts||''};
      else if(v) acq[k]={reward:k, ts:''};
    }
    saveInv(); saveAcq(); rerenderAll(); toast(t('toastLoaded',{n:Object.keys(inv).length}));
  }catch(err){ toast(t('toastBadFile')); }
}
async function loadStock(){
  if(window.showOpenFilePicker){
    try{
      const [h]=await window.showOpenFilePicker({types:FS_TYPES, multiple:false});
      const f=await h.getFile(); const text=await f.text();
      applyLoaded(text); fileHandle=h;   // gewaehltes File merken -> Speichern schreibt dorthin zurueck
      return;
    }catch(err){ if(err && err.name==='AbortError') return; /* sonst: Fallback */ }
  }
  $('#fileInput').click();
}
$('#btnSave').addEventListener('click', saveStock);
$('#btnSave').addEventListener('contextmenu', e=>{ e.preventDefault(); fileHandle=null; saveStock(); });  // Rechtsklick: Speicherort neu waehlen
$('#btnLoad').addEventListener('click', loadStock);
$('#fileInput').addEventListener('change', e=>{   // Fallback ohne File System Access API
  const f=e.target.files[0]; if(!f) return;
  const rd=new FileReader();
  rd.onload=()=>applyLoaded(rd.result);
  rd.readAsText(f); e.target.value='';
});
$('#btnReset').addEventListener('click', ()=>{ if(confirm(t('confirmClear'))){ inv={}; saveInv(); rerenderAll(); } });

// ---- In-App-Datenaktualisierung (Refresh) ----
const EP = {
  wikelo:     'https://seeknd.github.io/Wikelo/data/wikelo_data.json',
  blueprints: 'https://api.star-head.de/blueprint',
  uex:        'https://api.uexcorp.space/2.0/commodities',
};
async function getJSON(url){ const r=await fetch(url,{cache:'no-store'}); if(!r.ok) throw new Error('HTTP '+r.status); return r.json(); }
function ingredientNamesFrom(w){
  const set=new Set(), recs=[...(w.ships||[]),...(w.items||[]),...(w.intro_mission?[w.intro_mission]:[])];
  for(const rec of recs) for(const it of parseRecipe(rec.recipe||'')) set.add(it.name);
  return set;
}
async function fetchBlueprints(names){
  const bp=await getJSON(EP.blueprints), out=[];
  for(const b of bp){ const nm=b&&b.name; if(!nm||!names.has(nm)) continue;
    const costs=[]; for(const c of (b.costs||[])){ const rn=c&&c.commodity&&c.commodity.name; if(rn) costs.push({name:rn, qty:c.quantity||0}); }
    if(costs.length) out.push({name:nm, costs}); }
  return out;
}
function needOreBases(names){ const s=new Set(); for(const n of names){ const o=oreCommodity(n); if(o) s.add(o); } return s; }
async function fetchPricesUex(bases){
  if(!bases.size) return {};
  const CAP=100000;   // Plausibilitaet: UEX hat fuer neue Erze teils Platzhalter (0 / Millionen)
  const res=await getJSON(EP.uex), data=(res&&res.data)||res||[], out={};
  for(const c of data){ const nm=String(c.name||'').trim(), base=nm.replace(/\s*\((Ore|Pure|Raw)\)$/,'').trim();
    if(!bases.has(base)) continue;
    const pb=c.price_buy||0, ps=c.price_sell||0, e=out[base]||{buy:null,sell:null,src:'uex'};
    if(pb>0&&pb<=CAP&&(!e.buy||pb<e.buy.price)) e.buy={price:Math.round(pb),loc:null};
    if(ps>0&&ps<=CAP&&(!e.sell||ps>e.sell.price)) e.sell={price:Math.round(ps),loc:null};
    if(e.buy||e.sell) out[base]=e; }
  return out;
}
async function refreshData(){
  const btn=$('#btnRefresh'); if(btn.dataset.busy) return;
  btn.dataset.busy='1'; btn.disabled=true; const label=btn.textContent; btn.textContent=t('loading');
  try{
    const w0=await getJSON(EP.wikelo);
    const w={ meta:w0.meta||{}, ships:w0.ships||[], items:w0.items||[], intro_mission:w0.intro_mission||{}, currency_exchanges:w0.currency_exchanges||[] };
    const names=ingredientNamesFrom(w), src=pref.priceSrc||'beide';
    let blueprints=[];
    if(src!=='uex'){ try{ blueprints=await fetchBlueprints(names); }catch(e){ toast(t('toastBpFail')); } }
    let prices={};
    if(src==='uex'||src==='beide'){ try{ prices=await fetchPricesUex(needOreBases(names)); }catch(e){ toast(t('toastPriceFail')); } }
    const newRaw={ schema:RAW_BAKED.schema, version:RAW_BAKED.version, generated:new Date().toISOString().slice(0,10),
      source:'refresh', wikelo:w, blueprints, prices, saved_inv:(RAW.saved_inv||{}), saved_acq:(RAW.saved_acq||{}) };
    RAW=newRaw; DATA=transform(RAW);
    try{ localStorage.setItem(LS_RAW, JSON.stringify(newRaw)); }catch(e){}
    updateMeta(); rerenderAll();
    toast(t('toastRefreshed',{n:DATA.meta.n_offers, p:DATA.meta.patch}));
  }catch(e){
    toast(t('toastRefreshFail'));
  }finally{ btn.dataset.busy=''; btn.disabled=false; btn.textContent=label; }
}
$('#btnRefresh').addEventListener('click', refreshData);
$('#btnRefresh').addEventListener('contextmenu', e=>{ e.preventDefault();
  if(confirm(t('confirmReset'))){
    try{ localStorage.removeItem(LS_RAW); }catch(e2){} RAW=RAW_BAKED; DATA=transform(RAW); updateMeta(); rerenderAll(); toast(t('toastReset')); }
});
$('#priceSrc').addEventListener('change', e=>{ pref.priceSrc=e.target.value; savePref(); });

function updateMeta(){
  const m=DATA.meta, fresh = m.source==='refresh' ? t('metaRefreshed',{d:m.generated}) : t('metaBuilt',{d:m.generated});
  $('#meta').textContent = t('metaLine',{v:m.version, patch:m.patch, data:m.data_updated, no:m.n_offers, ni:m.n_ingredients, fresh});
}

// ---- Sprache (DE/EN) ----
function applyStaticI18n(){
  document.querySelectorAll('[data-i18n]').forEach(el=> el.textContent=t(el.dataset.i18n));
  document.querySelectorAll('[data-i18n-ph]').forEach(el=> el.placeholder=t(el.dataset.i18nPh));
  document.querySelectorAll('[data-i18n-title]').forEach(el=> el.title=t(el.dataset.i18nTitle));
  document.documentElement.lang=LANG;
  $$('#langSeg button').forEach(b=>b.classList.toggle('on', b.dataset.lang===LANG));
}
$('#langSeg').addEventListener('click', e=>{
  const b=e.target.closest('button[data-lang]'); if(!b) return;
  LANG=b.dataset.lang; pref.lang=LANG; savePref();
  applyStaticI18n(); updateMeta(); rerenderAll();
});

// ---- init ----
LANG = pref.lang || 'de';
applyStaticI18n();
updateMeta();
$('#priceSrc').value = pref.priceSrc||'beide';
$('#myRep').value=pref.myRep||0; $('#onlyRep').checked=!!pref.onlyRep;
$('#showRetired').checked=!!pref.showRetired; $('#showAcquired').checked=!!pref.showAcquired; $('#onlyHave').checked=!!pref.onlyHave;
$$('#modeSeg button').forEach(x=>x.classList.toggle('on',x.dataset.mode===pref.mode));
if(!lsInv && Object.keys(inv).length) toast(t('toastPreload'));
rerenderAll();
</script>
</body>
</html>
"""


def main():
    raw = build_raw()
    payload = json.dumps(raw, ensure_ascii=False, separators=(",", ":"))
    payload = payload.replace("</", "<\\/")
    html = HTML_TEMPLATE.replace("/*__RAW__*/", payload)
    OUTHTML.write_text(html, encoding="utf-8")
    n_off = len(raw["wikelo"]["ships"]) + len(raw["wikelo"]["items"]) + 1
    n_pr = sum(1 for v in raw["prices"].values() if v.get("buy") or v.get("sell"))
    print("gespeichert:", OUTHTML)
    print(f"  {n_off} Angebote, {len(raw['blueprints'])} Baupläne, {n_pr} Erz-Preise.")
    print("FERTIG:", STAMP, "-> Datei per Doppelklick im Browser oeffnen.")


if __name__ == "__main__":
    main()
