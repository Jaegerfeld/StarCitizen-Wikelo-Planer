# -*- coding: utf-8 -*-
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
  * Bestand bleibt im Browser (localStorage) + Speichern/Laden als Datei
    (SC_Wikelo_Bestand.json). Diese Datei wird beim Neubau automatisch vorgeladen.

Start:  py "wikelo_planer_bauen.py"   (oder Wikelo_Planer_aktualisieren.bat)
"""
import http.client, json, os, re, ssl, time, datetime, pathlib, sys, urllib.request

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
    saved_inv = {}
    if BESTAND.exists():
        try:
            b = json.loads(BESTAND.read_text(encoding="utf-8"))
            for k, v in b.items():
                q = max(0, int(round(float(v))))
                if q > 0: saved_inv[k] = q
            print(f"  Bestand vorgeladen aus {BESTAND.name}: {len(saved_inv)} Ressourcen.")
        except Exception as e:
            print("  Hinweis: SC_Wikelo_Bestand.json nicht lesbar.", e)

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
  border-left:4px solid var(--line)}
.card.b0{border-left-color:var(--ok)}
.card.b1{border-left-color:var(--gold2)}
.card.b2{border-left-color:#e69138}
.card.b3{border-left-color:#c0392b}
.card.locked{opacity:.62}
.card h3{margin:0 0 3px;font-size:14px;line-height:1.2}
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
  </div>
  <div class="controls">
    <div class="seg" id="modeSeg">
      <button data-mode="aufwand" class="on">Nach Aufwand</button>
      <button data-mode="gruppe">Nach Artikelgruppe</button>
    </div>
    <label>Mein Wikelo-Ruf:
      <input type="number" id="myRep" min="0" step="5" value="0" style="width:72px">
    </label>
    <label><input type="checkbox" id="onlyRep"> nur erfüllbarer Ruf</label>
    <label><input type="checkbox" id="showRetired"> zurückgezogene zeigen</label>
    <input type="text" id="offerSearch" placeholder="Angebote filtern…" style="min-width:150px">
    <button class="btn prim" id="btnSave">💾 Bestand speichern</button>
    <button class="btn" id="btnLoad">📂 Bestand laden</button>
    <button class="btn" id="btnReset">leeren</button>
    <input type="file" id="fileInput" accept=".json,application/json" style="display:none">
    <span style="flex:1 1 auto"></span>
    <label title="Preisquelle für Erze">Preise:
      <select id="priceSrc">
        <option value="beide">beide (star-head + UEX)</option>
        <option value="uex">nur UEX</option>
        <option value="starhead">nur star-head</option>
      </select>
    </label>
    <button class="btn" id="btnRefresh" title="Angebote + Baupläne + Preise live neu laden">🔄 Daten aktualisieren</button>
  </div>
</header>

<main>
  <aside class="panel side">
    <div class="ph">
      <b>Mein Ressourcen-Bestand</b>
      <span class="meta" id="haveCount"></span>
    </div>
    <div class="qadd">
      <input type="text" id="quickAdd" autocomplete="off" placeholder='⚡ Schnell-Eingabe: z. B. „carinite 50" · Enter'>
      <div class="qsug" id="quickSug"></div>
    </div>
    <div class="qhint">„name zahl" setzt · „name +zahl" addiert · nur „name" = +1 · ↑↓ wählen, Enter übernehmen</div>
    <div style="padding:8px 8px 0"><input type="text" id="resSearch" placeholder="Ressource suchen…" style="width:100%"></div>
    <div style="padding:5px 12px 0;color:var(--dim);font-size:11px;line-height:1.4">
      Menge: Klick <b>+1</b> · Shift <b>+10</b> · Strg <b>+50</b> · Alt <b>+100</b>
      <span style="color:#7d95a8">(Mausrad = hoch/runter, Rechtsklick = minus, gleiche Modifier)</span>
    </div>
    <label style="padding:6px 12px;color:var(--dim);font-size:12px;display:flex;gap:6px;align-items:center">
      <input type="checkbox" id="onlyHave"> nur „hab ich" zeigen
    </label>
    <div class="scroll" id="resList"></div>
  </aside>

  <section>
    <div class="legend">
      <span><i class="sw" style="background:var(--ok)"></i> sofort</span>
      <span><i class="sw" style="background:var(--gold2)"></i> 1 fehlt</span>
      <span><i class="sw" style="background:#e69138"></i> 2 fehlen</span>
      <span><i class="sw" style="background:#c0392b"></i> 3+ fehlen</span>
      <span>· Aufwand <i class="edot on"></i><i class="edot on"></i><i class="edot"></i> = Gesamtaufwand des Fehlenden (Menge × Beschaffung)</span>
      <span style="margin-left:auto">Menge links: Klick +1 · Shift +10 · Strg +50 · Alt +100 (Mausrad/Rechtsklick ebenso)</span>
    </div>
    <div id="offers" style="margin-top:12px"></div>
  </section>
</main>

<div class="toast" id="toast"></div>

<script id="wikelo-raw" type="application/json">/*__RAW__*/</script>
<script>
const LS_INV = 'sc_wikelo_inv_v1', LS_PREF = 'sc_wikelo_pref_v1', LS_RAW = 'sc_wikelo_raw_v2';
const RAW_BAKED = JSON.parse(document.getElementById('wikelo-raw').textContent);

// ===== Aufbereitungslogik – EINZIGE Quelle der Wahrheit (Offline-Build wie In-App-Refresh) =====
const CAT_DE = {ship:'Schiff',vehicle:'Fahrzeug',weapon:'Waffe',armor:'Ruestung',gear:'Ausruestung',intro:'Freischaltung'};
const CAT_ORDER = {Schiff:0,Fahrzeug:1,Waffe:2,Ruestung:3,Ausruestung:4,Freischaltung:5};
const STATUS_DE = {active:'aktiv','retired-loot':'zurueckgezogen (Loot)','retired-store':'zurueckgezogen (Store)'};
const SRC_META = {
  'Wikelo/Waehrung':      {unit:4, hint:'Wikelo-Favor/Scrip – per Tausch (siehe unten)'},
  'Mining/Erz':           {unit:1, hint:'Mining / teils kaufbar (Preis siehe unten)'},
  'Creature/Loot':        {unit:2, hint:'Creature-Jagd (Valakkar / Kopion / Yormandi)'},
  'Salvage/Vanduul':      {unit:2, hint:'Salvage / Vanduul-Gebiete'},
  'CZ/Tech-Loot':         {unit:3, hint:'Contested Zones / Tech-Loot (PvP-Risiko)'},
  'Missions-/Beute-Item': {unit:3, hint:'Missionsbelohnung / seltener Loot'},
  'Craftbar (Bauplan)':   {unit:2, hint:'Craften – Rezept siehe unten'},
  'Item/Sonstiges':       {unit:1, hint:'Kauf / Loot'},
};
const SRC_ORDER = ['Wikelo/Waehrung','Mining/Erz','Creature/Loot','Salvage/Vanduul','CZ/Tech-Loot','Missions-/Beute-Item','Craftbar (Bauplan)','Item/Sonstiges'];
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
  if(['Wikelo Favor','Polaris Bit','MG Scrip','Council Scrip'].includes(name)) return 'Wikelo/Waehrung';
  if(['(ore)','(pure)','saldynium','jaclium','carinite','sadaryx','quantanium fuel'].some(w=>n.includes(w))) return 'Mining/Erz';
  if(['valakkar','kopion','yormandi','grazer','fungus'].some(w=>n.includes(w))) return 'Creature/Loot';
  if(['medal','marker','badge','artifact fragment','metamaterial','test #'].some(w=>n.includes(w))) return 'Missions-/Beute-Item';
  if(n.includes('vanduul')) return 'Salvage/Vanduul';
  if(['rcmbnt','comp-board','secure drive','drive'].some(w=>n.includes(w))) return 'CZ/Tech-Loot';
  if(craftable) return 'Craftbar (Bauplan)';
  return 'Item/Sonstiges';
}
function transform(raw){
  const w = raw.wikelo||{};
  const allrecs = [...(w.ships||[]), ...(w.items||[]), ...(w.intro_mission?[w.intro_mission]:[])];
  const bpMap={};
  for(const b of (raw.blueprints||[])) if(b && b.name && b.costs && b.costs.length) bpMap[b.name]=b.costs;
  const catRank=a=> (CAT_ORDER[a]!=null?CAT_ORDER[a]:9);
  const offers = allrecs.map(rec=>({
    id: rec.id||'', reward: nameOf(rec), art: CAT_DE[rec.category]||rec.category||'',
    mission: String(rec.mission_name||'').trim(), recipe: parseRecipe(rec.recipe||''),
    rep_req: rec.reputation_required||0, rep_rew: rec.reputation_reward||0,
    status: rec.status||'active', status_de: STATUS_DE[rec.status]||rec.status||'',
  })).sort((a,b)=> (catRank(a.art)-catRank(b.art)) || cmp(a.reward.toLowerCase(), b.reward.toLowerCase()));
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
    src_order:SRC_ORDER, src_meta:SRC_META, cat_order:CAT_ORDER, saved_inv:raw.saved_inv||{},
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
let pref = {mode:'aufwand', myRep:0, onlyRep:false, showRetired:false, onlyHave:false, priceSrc:'beide'};
let lsInv = null;
try{ lsInv = JSON.parse(localStorage.getItem(LS_INV)||'null'); }catch(e){}
if(lsInv && Object.keys(lsInv).length){ inv = lsInv; }
else { inv = Object.assign({}, DATA.saved_inv||{}); }   // Vorbelegung aus SC_Wikelo_Bestand.json
try{ Object.assign(pref, JSON.parse(localStorage.getItem(LS_PREF)||'{}')||{}); }catch(e){}

function saveInv(){ try{localStorage.setItem(LS_INV, JSON.stringify(inv));}catch(e){} }
function savePref(){ try{localStorage.setItem(LS_PREF, JSON.stringify(pref));}catch(e){} }
function have(n){ return inv[n]||0; }
function setHave(n,q){ q=Math.max(0,Math.round(q||0)); if(q<=0) delete inv[n]; else inv[n]=q; saveInv(); rerenderAll(); }

// ---- helpers ----
const $=s=>document.querySelector(s), $$=s=>[...document.querySelectorAll(s)];
function toast(m){ const t=$('#toast'); t.textContent=m; t.classList.add('show'); clearTimeout(t._t); t._t=setTimeout(()=>t.classList.remove('show'),1800); }
function esc(s){ return (s||'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c])); }
function fmt(n){ return Math.round(n).toLocaleString('de-DE'); }
function unitOf(name){ const info=DATA.ingredients[name]||{}; return (DATA.src_meta[info.src]||{}).unit||2; }
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

const BANDS=[
  {k:0,label:'Sofort verfügbar',dot:'var(--ok)'},
  {k:1,label:'1 Zutat fehlt',dot:'var(--gold2)'},
  {k:2,label:'2 Zutaten fehlen',dot:'#e69138'},
  {k:3,label:'3+ Zutaten fehlen',dot:'#c0392b'},
];

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
    html+=`<div class="grp">${esc(src)}</div>`;
    for(const [nm,info] of arr){
      const v=have(nm);
      html+=`<div class="res ${v?'have':''}" data-n="${esc(nm)}">
        <div class="qbox">
          <button class="qbtn" data-a="dec">−</button>
          <span class="qval ${v?'':'z'}">${v}</span>
          <button class="qbtn" data-a="inc">+</button>
        </div>
        <div class="nm">${esc(nm)}<small>in ${info.n_offers} Angebot${info.n_offers>1?'en':''}${info.blueprint?' · craftbar':''}${info.ore?' · Erz':''}</small></div>
      </div>`;
    }
  }
  $('#resList').innerHTML = html || '<div class="empty">Keine Ressource gefunden.</div>';
  const hc=Object.keys(inv).length;
  $('#haveCount').textContent = hc? `${hc} markiert` : '';
}

// ---- procurement hint for a missing ingredient ----
function hintFor(name){
  const info=DATA.ingredients[name]||{};
  const meta=DATA.src_meta[info.src]||{};
  let extra='';
  // Bauplan
  if(info.blueprint){
    extra = '🔨 '+info.blueprint.map(c=>`${c.qty}× ${esc(c.name)}`).join(', ');
  }
  // Waehrungs-Tausch (z. B. Wikelo Favor)
  else if(DATA.currency_map[name]){
    const opts=DATA.currency_map[name].map(o=> o.recipe_raw
        ? `<span class="opt">${esc(o.recipe_raw)}</span>`
        : `<span class="opt">${esc(o.mission||'Sonderauftrag')}</span>`).join('');
    extra = 'Tausch: '+opts;
  }
  // Erz-Preis / Kaufort
  else if(info.ore && DATA.prices[info.ore]){
    const p=DATA.prices[info.ore], q=p.src==='uex'?'Ø UEX':'Ø Markt';
    if(p.buy) extra = `kaufbar ≈ ${fmt(p.buy.price)} aUEC/SCU` + (p.buy.loc?` bei ${esc(p.buy.loc)}`:` (${q})`);
    else if(p.sell) extra = `Verkaufswert ≈ ${fmt(p.sell.price)} aUEC/SCU` + (p.sell.loc?` (${esc(p.sell.loc)})`:` (${q})`);
  }
  return {src:info.src, hint:meta.hint||'', extra};
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
        return `<div class="row"><span class="src">${esc(h.src)}</span>
          <b>${m.gap}× ${esc(m.name)}</b>${m.has?` <span class="sub">(hast ${m.has}/${m.need})</span>`:''}
          <div class="sub">${h.extra||esc(h.hint)}</div></div>`;
      }).join('') + `</div>`;
  }
  // Aufwand-Sterne (1..5) – mengengewichtet
  const eff = a.stars;
  const dots = a.missTypes? `<span class="effort" title="Gesamt-Beschaffungsaufwand des Fehlenden (Menge × Quelle)">Aufwand `+
    [1,2,3,4,5].map(i=>`<i class="edot ${i<=eff?'on':''}"></i>`).join('')+`</span>` : '';
  const repBadge = o.rep_req? `<span class="badge ${locked?'lock':'rep'}">Ruf ${o.rep_req}${locked?' ⚠':''}</span>`:'';
  const rewBadge = o.rep_rew? `<span class="badge rep">+${o.rep_rew} Ruf</span>`:'';
  const retBadge = retired? `<span class="badge ret">${esc(o.status_de)}</span>`:'';
  return `<div class="card b${a.band} ${locked?'locked':''}" data-id="${o.id}">
    <h3>${esc(o.reward||o.mission)}</h3>
    <span class="cat">${esc(o.art)}</span>
    ${o.mission&&o.mission!==o.reward?`<div class="mission">„${esc(o.mission)}"</div>`:''}
    <div class="chips">${chips}</div>
    ${detHtml}
    <div class="foot">
      <span>${a.missing.length?`<span class="tog">Fehlendes beschaffen ▾</span>`:'<span style="color:var(--ok)">✓ komplett</span>'}</span>
      <span style="display:flex;gap:8px;align-items:center">${dots} ${retBadge} ${rewBadge} ${repBadge}</span>
    </div>
  </div>`;
}

function passFilter(o,a){
  if(o.status!=='active' && !pref.showRetired) return false;
  if(pref.onlyRep && !a.repOk) return false;
  const q=($('#offerSearch').value||'').toLowerCase();
  if(q){
    const hay=(o.reward+' '+o.mission+' '+o.art+' '+o.recipe.map(r=>r.name).join(' ')).toLowerCase();
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
      html+=`<div class="band"><div class="bh"><span class="dot" style="background:${b.dot}"></span>
        <b>${b.label}</b><span class="cnt">${items.length} Angebot${items.length>1?'e':''}</span></div>
        <div class="cards">${items.map(x=>offerCard(x.o)).join('')}</div></div>`;
    }
  } else {
    const cats=Object.keys(DATA.cat_order).sort((a,b)=>DATA.cat_order[a]-DATA.cat_order[b]);
    for(const cat of cats){
      const items=rows.filter(x=>x.o.art===cat).sort(sortCmp);
      if(!items.length) continue;
      html+=`<div class="band"><div class="bh"><span class="dot" style="background:var(--navy2)"></span>
        <b>${esc(cat)}</b><span class="cnt">${items.length}</span></div>
        <div class="cards">${items.map(x=>offerCard(x.o)).join('')}</div></div>`;
    }
  }
  $('#offers').innerHTML = html || '<div class="empty">Keine Angebote für diese Filter.</div>';
}

function rerenderAll(){ renderRes(); renderOffers(); }

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
      <span><span class="src2">${esc(info.src||'')}</span> ${esc(m.name)} <small>(${cur})</small></span>
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
  const tog=e.target.closest('.tog');
  if(tog){ const d=tog.closest('.card').querySelector('.det'); if(d){ d.classList.toggle('open');
    tog.textContent = d.classList.contains('open')?'Fehlendes beschaffen ▴':'Fehlendes beschaffen ▾'; } return; }
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
$('#modeSeg').addEventListener('click', e=>{
  const b=e.target.closest('button[data-mode]'); if(!b) return;
  pref.mode=b.dataset.mode; savePref();
  $$('#modeSeg button').forEach(x=>x.classList.toggle('on',x===b)); renderOffers();
});

// ---- Bestand speichern / laden (Datei) ----
$('#btnSave').addEventListener('click', ()=>{
  const blob=new Blob([JSON.stringify(inv,null,1)],{type:'application/json'});
  const url=URL.createObjectURL(blob);
  const a=document.createElement('a'); a.href=url; a.download='SC_Wikelo_Bestand.json';
  document.body.appendChild(a); a.click(); a.remove();
  setTimeout(()=>URL.revokeObjectURL(url),1000);
  toast('Bestand als SC_Wikelo_Bestand.json gespeichert');
});
$('#btnLoad').addEventListener('click', ()=> $('#fileInput').click());
$('#fileInput').addEventListener('change', e=>{
  const f=e.target.files[0]; if(!f) return;
  const rd=new FileReader();
  rd.onload=()=>{ try{
    const o=JSON.parse(rd.result); if(typeof o!=='object'||Array.isArray(o)) throw 0;
    inv={}; for(const [k,v] of Object.entries(o)){ const q=Math.max(0,Math.round(+v||0)); if(q>0) inv[k]=q; }
    saveInv(); rerenderAll(); toast('Bestand geladen: '+Object.keys(inv).length+' Ressourcen');
  }catch(err){ toast('Ungültige Datei (kein Bestand-JSON)'); } };
  rd.readAsText(f); e.target.value='';
});
$('#btnReset').addEventListener('click', ()=>{ if(confirm('Wirklich den ganzen Bestand leeren?')){ inv={}; saveInv(); rerenderAll(); } });

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
  btn.dataset.busy='1'; btn.disabled=true; const label=btn.textContent; btn.textContent='⏳ lädt…';
  try{
    const w0=await getJSON(EP.wikelo);
    const w={ meta:w0.meta||{}, ships:w0.ships||[], items:w0.items||[], intro_mission:w0.intro_mission||{}, currency_exchanges:w0.currency_exchanges||[] };
    const names=ingredientNamesFrom(w), src=pref.priceSrc||'beide';
    let blueprints=[];
    if(src!=='uex'){ try{ blueprints=await fetchBlueprints(names); }catch(e){ toast('Baupläne (star-head) nicht erreichbar'); } }
    let prices={};
    if(src==='uex'||src==='beide'){ try{ prices=await fetchPricesUex(needOreBases(names)); }catch(e){ toast('Preise (UEX) nicht erreichbar'); } }
    const newRaw={ schema:RAW_BAKED.schema, version:RAW_BAKED.version, generated:new Date().toISOString().slice(0,10),
      source:'refresh', wikelo:w, blueprints, prices, saved_inv:(RAW.saved_inv||{}) };
    RAW=newRaw; DATA=transform(RAW);
    try{ localStorage.setItem(LS_RAW, JSON.stringify(newRaw)); }catch(e){}
    updateMeta(); rerenderAll();
    toast('Daten aktualisiert · '+DATA.meta.n_offers+' Angebote, Patch '+DATA.meta.patch);
  }catch(e){
    toast('Aktualisierung fehlgeschlagen (Quelle offline?) – bestehende Daten bleiben');
  }finally{ btn.dataset.busy=''; btn.disabled=false; btn.textContent=label; }
}
$('#btnRefresh').addEventListener('click', refreshData);
$('#btnRefresh').addEventListener('contextmenu', e=>{ e.preventDefault();
  if(confirm('Auf die eingebauten Build-Daten zurücksetzen (gecachte Aktualisierung verwerfen)?')){
    try{ localStorage.removeItem(LS_RAW); }catch(e2){} RAW=RAW_BAKED; DATA=transform(RAW); updateMeta(); rerenderAll(); toast('Auf Build-Daten zurückgesetzt'); }
});
$('#priceSrc').addEventListener('change', e=>{ pref.priceSrc=e.target.value; savePref(); });

function updateMeta(){
  const m=DATA.meta, fresh = m.source==='refresh' ? ('aktualisiert '+m.generated) : ('gebaut '+m.generated);
  $('#meta').textContent = `v${m.version} · Patch ${m.patch} · Daten ${m.data_updated} · ${m.n_offers} Angebote · ${m.n_ingredients} Ressourcen · ${fresh}`;
}

// ---- init ----
updateMeta();
$('#priceSrc').value = pref.priceSrc||'beide';
$('#myRep').value=pref.myRep||0; $('#onlyRep').checked=!!pref.onlyRep;
$('#showRetired').checked=!!pref.showRetired; $('#onlyHave').checked=!!pref.onlyHave;
$$('#modeSeg button').forEach(x=>x.classList.toggle('on',x.dataset.mode===pref.mode));
if(!lsInv && Object.keys(inv).length) toast('Bestand aus SC_Wikelo_Bestand.json vorgeladen');
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
