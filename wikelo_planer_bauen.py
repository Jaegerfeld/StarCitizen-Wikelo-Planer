# =============================================================================
# Autor:          Robert Seebauer
# Repository:     https://github.com/Jaegerfeld/StarCitizen-Wikelo-Planer
# KI-Unterstützung: Erstellt mit Unterstützung von Claude (Anthropic)
# Erstellt:       22.08.2026
# Geändert:       01.11.2026
# Lizenz:         BSD-3-Clause (siehe LICENSE)
#
# Fachliche Funktion:
#   Baut den Wikelo-Ressourcen-Planer für Star-Citizen-Spieler: eine einzige,
#   offline lauffähige HTML-Datei (SC_Wikelo_Planer.html), die zeigt, welche
#   Wikelo-Angebote (Schiffe, Fahrzeuge, Waffen, Rüstung, Ausrüstung,
#   Freischalt-Mission) sich mit dem eigenen Ressourcen-Bestand erfüllen lassen
#   und was dafür noch fehlt.
#   Datenquellen (Community, nur gelesen):
#     - Wikelo-Angebote, Rezepte, Ruf und Währungs-Tausch:
#       seeknd.github.io/Wikelo/data/wikelo_data.json
#     - Bauplan-Rezepte craftbarer Zutaten: api.star-head.de/blueprint
#       (nur Baupläne, deren Name eine Wikelo-Zutat ist – hält die Datei klein)
#     - Erz-Preise (aUEC/SCU) für Carinite, Jaclium, Saldynium, Sadaryx:
#       api.star-head.de (commodity, shop, shopitem/price) mit Shop und Ort,
#       dieselbe Quelle wie im Handels-Planer. Die Erze sind nicht kaufbar,
#       es gibt nur Verkaufswerte; sie liegen im Millionenbereich und sind echt
#       (am 28.10.2026 per Screenshot bestätigt). Bis 1.6.1 kamen die Preise von
#       UEX und wurden ab 100 000 als Platzhalter verworfen, daher „0 Erz-Preise“.
#   Python bündelt nur die Rohdaten; die Aufbereitung (Zutaten-Kategorien,
#   Beschaffungs-Aufwand, Bänder „sofort / 1 / 2 / 3+ fehlen“, Sortierung,
#   Beschaffungs-Hinweise) läuft einmalig im Browser (transform() im HTML),
#   damit Offline-Build und In-App-Aktualisierung dieselbe Logik nutzen.
#   Die Rohdaten werden in die HTML eingebacken und zusätzlich als data.json
#   (ohne persönlichen Bestand) geschrieben; der Knopf „Neuesten Stand laden“
#   holt diese Datei von GitHub Pages statt die Community-Quellen direkt
#   abzufragen.
#   Persönlicher Bestand: Liegt neben dem Skript eine SC_Wikelo_Bestand.json
#   (Format {schema, inventory, acquired}; altes flaches {name: menge} wird
#   weiter gelesen), wird sie beim Bau vorgeladen. In der App bleiben Bestand
#   und „erworben“-Markierungen im localStorage und lassen sich als Datei
#   speichern/laden.
#   Bei nicht erreichbarer Wikelo-Quelle bricht der Bau ab und lässt die
#   bestehende HTML unverändert; fehlende Baupläne oder Preise sind kein
#   Abbruchgrund.
#   Start: py wikelo_planer_bauen.py (oder Wikelo_Planer_aktualisieren.bat).
# =============================================================================
"""Build script for the SC Wikelo resource planner (single offline HTML file)."""
import datetime
import http.client
import json
import pathlib
import re
import ssl
import sys
import time
import urllib.request

import kopfzeile as kz
import sc_design as sd

#: Host of the seeknd Wikelo data site (offers, recipes, currency exchanges).
HOST     = "seeknd.github.io"
#: Path prefix of the Wikelo site on HOST.
BASEPATH = "/Wikelo/"
#: Output folder = script folder, so the build runs on any PC and in CI.
OUTDIR   = pathlib.Path(__file__).resolve().parent
#: The generated single-file planner.
OUTHTML  = OUTDIR / "SC_Wikelo_Planer.html"
#: Same data snapshot as a file (without personal inventory) for the in-app refresh via Pages.
OUTJSON  = OUTDIR / "data.json"
#: Published location of data.json on GitHub Pages.
DATA_URL = "https://jaegerfeld.github.io/StarCitizen-Wikelo-Planer/data.json"
#: Optional personal inventory file; preloaded into the build when present.
BESTAND  = OUTDIR / "SC_Wikelo_Bestand.json"
#: Base URL of the star-head.de JSON API (blueprints and ore prices).
STARHEAD = "https://api.star-head.de"
#: star-head returns pricePerItem per cSCU; multiplying by this gives aUEC/SCU (as in the Handels-Planer).
PRICE_FACTOR = 100
#: Build date (ISO), shown in the app and stored as ``generated``.
STAMP    = datetime.date.today().isoformat()
try:
    from version import VERSION
except Exception:
    VERSION = "0.0.0"

#: One recipe part such as ``"12 x Carinite (Pure)"`` -> (quantity, name).
PAT = re.compile(r'^\s*(\d+)\s*x\s+(.*\S)\s*$')

# The preparation logic (categories, source classification, offers, currency exchange,
# effort weights) lives ONCE in the browser (transform() in the HTML), so the in-app
# refresh uses the same logic as the offline build. Python only bundles the raw data.

def ore_commodity(name):
    """Map an ore ingredient to its commodity base name for the price lookup.

    Only the four Wikelo ores are recognised; the suffixes ``(Ore)`` and
    ``(Pure)`` are stripped first.

    Args:
        name: Ingredient name as it appears in a Wikelo recipe.

    Returns:
        The base name (``"Carinite"``, ``"Jaclium"``, ``"Saldynium"`` or
        ``"Sadaryx"``), or ``None`` if the ingredient is not one of these ores.
    """
    base = re.sub(r'\s*\((Ore|Pure)\)$', '', str(name).strip()).strip()
    if base in ("Carinite", "Jaclium", "Saldynium", "Sadaryx"):
        return base
    return None


# ----------------------------------------------------------------- Network
class SiteClient:
    """A reused HTTPS connection (keep-alive) to one host with automatic reconnect."""
    def __init__(self, host):
        """Open the connection.

        Args:
            host: Host name, e.g. ``"seeknd.github.io"``.
        """
        self.host = host; self.ctx = ssl.create_default_context(); self._connect()
    def _connect(self):
        """(Re)create the underlying HTTPS connection with a 30 s timeout."""
        self.conn = http.client.HTTPSConnection(self.host, timeout=30, context=self.ctx)
    def get(self, path, retries=4):
        """Send a GET request, reconnecting after network errors.

        Args:
            path: Request path on the host, including the leading slash.
            retries: Number of attempts before giving up.

        Returns:
            Tuple ``(status, body)``; ``(None, b"")`` if every attempt failed.
        """
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
        """Close the connection, ignoring errors."""
        try: self.conn.close()
        except Exception: pass


def netzfehler_exit(quelle, grund):
    """Print a friendly "source unreachable" notice and exit with status 1.

    The existing HTML file is left untouched, so the last good build stays usable.

    Args:
        quelle: Name of the data source shown to the user.
        grund: Exception or reason text.

    Raises:
        SystemExit: Always, with exit code 1.
    """
    print(); print("=" * 64)
    print(f" Datenquelle ({quelle}) ist gerade NICHT erreichbar.")
    print(" Grund:", grund)
    print(" Das liegt fast immer an der Quelle/am Netz, nicht an dir.")
    print(" Bitte spaeter nochmal ausfuehren. Die bestehende HTML-Datei")
    print(" bleibt unveraendert erhalten.")
    print("=" * 64); sys.exit(1)


def get_json_url(url, timeout=90):
    """Fetch a URL and decode its body as JSON.

    Args:
        url: Full URL to fetch.
        timeout: Timeout in seconds.

    Returns:
        The decoded JSON value.

    Raises:
        urllib.error.URLError: On network or HTTP errors.
        json.JSONDecodeError: If the body is not valid JSON.
    """
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 sc-wikelo-planer"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


# ----------------------------------------------------------------- Helpers
def parse_recipe(recipe):
    """Split a Wikelo recipe string into ingredients with quantities.

    Parts are separated by ``;``; a part without ``"<n> x "`` prefix counts as quantity 1.

    Args:
        recipe: Recipe string, e.g. ``"50 x Carinite; 1 x Wikelo Favor"``.

    Returns:
        List of ``{"name": str, "qty": int}`` dicts in recipe order.
    """
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


# ----------------------------------------------------------------- Ore prices (star-head)
def _shop_places():
    """Map star-head shop ids to a readable place name, ``"Shop (Station)"``.

    Returns:
        Dict ``{shop_id: place}``; empty if the shop list is unreachable (the
        price rows then show the bare shop name).
    """
    try:
        shops = get_json_url(STARHEAD + "/shop")
    except Exception as e:
        print("  Hinweis: Shop-Liste (star-head) nicht erreichbar.", e)
        return {}
    out = {}
    for sh in shops or []:
        name = sh.get("name") or ""
        parent = (sh.get("parent") or {}).get("name") or ""
        # star-head spells some stations without spaces ("ArcCorpMining Area 045"), so compare loosely.
        same = re.sub(r"\s+", "", parent).lower() == re.sub(r"\s+", "", name).lower()
        out[sh.get("id")] = f"{name} ({parent})" if parent and not same else name
    return out


def fetch_prices_starhead(need_bases):
    """Fetch ore prices (aUEC/SCU) per commodity base name from star-head.de.

    Every star-head commodity whose name reduces to a needed base (for example
    ``"Jaclium"`` and ``"Jaclium (Ore)"``) is queried for buy and sell prices
    via ``/shopitem/price``. The cheapest buy and the best sell win, each with
    its place. star-head's ``pricePerItem`` is per cSCU and is converted with
    :data:`PRICE_FACTOR`. Prices of 0 are ignored; there is no upper limit,
    because these ores really sell for millions per SCU. If star-head is
    unreachable, a notice is printed and the build continues without prices.

    Args:
        need_bases: Set of commodity base names that Wikelo recipes need.

    Returns:
        Dict ``{base: {"buy": {"price", "loc", "date"} | None, "sell": ... | None,
        "n_sell": int, "src": "starhead"}}``; only bases with at least one valid
        price appear.
    """
    out = {}
    if not need_bases:
        return out
    try:
        commodities = get_json_url(STARHEAD + "/commodity")
    except Exception as e:
        print("  Hinweis: Erz-Preise (star-head) nicht erreichbar -> ohne Erz-Preise.", e)
        return out
    places = _shop_places()
    for c in commodities or []:
        base = re.sub(r'\s*\((Ore|Pure|Raw)\)$', '', (c.get("name") or "").strip()).strip()
        if base not in need_bases:
            continue
        entry = out.get(base, {"buy": None, "sell": None, "n_sell": 0, "src": "starhead"})
        for tt in ("Buy", "Sell"):
            try:
                rows = get_json_url(f"{STARHEAD}/shopitem/price?commodityId={c['id']}&tradeType={tt}")
            except Exception as e:
                print(f"  Hinweis: Preise für {c.get('name')} ({tt}) nicht erreichbar.", e)
                continue
            for x in rows or []:
                price = round((x.get("pricePerItem") or 0) * PRICE_FACTOR)
                if price <= 0:
                    continue
                shop = x.get("shop") or {}
                hit = {"price": price, "loc": places.get(shop.get("id")) or shop.get("name") or None,
                       "date": (x.get("lastUpdated") or "")[:10]}
                # On equal prices the more recent report wins, so the shown date is the freshest.
                if tt == "Buy":
                    cur = entry["buy"]
                    if cur is None or (price, cur["date"]) < (cur["price"], hit["date"]):
                        entry["buy"] = hit
                if tt == "Sell":
                    entry["n_sell"] += 1
                    cur = entry["sell"]
                    if cur is None or (price, hit["date"]) > (cur["price"], cur["date"]):
                        entry["sell"] = hit
        if entry["buy"] or entry["sell"]:
            out[base] = entry
    return out


# ----------------------------------------------------------------- Bundle raw data
def recipe_names(recipe):
    """Return only the ingredient names of a recipe string (for the blueprint filter).

    Args:
        recipe: Recipe string as in :func:`parse_recipe`.

    Returns:
        List of ingredient names in recipe order.
    """
    out = []
    for part in str(recipe).split(";"):
        part = part.strip()
        if not part: continue
        m = PAT.match(part)
        out.append(m.group(2) if m else part)
    return out


def load_saved(path):
    """Read the personal inventory file to preload it into the build.

    Format v2 is ``{"inventory": {...}, "acquired": {...}}``; the old flat
    ``{name: amount}`` is still read as plain inventory (backward compatibility).
    Amounts are rounded and only positive ones are kept. An unreadable file
    prints a notice and yields empty results.

    Args:
        path: Path to ``SC_Wikelo_Bestand.json``; it may be missing.

    Returns:
        Tuple ``(saved_inv, saved_acq)``: ``{name: amount}`` and
        ``{mission_name: {"reward": str, "ts": str}}``.
    """
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
    """Download all sources and bundle them into the raw data object (schema 2).

    Wikelo data is mandatory (exits via :func:`netzfehler_exit` if unreachable);
    star-head blueprints and ore prices are optional and only print a notice
    on failure.

    Returns:
        Dict with ``schema``, ``version``, ``generated``, ``source``,
        ``wikelo`` (meta, ships, items, intro_mission, currency_exchanges),
        ``blueprints``, ``prices``, ``saved_inv`` and ``saved_acq``.
    """
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

    # Ingredient names (for the blueprint filter and the ore demand)
    ingredient_names = set()
    for rec in allrecs:
        for nm in recipe_names(rec.get("recipe", "")):
            ingredient_names.add(nm)

    # Blueprints: only those whose name is a Wikelo ingredient (keeps the file small)
    print("Lade Bauplan-Rezepte (star-head.de) ...")
    blueprints = []
    try:
        bp = get_json_url(STARHEAD + "/blueprint")
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

    # Ore prices (star-head)
    print("Lade Erz-Preise (star-head.de) ...")
    need_ore = {oc for nm in ingredient_names if (oc := ore_commodity(nm))}
    prices = fetch_prices_starhead(need_ore)
    print(f"  Preise fuer {sum(1 for v in prices.values() if v.get('buy') or v.get('sell'))} Erz(e).")

    # Saved inventory (if present) as preset
    saved_inv, saved_acq = load_saved(BESTAND)

    return {
        "schema": 2,
        "version": VERSION,
        "generated": STAMP,
        "source": "build",       # overwritten with "refresh" by the in-app refresh
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
        "saved_acq": saved_acq,   # {mission_name: {reward, ts}} – offers marked as acquired
    }


# ----------------------------------------------------------------- HTML
HTML_TEMPLATE = r"""<!doctype html>
<!-- SC Wikelo resource planner (which Wikelo offers the inventory can fulfil, what is missing); generated by wikelo_planer_bauen.py, do not edit by hand -->
<html lang="de" data-theme="dark">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>SC Wikelo Ressourcen-Planer</title>
<style>
:root{
  /* Wikelo roles, derived from the family tokens in sc_design.py (light + dark) */
  --w-navy:var(--panel); --w-navy2:var(--panel); --w-ink:var(--bg); --w-panel:var(--panel); --w-panel2:var(--panel2);
  --w-line:var(--line); --w-txt:var(--ink); --w-dim:var(--muted); --w-gold:var(--accent2); --w-gold2:var(--accent2);
  --w-ok:var(--ok); --w-okbg:var(--okbg); --w-miss:var(--bad); --w-missbg:var(--badbg); --w-chip:var(--panel2);
  --w-band2:#d07a1f; --w-band3:#b3452f; --w-retbg:#efe9f7; --w-retbd:#c9b6e6; --w-rettx:#5b3f86;
}
:root[data-theme="dark"]{
  --w-band2:#e69138; --w-band3:#c0392b; --w-retbg:#2a2333; --w-retbd:#4a3d5c; --w-rettx:#c9b6e6;
}
*{box-sizing:border-box}
html,body{margin:0;background:var(--w-ink);color:var(--w-txt);font-size:14px}
a{color:var(--w-gold)}
.wtools{background:var(--w-panel);padding:10px 16px;
  border-bottom:2px solid var(--w-gold2);border-top:1px solid var(--w-line);position:sticky;top:0;z-index:20}
.wtools .controls{margin-top:0}
.hazard{height:5px;background:repeating-linear-gradient(45deg,var(--w-gold2) 0 14px,transparent 14px 28px);opacity:.9}
.fhwrap{padding:0 16px}
.hrow{display:flex;flex-wrap:wrap;gap:10px 18px;align-items:center}
h1{font-size:18px;margin:0;letter-spacing:.3px}
h1 .sub{color:var(--w-gold);font-weight:600}
.meta{color:var(--w-dim);font-size:12px}
.controls{display:flex;flex-wrap:wrap;gap:8px 14px;align-items:center;margin-top:8px}
.controls label{font-size:12.5px;color:var(--w-dim);display:flex;gap:6px;align-items:center}
input[type=text],input[type=number]{background:var(--w-panel2);border:1px solid var(--w-line);
  color:var(--w-txt);border-radius:6px;padding:6px 8px;font-size:13px}
input[type=number]{width:64px}
select{background:var(--w-panel2);border:1px solid var(--w-line);color:var(--w-txt);border-radius:6px;padding:5px 6px;font-size:12.5px}
.btn[disabled]{opacity:.5;cursor:progress}
.btn{background:var(--w-chip);border:1px solid var(--w-line);color:var(--w-txt);border-radius:6px;
  padding:6px 10px;font-size:12.5px;cursor:pointer}
.btn:hover{border-color:var(--w-gold2)}
.btn.prim{background:var(--accent);color:var(--onaccent);font-weight:700;border-color:var(--accent)}
.seg{display:inline-flex;border:1px solid var(--w-line);border-radius:6px;overflow:hidden}
.seg button{background:var(--w-panel2);border:0;color:var(--w-dim);padding:6px 10px;cursor:pointer;font-size:12.5px}
.seg button.on{background:var(--accent);color:var(--onaccent);font-weight:700}
main{display:grid;grid-template-columns:340px 1fr;gap:14px;padding:14px;align-items:start}
.panel{background:var(--w-panel);border:1px solid var(--w-line);border-radius:10px}
.panel > .ph{padding:9px 12px;border-bottom:1px solid var(--w-line);display:flex;
  justify-content:space-between;align-items:center;gap:8px}
.ph b{font-size:13px}
.side{position:sticky;top:96px;max-height:calc(100vh - 112px);display:flex;flex-direction:column}
.side .scroll{overflow:auto;padding:6px 6px 10px}
.grp{margin:6px 4px 2px;color:var(--w-gold);font-size:11.5px;text-transform:uppercase;
  letter-spacing:.5px;padding:6px 8px 2px;border-top:1px solid var(--w-line)}
.grp:first-child{border-top:0}
.res{display:flex;align-items:center;gap:8px;padding:5px 8px;border-radius:7px;cursor:pointer;
  user-select:none}
.res:hover{background:var(--hover)}
.res.have{background:var(--w-okbg)}
.res .nm{flex:1;line-height:1.15}
.res .nm small{color:var(--w-dim);display:block;font-size:10.5px}
.res.have .nm{color:var(--ok)}
.qbox{display:flex;align-items:center;gap:3px}
.qbtn{width:22px;height:22px;border-radius:5px;border:1px solid var(--w-line);background:var(--w-panel2);
  color:var(--w-txt);cursor:pointer;font-size:14px;line-height:1;display:flex;align-items:center;justify-content:center}
.qbtn:hover{border-color:var(--w-gold2)}
.qval{min-width:26px;text-align:center;font-variant-numeric:tabular-nums;font-weight:700}
.qval.z{color:var(--w-dim);font-weight:400}
.qadd{position:relative;padding:8px 8px 2px}
#quickAdd{width:100%;border-color:var(--w-gold2)}
.qhint{padding:0 12px;color:var(--w-dim);font-size:10.5px}
.qsug{position:absolute;left:8px;right:8px;top:calc(100% - 2px);z-index:18;background:var(--w-panel2);
  border:1px solid var(--w-gold2);border-top:0;border-radius:0 0 8px 8px;max-height:280px;overflow:auto;display:none;
  box-shadow:0 10px 24px rgba(0,0,0,.4)}
.qsug.open{display:block}
.qsug .s{display:flex;justify-content:space-between;gap:8px;padding:6px 10px;cursor:pointer;font-size:12.5px}
.qsug .s:hover,.qsug .s.act{background:var(--hover)}
.qsug .s .src2{color:var(--w-gold);font-size:9.5px;text-transform:uppercase}
.qsug .s .sq{color:var(--w-ok);font-variant-numeric:tabular-nums;font-weight:700}
.qsug .s small{color:var(--w-dim)}
.band{margin:0 0 14px}
.band > .bh{display:flex;align-items:center;gap:10px;margin:2px 2px 8px;padding:6px 4px;
  border-bottom:1px solid var(--w-line)}
.band > .bh .dot{width:11px;height:11px;border-radius:50%}
.band > .bh b{font-size:14px}
.band > .bh .cnt{color:var(--w-dim);font-size:12px}
.cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(310px,1fr));gap:10px}
.card{background:var(--w-panel2);border:1px solid var(--w-line);border-radius:9px;padding:10px 11px;
  border-left:4px solid var(--w-line);position:relative}
.card.b0{border-left-color:var(--w-ok)}
.card.b1{border-left-color:var(--w-gold2)}
.card.b2{border-left-color:var(--w-band2)}
.card.b3{border-left-color:var(--w-band3)}
.card.locked{opacity:.62}
.card.acquired{opacity:.6}
.acq-btn{position:absolute;top:8px;right:8px;z-index:2;background:var(--w-chip);border:1px solid var(--w-line);
  color:var(--w-dim);border-radius:6px;padding:2px 7px;font-size:11px;cursor:pointer;line-height:1.4}
.acq-btn:hover{border-color:var(--w-gold2);color:var(--w-txt)}
.acq-btn.on{background:var(--w-okbg);border-color:var(--okbd);color:var(--oktx)}
.card h3{margin:0 0 3px;font-size:14px;line-height:1.2;padding-right:78px}
.card .cat{display:inline-block;font-size:10.5px;color:var(--w-dim);border:1px solid var(--w-line);
  border-radius:20px;padding:1px 8px;margin-bottom:6px}
.card .mission{color:var(--w-dim);font-size:11.5px;margin:0 0 7px;font-style:italic}
.chips{display:flex;flex-wrap:wrap;gap:5px}
.chip{font-size:11.5px;border-radius:6px;padding:3px 7px;border:1px solid var(--w-line);
  background:var(--w-chip);display:flex;gap:5px;align-items:center;cursor:default}
.chip.ok{background:var(--w-okbg);border-color:var(--okbd);color:var(--oktx)}
.chip.miss{background:var(--w-missbg);border-color:var(--badbd);color:var(--badtx);cursor:pointer}
.chip .q{font-weight:700;font-variant-numeric:tabular-nums}
.chip .cr{color:var(--w-gold);font-size:10px}
.card .foot{display:flex;justify-content:space-between;align-items:center;margin-top:8px;
  color:var(--w-dim);font-size:11px;gap:8px}
.effort{display:flex;align-items:center;gap:4px;color:var(--w-dim);font-size:10.5px}
.edot{width:7px;height:7px;border-radius:50%;background:var(--w-line);display:inline-block}
.edot.on{background:var(--w-gold2)}
.badge{border-radius:5px;padding:1px 6px;font-size:10.5px;border:1px solid var(--w-line)}
.badge.rep{color:var(--w-gold)}
.badge.lock{background:var(--badbg);border-color:var(--badbd);color:var(--badtx)}
.badge.ret{background:var(--w-retbg);border-color:var(--w-retbd);color:var(--w-rettx)}
.det{margin-top:7px;border-top:1px dashed var(--w-line);padding-top:7px;display:none}
.det.open{display:block}
.det .row{margin:4px 0;font-size:11.5px;line-height:1.35}
.det .row b{color:var(--w-txt)}
.det .src{color:var(--w-gold);font-size:10px;text-transform:uppercase;letter-spacing:.4px}
.det .sub{color:var(--w-dim)}
.det .opt{display:inline-block;background:var(--w-chip);border:1px solid var(--w-line);border-radius:5px;
  padding:1px 6px;margin:2px 4px 0 0;font-size:11px}
.tog{cursor:pointer;color:var(--w-gold)}
.empty{color:var(--w-dim);padding:18px;text-align:center}
.legend{display:flex;flex-wrap:wrap;gap:10px;color:var(--w-dim);font-size:11px;margin-top:6px;align-items:center}
.legend span{display:flex;gap:5px;align-items:center}
.sw{width:10px;height:10px;border-radius:3px;display:inline-block}
.toast{position:fixed;bottom:16px;left:50%;transform:translateX(-50%);background:var(--w-navy2);
  border:1px solid var(--w-gold2);color:var(--w-txt);padding:9px 16px;border-radius:8px;z-index:50;
  opacity:0;transition:opacity .2s;pointer-events:none}
.toast.show{opacity:1}
/* Changelog modal */
.modal{position:fixed;inset:0;background:rgba(0,0,0,.62);z-index:60;display:none;
  align-items:center;justify-content:center;padding:20px}
.modal.open{display:flex}
.modal-box{background:var(--w-panel);border:1px solid var(--w-gold2);border-radius:12px;
  max-width:720px;width:100%;max-height:85vh;display:flex;flex-direction:column;box-shadow:0 16px 48px rgba(0,0,0,.5)}
.modal-head{display:flex;justify-content:space-between;align-items:center;padding:11px 16px;border-bottom:1px solid var(--w-line)}
.modal-head b{font-size:15px;color:var(--w-gold)}
.modal-body{overflow:auto;padding:4px 18px 12px}
.modal-body h3{color:var(--w-gold);font-size:15px;margin:16px 0 6px;border-bottom:1px solid var(--w-line);padding-bottom:4px}
.modal-body h4{font-size:11.5px;color:var(--w-gold2);text-transform:uppercase;letter-spacing:.5px;margin:10px 0 3px}
.modal-body ul{margin:3px 0;padding-left:20px}
.modal-body li{margin:3px 0;line-height:1.4}
.modal-body p{color:var(--w-dim);line-height:1.4;margin:6px 0}
.modal-body code{background:var(--w-panel2);border:1px solid var(--w-line);border-radius:4px;padding:0 4px;font-size:12px}
.modal-body a{word-break:break-word}
.modal-foot{padding:10px 16px;border-top:1px solid var(--w-line);text-align:right;font-size:12.5px}
/* Responsive overrides at the very end so they override the base rules */
.controls{gap:8px 10px}
.wgrp{display:flex;flex-wrap:wrap;gap:8px 12px;align-items:center;padding:6px 10px;border:1px solid var(--w-line);border-radius:10px;background:var(--w-panel2)}
.wlbl{font-family:var(--disp);font-weight:700;font-size:11px;letter-spacing:.12em;text-transform:uppercase;color:var(--w-dim)}
.wsep{width:8px}
@media(max-width:919px){
  main{grid-template-columns:1fr;padding:0 12px 14px}
  .side{position:static;max-height:none}
  .side .scroll{max-height:none}
  .wtools{position:static}
  .sc-ptabs{margin:10px 12px 0}
  .wtools{border-top:0;padding:10px 12px}
}
@media(max-width:600px){
  .wgrp{width:100%}
  #offerSearch{flex:1 1 100%;min-width:0!important}
}
@media(pointer:coarse){
  .qbtn{width:44px;height:44px;font-size:18px}
  .seg button{min-height:44px}
}
/*FH_CSS*/
</style>
<!--FH_FONTS-->
</head>
<body>
<div class="hazard"></div>
<div class="fhwrap">
<!--FH_HEADER-->
</div>
<div class="sc-ptabs" id="wkTabs"></div>
<div class="wtools">
  <div class="controls">
    <div class="wgrp" id="grpView" role="group" aria-labelledby="wgView"><span class="wlbl" id="wgView" data-i18n="grpView">Ansicht</span>
      <div class="seg" id="modeSeg">
        <button data-mode="aufwand" class="on" data-i18n="modeEffort">Nach Aufwand</button>
        <button data-mode="gruppe" data-i18n="modeGroup">Nach Artikelgruppe</button>
      </div>
      <label><span data-i18n="repLabel">Mein Wikelo-Ruf:</span>
        <input type="number" id="myRep" min="0" step="5" value="0" style="width:76px">
      </label>
      <label><input type="checkbox" id="onlyRep"> <span data-i18n="onlyRep">nur erfüllbarer Ruf</span></label>
      <label><input type="checkbox" id="showRetired"> <span data-i18n="showRetired">zurückgezogene zeigen</span></label>
      <label><input type="checkbox" id="showAcquired"> <span data-i18n="showAcquired">erworbene zeigen</span> <span class="meta" id="acqCount"></span></label>
      <input type="text" id="offerSearch" data-i18n-ph="offerSearchPh" placeholder="Angebote filtern…" style="min-width:150px">
    </div>
    <div class="wgrp" id="grpInv" role="group" aria-labelledby="wgInv"><span class="wlbl" id="wgInv" data-i18n="grpInv">Bestand</span>
      <button class="btn prim" id="btnSave" data-i18n="btnSave" data-i18n-title="btnSaveTitle" title="Klick: speichern · Rechtsklick: Speicherort neu wählen">💾 Bestand speichern</button>
      <button class="btn" id="btnLoad" data-i18n="btnLoad">📂 Bestand laden</button>
      <span class="wsep" aria-hidden="true"></span>
      <button class="btn danger" id="btnReset" data-i18n="btnReset">leeren</button>
      <input type="file" id="fileInput" accept=".json,application/json" style="display:none">
    </div>
  </div>
</div>

<main>
  <aside class="panel side" id="wkSide">
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
    <div style="padding:5px 12px 0;color:var(--w-dim);font-size:11px;line-height:1.4">
      <span data-i18n="qtyHint">Menge: Klick +1 · Shift +10 · Strg +50 · Alt +100</span>
      <span style="color:var(--w-dim)" data-i18n="qtyHint2">(Mausrad = hoch/runter, Rechtsklick = minus, gleiche Modifier)</span>
    </div>
    <label style="padding:6px 12px;color:var(--w-dim);font-size:12px;display:flex;gap:6px;align-items:center">
      <input type="checkbox" id="onlyHave"> <span data-i18n="onlyHave">nur „hab ich" zeigen</span>
    </label>
    <div class="scroll" id="resList"></div>
  </aside>

  <section id="wkOffers">
    <div class="legend">
      <span><i class="sw" style="background:var(--w-ok)"></i> <span data-i18n="lgNow">sofort</span></span>
      <span><i class="sw" style="background:var(--w-gold2)"></i> <span data-i18n="lg1">1 fehlt</span></span>
      <span><i class="sw" style="background:var(--w-band2)"></i> <span data-i18n="lg2">2 fehlen</span></span>
      <span><i class="sw" style="background:var(--w-band3)"></i> <span data-i18n="lg3">3+ fehlen</span></span>
      <span>· <span data-i18n="lgEffort">Aufwand = Gesamtaufwand des Fehlenden (Menge × Beschaffung)</span></span>
      <span style="margin-left:auto" data-i18n="tip">Menge links: Klick +1 · Shift +10 · Strg +50 · Alt +100 (Mausrad/Rechtsklick ebenso)</span>
    </div>
    <div id="offers" style="margin-top:12px"></div>
  </section>
</main>

<div class="toast" id="toast"></div>

<!--FH_DIALOG-->

<script id="wikelo-raw" type="application/json">/*__RAW__*/</script>
<script>
// localStorage keys: inventory, preferences, cached refreshed raw data, acquired marks
const LS_INV = 'sc_wikelo_inv_v1', LS_PREF = 'sc_wikelo_pref_v1', LS_RAW = 'sc_wikelo_raw_v2';
const LS_ACQ = 'sc_wikelo_acq_v1';   // offers marked as acquired (key = mission_name, stable)
const RAW_BAKED = JSON.parse(document.getElementById('wikelo-raw').textContent);

// ===== Preparation logic – the ONE source of truth (offline build and in-app refresh alike) =====
// Category order, sourcing effort per unit by source class (currency hardest, mining easiest), source order
const CAT_ORDER = {ship:0,vehicle:1,weapon:2,armor:3,gear:4,intro:5};
const SRC_UNIT  = {currency:4,mining:1,creature:2,salvage:2,cz:3,loot:3,craft:2,item:1};
const SRC_ORDER = ['currency','mining','creature','salvage','cz','loot','craft','item'];

// ===== Bilingual UI (DE/EN) =====
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
  de:{currency:'Wikelo-Favor/Scrip – per Tausch (siehe unten)',mining:'Mining / teils kaufbar',creature:'Creature-Jagd (Valakkar / Kopion / Yormandi)',salvage:'Salvage / Vanduul-Gebiete',cz:'Contested Zones / Tech-Loot (PvP-Risiko)',loot:'Missionsbelohnung / seltener Loot',craft:'Craften – Rezept siehe unten',item:'Kauf / Loot'},
  en:{currency:'Wikelo Favor/Scrip – via exchange (see below)',mining:'Mining / partly buyable',creature:'Creature hunt (Valakkar / Kopion / Yormandi)',salvage:'Salvage / Vanduul areas',cz:'Contested Zones / tech loot (PvP risk)',loot:'Mission reward / rare loot',craft:'Craft it – recipe below',item:'Buy / loot'}};
const BAND_LABEL = {
  de:['Sofort verfügbar','1 Zutat fehlt','2 Zutaten fehlen','3+ Zutaten fehlen'],
  en:['Available now','1 ingredient missing','2 ingredients missing','3+ ingredients missing']};
const I18N = {
  de:{ modeEffort:'Nach Aufwand', modeGroup:'Nach Artikelgruppe', repLabel:'Mein Wikelo-Ruf:',
    grpView:'Ansicht', grpInv:'Bestand', onlyRep:'nur erfüllbarer Ruf', showRetired:'zurückgezogene zeigen', showAcquired:'erworbene zeigen',
    offerSearchPh:'Angebote filtern…',
    btnSave:'💾 Bestand speichern', btnSaveTitle:'Klick: speichern · Rechtsklick: Speicherort neu wählen',
    btnLoad:'📂 Bestand laden', btnReset:'leeren',
    btnRefresh:'🔄 Neuesten Stand laden (GitHub)', btnRefreshTitle:'Neuesten täglich gebauten Datenstand von GitHub laden (Rechtsklick: auf Build-Daten zurücksetzen)',
    btnChangelog:'🆕 Was ist neu?', btnSwap:'Bauplan-Planer', btnSwapHandel:'Handels-Planer', btnGuides:'Guides-Übersicht', clTitle:'Was ist neu?', clGh:'Vollständiges Changelog auf GitHub ↗',
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
    exchange:'Tausch:', priceBuy:'kaufbar ≈ {p} aUEC/SCU', priceSell:'Verkaufswert ≈ {p} aUEC/SCU', avgMarket:'Ø Markt', moreSell:'{n} Verkaufsorte bei star-head', priceDate:'Stand {d}',
    confirmClear:'Wirklich den ganzen Bestand leeren?', confirmReset:'Auf die eingebauten Build-Daten zurücksetzen (gecachte Aktualisierung verwerfen)?',
    toastReset:'Auf Build-Daten zurückgesetzt', toastRefreshed:'Neuester Stand geladen · {n} Angebote, Patch {p}', toastSame:'Du hast bereits den neuesten Stand.',
    toastRefreshFail:'GitHub nicht erreichbar – bestehende Daten bleiben',
    toastBpFail:'Baupläne (star-head) nicht erreichbar',
    toastSaved:'Bestand gespeichert', toastLoaded:'Bestand geladen: {n} Ressourcen',
    toastBadFile:'Ungültige Datei (kein Bestand-JSON)', toastPreload:'Bestand aus SC_Wikelo_Bestand.json vorgeladen',
    loading:'⏳ lädt…', metaBuilt:'gebaut {d}', metaRefreshed:'GitHub-Stand {d}',
    metaLine:'Patch {patch} · Daten {data} · {no} Angebote · {ni} Ressourcen · {fresh}' },
  en:{ modeEffort:'By effort', modeGroup:'By category', repLabel:'My Wikelo reputation:',
    grpView:'View', grpInv:'Inventory', onlyRep:'only reachable rep', showRetired:'show retired', showAcquired:'show acquired',
    offerSearchPh:'Filter offers…',
    btnSave:'💾 Save stock', btnSaveTitle:'Click: save · Right-click: choose new location',
    btnLoad:'📂 Load stock', btnReset:'clear',
    btnRefresh:'🔄 Load latest build (GitHub)', btnRefreshTitle:'Load the latest daily build from GitHub (right-click: reset to built-in data)',
    btnChangelog:'🆕 What\'s new?', btnSwap:'Blueprint Planner', btnSwapHandel:'Trade Planner', btnGuides:'Guides overview', clTitle:'What\'s new?', clGh:'Full changelog on GitHub ↗',
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
    exchange:'Exchange:', priceBuy:'buyable ≈ {p} aUEC/SCU', priceSell:'sell value ≈ {p} aUEC/SCU', avgMarket:'market avg', moreSell:'{n} sell locations on star-head', priceDate:'as of {d}',
    confirmClear:'Really clear the entire stock?', confirmReset:'Reset to the built-in build data (discard cached refresh)?',
    toastReset:'Reset to build data', toastRefreshed:'Latest build loaded · {n} offers, patch {p}', toastSame:'You already have the latest build.',
    toastRefreshFail:'GitHub unreachable – existing data kept',
    toastBpFail:'Blueprints (star-head) unreachable',
    toastSaved:'Stock saved', toastLoaded:'Stock loaded: {n} resources',
    toastBadFile:'Invalid file (not a stock JSON)', toastPreload:'Stock preloaded from SC_Wikelo_Bestand.json',
    loading:'⏳ loading…', metaBuilt:'built {d}', metaRefreshed:'GitHub build {d}',
    metaLine:'patch {patch} · data {data} · {no} offers · {ni} resources · {fresh}' }
};
// Translate key k (fallback: German, then the key itself) and fill {placeholders} from p
function t(k,p){ let s=(I18N[LANG]&&I18N[LANG][k]!=null)?I18N[LANG][k]:(I18N.de[k]!=null?I18N.de[k]:k);
  if(p) for(const key in p) s=s.split('{'+key+'}').join(p[key]); return s; }
// Label lookups for the current language with German fallback
const catLabel=k=>(CAT_LABEL[LANG][k]||CAT_LABEL.de[k]||k);
// Display name of an ingredient source class
const srcLabel=k=>(SRC_LABEL[LANG][k]||SRC_LABEL.de[k]||k);
// Short procurement hint for a source class
const srcHint =k=>(SRC_HINT[LANG][k]||SRC_HINT.de[k]||'');
// Display name of an offer status (active / retired)
const statusLabel=k=>(STATUS_LABEL[LANG][k]||STATUS_LABEL.de[k]||k);
// Heading of an effort band (0 = available now … 3 = 3+ missing)
const bandLabel=i=>(BAND_LABEL[LANG][i]||BAND_LABEL.de[i]);
const RECIPE_RE = /^\s*(\d+)\s*x\s+(.*\S)\s*$/;
const cmp = (a,b)=> a<b?-1:a>b?1:0;   // code-point comparison like Python (no localeCompare)

// Split a recipe string "12 x Name; Other" into [{name, qty}] (parts without "n x" count as 1)
function parseRecipe(s){
  const out=[];
  for(let part of String(s==null?'':s).split(';')){
    part=part.trim(); if(!part) continue;
    const m=part.match(RECIPE_RE);
    out.push(m ? {name:m[2], qty:parseInt(m[1],10)} : {name:part, qty:1});
  }
  return out;
}
// Display name of a Wikelo record: reward, else name, else mission name
function nameOf(rec){ return String(rec.reward||rec.name||rec.mission_name||'').trim(); }
// Ore ingredient -> commodity base name for the price lookup (only the four Wikelo ores), else null
function oreCommodity(name){
  const base=String(name).trim().replace(/\s*\((Ore|Pure)\)$/,'').trim();
  return ['Carinite','Jaclium','Saldynium','Sadaryx'].includes(base)?base:null;
}
// Classify an ingredient into a source class by name keywords (currency, mining, creature, loot, …)
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
// Turn the raw bundle into the app model: sorted offers, currency exchanges, ingredients with source/blueprint/ore
function transform(raw){
  const w = raw.wikelo||{};
  const allrecs = [...(w.ships||[]), ...(w.items||[]), ...(w.intro_mission?[w.intro_mission]:[])];
  const bpMap={};
  for(const b of (raw.blueprints||[])) if(b && b.name && b.costs && b.costs.length) bpMap[b.name]=b.costs;
    // Category sort rank; unknown categories go last
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

// Active raw data: cached refresh (if the schema matches), otherwise the baked-in build data
function loadRaw(){
  try{ const c=JSON.parse(localStorage.getItem(LS_RAW)||'null');
    if(c && c.schema===RAW_BAKED.schema && c.wikelo) return c; }catch(e){}
  return RAW_BAKED;
}
let RAW = loadRaw();
let DATA = transform(RAW);

// ---- state ----
let inv = {};
let acq = {};   // {mission_name: {reward, ts}} – marked as acquired (by mission_name, stable across refresh)
let pref = {mode:'aufwand', myRep:0, onlyRep:false, showRetired:false, showAcquired:false, onlyHave:false, lang:'de'};
let lsInv = null;
try{ lsInv = JSON.parse(localStorage.getItem(LS_INV)||'null'); }catch(e){}
if(lsInv && Object.keys(lsInv).length){ inv = lsInv; }
else { inv = Object.assign({}, DATA.saved_inv||{}); }   // preset from SC_Wikelo_Bestand.json
let lsAcq = null;
try{ lsAcq = JSON.parse(localStorage.getItem(LS_ACQ)||'null'); }catch(e){}
if(lsAcq && Object.keys(lsAcq).length){ acq = lsAcq; }
else { acq = Object.assign({}, DATA.saved_acq||{}); }    // same preset logic as the inventory
try{ Object.assign(pref, JSON.parse(localStorage.getItem(LS_PREF)||'{}')||{}); }catch(e){}
// Light/dark: set before the first paint, store the choice in pref
document.documentElement.setAttribute('data-theme', pref.theme||'dark');
document.getElementById('themeBtn').addEventListener('click', ()=>{
  const n=document.documentElement.getAttribute('data-theme')==='dark'?'light':'dark';
  document.documentElement.setAttribute('data-theme',n); pref.theme=n; savePref();
});
// Tabs on narrow screens: offers first
scPanels(document.getElementById('wkTabs'),[
  {key:'off',label:'<span class="fh-de">Angebote</span><span class="fh-en">Offers</span>',els:[document.getElementById('wkOffers'),document.getElementById('grpView')]},
  {key:'inv',label:'<span class="fh-de">Mein Bestand</span><span class="fh-en">My inventory</span>',els:[document.getElementById('wkSide'),document.getElementById('grpInv')]}],'off');

// Persist the inventory to localStorage (errors ignored, e.g. blocked storage)
function saveInv(){ try{localStorage.setItem(LS_INV, JSON.stringify(inv));}catch(e){} }
// Persist acquired marks
function saveAcq(){ try{localStorage.setItem(LS_ACQ, JSON.stringify(acq));}catch(e){} }
// Persist preferences
function savePref(){ try{localStorage.setItem(LS_PREF, JSON.stringify(pref));}catch(e){} }
// Amount of ingredient n in the inventory (0 if none)
function have(n){ return inv[n]||0; }
// Set the amount of ingredient n (rounded, min 0; 0 removes it), persist and re-render
function setHave(n,q){ q=Math.max(0,Math.round(q||0)); if(q<=0) delete inv[n]; else inv[n]=q; saveInv(); rerenderAll(); }
// Acquired mark keyed by mission_name (more stable than the position-dependent offer.id)
function isAcq(o){ return !!(o && o.mission && acq[o.mission]); }
// Toggle the acquired mark of the offer with mission name mkey, persist and re-render
function toggleAcq(mkey){
  if(!mkey) return;
  if(acq[mkey]){ delete acq[mkey]; toast(t('toastUnacq')); }
  else { const o=DATA.offers.find(x=>x.mission===mkey); acq[mkey]={reward:o?o.reward:mkey, ts:new Date().toISOString()}; toast(t('toastAcq')); }
  saveAcq(); rerenderAll();
}

// ---- helpers ----
// DOM shortcuts: first match / all matches as array
const $=s=>document.querySelector(s), $$=s=>[...document.querySelectorAll(s)];
// Show a short status message at the bottom for 1.8 s
function toast(m){ const t=$('#toast'); t.textContent=m; t.classList.add('show'); clearTimeout(t._t); t._t=setTimeout(()=>t.classList.remove('show'),1800); }
// Escape text for safe insertion into HTML
function esc(s){ return (s||'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c])); }
// Format a number with German thousands separators
function fmt(n){ return Math.round(n).toLocaleString('de-DE'); }
// Sourcing effort per unit of an ingredient, from its source class (default 2)
function unitOf(name){ const info=DATA.ingredients[name]||{}; return SRC_UNIT[info.src]||2; }
// Effort (quantity-weighted) -> 1..5 stars, log-compressed (calibrated: Wikelo Arrive≈1★, Idris≈5★)
function starsOf(raw){ if(raw<=0) return 0; const l=Math.log10(raw);
  return l<1?1 : l<1.6?2 : l<2.1?3 : l<2.7?4 : 5; }

// offer analysis
// Compare an offer with the inventory: missing items, band (0..3), weighted effort, stars, reputation check
function analyze(o){
  let missTypes=0, missQty=0, missing=[], effort=0;
  for(const it of o.recipe){
    const need=it.qty, has=have(it.name), gap=Math.max(0,need-has);
    if(gap>0){ missTypes++; missQty+=gap; effort+=gap*unitOf(it.name); missing.push({name:it.name, gap, need, has}); }
  }
  const band = missTypes>=3?3:missTypes;
  const stars = starsOf(effort);                          // total sourcing effort of what is missing
  const repOk = (pref.myRep||0) >= (o.rep_req||0);
  return {missTypes, missQty, missing, band, effort, stars, repOk};
}

const BANDS=[ {k:0,dot:'var(--w-ok)'}, {k:1,dot:'var(--w-gold2)'}, {k:2,dot:'var(--w-band2)'}, {k:3,dot:'var(--w-band3)'} ];

// ---- inventory panel ----
// Render the inventory list grouped by source class, honouring the search and "only have" filter
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
// Procurement hint for a missing ingredient: blueprint recipe, Wikelo exchange, or ore price
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
    // Older builds (UEX, up to 1.6.1) have no place; star-head entries carry place, date and the sell count.
    const p=DATA.prices[info.ore], q=t('avgMarket');
    const where=h=>(h.loc?` (${esc(h.loc)}${h.date?', '+esc(t('priceDate',{d:h.date})):''})`:` (${q})`);
    if(p.buy) extra = t('priceBuy',{p:fmt(p.buy.price)}) + where(p.buy);
    else if(p.sell) extra = t('priceSell',{p:fmt(p.sell.price)}) + where(p.sell)
      + (p.n_sell>1?' · '+esc(t('moreSell',{n:p.n_sell})):'');
  }
  return {src:info.src, hint:srcHint(info.src), extra};
}

// ---- offers ----
// Build the HTML card of one offer: ingredient chips, missing-item details, effort stars, badges
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
  // Details: every missing ingredient with its procurement hint
  let detHtml='';
  if(a.missing.length){
    detHtml = `<div class="det">`+ a.missing.map(m=>{
        const h=hintFor(m.name);
        return `<div class="row"><span class="src">${esc(srcLabel(h.src))}</span>
          <b>${m.gap}× ${esc(m.name)}</b>${m.has?` <span class="sub">(${t('haveShort',{have:m.has,need:m.need})})</span>`:''}
          <div class="sub">${h.extra||esc(h.hint)}</div></div>`;
      }).join('') + `</div>`;
  }
  // Effort stars (1..5) – quantity-weighted
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
      <span>${a.missing.length?`<span class="tog">${t('getMissing')} ▾</span>`:`<span style="color:var(--w-ok)">${t('complete')}</span>`}</span>
      <span style="display:flex;gap:8px;align-items:center">${dots} ${retBadge} ${rewBadge} ${repBadge}</span>
    </div>
  </div>`;
}

// Apply the offer filters: acquired, retired, reachable reputation, search text
function passFilter(o,a){
  if(isAcq(o) && !pref.showAcquired) return false;   // acquired -> hidden (unless shown)
  if(o.status!=='active' && !pref.showRetired) return false;
  if(pref.onlyRep && !a.repOk) return false;
  const q=($('#offerSearch').value||'').toLowerCase();
  if(q){
    const hay=(o.reward+' '+o.mission+' '+catLabel(o.artkey)+' '+o.artkey+' '+o.recipe.map(r=>r.name).join(' ')).toLowerCase();
    if(!hay.includes(q)) return false;
  }
  return true;
}

// Order within a band: band, reputation ok, effort, missing amount, then name
function sortCmp(p,q){
  const A=[p.a.band, p.a.repOk?0:1, p.a.effort, p.a.missQty, p.o.reward.toLowerCase()];
  const B=[q.a.band, q.a.repOk?0:1, q.a.effort, q.a.missQty, q.o.reward.toLowerCase()];
  for(let i=0;i<A.length;i++){ if(A[i]<B[i])return -1; if(A[i]>B[i])return 1; } return 0;
}

// Render all filtered offers, grouped by effort band or by category depending on the mode
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
      html+=`<div class="band"><div class="bh"><span class="dot" style="background:var(--w-navy2)"></span>
        <b>${esc(catLabel(cat))}</b><span class="cnt">${items.length}</span></div>
        <div class="cards">${items.map(x=>offerCard(x.o)).join('')}</div></div>`;
    }
  }
  $('#offers').innerHTML = html || `<div class="empty">${t('noOffers')}</div>`;
}

// Show the acquired count; the tooltip lists acquired offers no longer in the data
function updateAcqCount(){
  const el=$('#acqCount'); if(!el) return;
  const total=Object.keys(acq).length;
  el.textContent = total? t('acqCount',{n:total}) : '';
  // Orphans = acquired offers whose mission_name is missing from the current data (possible after a refresh)
  const present=new Set(DATA.offers.map(o=>o.mission));
  const orphans=Object.entries(acq).filter(([k])=>!present.has(k)).map(([,v])=>v.reward);
  el.title = orphans.length? t('acqOrphan',{n:orphans.length})+': '+orphans.join(', ') : '';
}
// Re-render inventory, offers and acquired count
function rerenderAll(){ renderRes(); renderOffers(); updateAcqCount(); }

// ---- Quick entry (command bar) ----
let quickMatches=[], quickIndex=0;
// Split quick-entry text into a search query and an optional number ("50" sets, "+50" adds)
function parseQuick(raw){
  const m=raw.match(/^(.*?)\s+([+]?\d+)\s*$/);
  return m ? {query:m[1].trim(), num:m[2]} : {query:raw.trim(), num:null};
}
// Rank up to 8 ingredients whose name contains all tokens (prefix and frequent ingredients first)
function qMatch(q){
  q=q.toLowerCase().trim(); if(!q) return [];
  const toks=q.split(/\s+/), out=[];
  for(const name of Object.keys(DATA.ingredients)){
    const ln=name.toLowerCase();
    if(!toks.every(t=>ln.includes(t))) continue;
    let score=0;
    if(ln.startsWith(q)) score-=100;
    const idx=ln.indexOf(q); if(idx>=0) score-=(50-Math.min(idx,49));
    score-=(DATA.ingredients[name].n_offers||0)*0.2;   // prefer frequent ingredients
    score+=ln.length*0.02;
    out.push({name,score});
  }
  out.sort((a,b)=>a.score-b.score);
  return out.slice(0,8);
}
// Render the suggestion list under the quick entry with the resulting amount
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
// Apply the quick entry to suggestion i (default: highlighted): +1, +n or set to n
function applyQuick(i){
  const idx=(i!=null)?i:quickIndex, m=quickMatches[idx]; if(!m) return;
  const {num}=parseQuick($('#quickAdd').value);
  if(num==null){ setHave(m.name, have(m.name)+1); toast('+1 '+m.name); }
  else if(num[0]==='+'){ const n=+num.slice(1)||0; setHave(m.name, have(m.name)+n); toast(m.name+' +'+n); }
  else { const n=+num||0; setHave(m.name, n); toast(m.name+' = '+n); }
  $('#quickAdd').value=''; quickIndex=0; renderQuick(); $('#quickAdd').focus();
}

// ---- Step size by modifier: click +1 · Shift +10 · Ctrl +50 · Alt +100 ----
// Step size of a mouse event from its modifier keys
function stepOf(e){ if(e.altKey) return 100; if(e.ctrlKey||e.metaKey) return 50; if(e.shiftKey) return 10; return 1; }

// ---- events: inventory ----
$('#resList').addEventListener('click', e=>{
  const row=e.target.closest('.res'); if(!row) return;
  const n=row.dataset.n, s=stepOf(e);
  const btn=e.target.closest('.qbtn');
  if(btn){ setHave(n, have(n)+(btn.dataset.a==='inc'?s:-s)); return; }
  // Row click: with modifier +step, otherwise toggle (0<->1)
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
// ---- events: quick entry ----
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

// ---- Save / load inventory (file, free location) ----
// File format v2: {schema, inventory:{name:amount}, acquired:{mission:{reward,ts}}}.
// Where available (Chromium, secure context) save/load use the File System Access API,
// so the location is free to choose and a loaded file is written back on the next save.
// Otherwise fall back to download / file picker. Under file:// the API is often blocked -> fallback.
let fileHandle = null;   // last chosen file (this session only), for saving back
const FS_TYPES = [{description:'Wikelo-Bestand (JSON)', accept:{'application/json':['.json']}}];
// The object written to SC_Wikelo_Bestand.json
function buildSaveObject(){ return {schema:2, inventory:inv, acquired:acq}; }

// Save the inventory JSON as a browser download (fallback without File System Access API)
function downloadStock(text){
  const blob=new Blob([text],{type:'application/json'});
  const url=URL.createObjectURL(blob);
  const a=document.createElement('a'); a.href=url; a.download='SC_Wikelo_Bestand.json';
  document.body.appendChild(a); a.click(); a.remove();
  setTimeout(()=>URL.revokeObjectURL(url),1000);
  toast(t('toastSaved'));
}
// Save the inventory to the chosen file; a cancelled dialog does nothing, other errors fall back to download
async function saveStock(){
  const text=JSON.stringify(buildSaveObject(),null,1);
  if(window.showSaveFilePicker){
    try{
      if(!fileHandle) fileHandle=await window.showSaveFilePicker({suggestedName:'SC_Wikelo_Bestand.json', types:FS_TYPES});
      const w=await fileHandle.createWritable(); await w.write(text); await w.close();
      toast(t('toastSaved')); return;
    }catch(err){
      fileHandle=null;
      if(err && err.name==='AbortError') return;   // user cancelled the dialog -> do NOT download
      // other errors (no access / file://): fall back to download
    }
  }
  downloadStock(text);
}
// Parse a loaded inventory file (v2 or old flat format), replace inventory and acquired marks
function applyLoaded(text){
  try{
    const o=JSON.parse(text);
    if(typeof o!=='object'||o===null||Array.isArray(o)) throw 0;
    // v2 with inventory/acquired, otherwise old flat {name:amount} = inventory only
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
// Load an inventory file via the File System Access API, else via the hidden file input
async function loadStock(){
  if(window.showOpenFilePicker){
    try{
      const [h]=await window.showOpenFilePicker({types:FS_TYPES, multiple:false});
      const f=await h.getFile(); const text=await f.text();
      applyLoaded(text); fileHandle=h;   // remember the file -> saving writes back to it
      return;
    }catch(err){ if(err && err.name==='AbortError') return; /* otherwise: fallback */ }
  }
  $('#fileInput').click();
}
$('#btnSave').addEventListener('click', saveStock);
$('#btnSave').addEventListener('contextmenu', e=>{ e.preventDefault(); fileHandle=null; saveStock(); });  // right-click: choose a new location
$('#btnLoad').addEventListener('click', loadStock);
$('#fileInput').addEventListener('change', e=>{   // fallback without File System Access API
  const f=e.target.files[0]; if(!f) return;
  const rd=new FileReader();
  rd.onload=()=>applyLoaded(rd.result);
  rd.readAsText(f); e.target.value='';
});
$('#btnReset').addEventListener('click', ()=>{ if(confirm(t('confirmClear'))){ inv={}; saveInv(); rerenderAll(); } });

// ---- In-app data refresh ----
// Direct source endpoints (the refresh itself only loads DATA_URL)
const DATA_URL='https://jaegerfeld.github.io/StarCitizen-Wikelo-Planer/data.json';
const EP = {
  wikelo:     'https://seeknd.github.io/Wikelo/data/wikelo_data.json',
  blueprints: 'https://api.star-head.de/blueprint',
};
// Fetch a URL without cache and parse JSON; throws on HTTP errors
async function getJSON(url){ const r=await fetch(url,{cache:'no-store'}); if(!r.ok) throw new Error('HTTP '+r.status); return r.json(); }
// Set of all ingredient names used in the Wikelo recipes
function ingredientNamesFrom(w){
  const set=new Set(), recs=[...(w.ships||[]),...(w.items||[]),...(w.intro_mission?[w.intro_mission]:[])];
  for(const rec of recs) for(const it of parseRecipe(rec.recipe||'')) set.add(it.name);
  return set;
}
// Fetch star-head blueprints, keeping only those named like a Wikelo ingredient
async function fetchBlueprints(names){
  const bp=await getJSON(EP.blueprints), out=[];
  for(const b of bp){ const nm=b&&b.name; if(!nm||!names.has(nm)) continue;
    const costs=[]; for(const c of (b.costs||[])){ const rn=c&&c.commodity&&c.commodity.name; if(rn) costs.push({name:rn, qty:c.quantity||0}); }
    if(costs.length) out.push({name:nm, costs}); }
  return out;
}
// Load the latest data.json from GitHub Pages and switch to it, keeping the build's inventory preset
async function refreshData(){
  // Loads the data last built on GitHub (daily 05:00 UTC). No direct access to
  // star-head/seeknd from the browser any more – this spares the community sources.
  const btn=$('#btnRefresh'); if(btn.dataset.busy) return;
  btn.dataset.busy='1'; btn.disabled=true; const label=btn.textContent; btn.textContent=t('loading');
  try{
    const g=await getJSON(DATA_URL);
    if(!g || g.schema!==RAW_BAKED.schema || !g.wikelo) throw new Error('schema');
    if(g.generated && g.generated===RAW.generated && RAW.source==='refresh'){ toast(t('toastSame')); return; }
    const newRaw=Object.assign({}, g, { source:'refresh', saved_inv:(RAW.saved_inv||{}), saved_acq:(RAW.saved_acq||{}) });
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

// Fill the header data line: patch, data date, counts, build or refresh date
function updateMeta(){
  const m=DATA.meta, fresh = m.source==='refresh' ? t('metaRefreshed',{d:m.generated}) : t('metaBuilt',{d:m.generated});
  $('#meta').textContent = t('metaLine',{v:m.version, patch:m.patch, data:m.data_updated, no:m.n_offers, ni:m.n_ingredients, fresh});
}

// ---- Language (DE/EN) ----
// Translate all static elements marked with data-i18n / -ph / -title and the language switch
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
$('#myRep').value=pref.myRep||0; $('#onlyRep').checked=!!pref.onlyRep;
$('#showRetired').checked=!!pref.showRetired; $('#showAcquired').checked=!!pref.showAcquired; $('#onlyHave').checked=!!pref.onlyHave;
$$('#modeSeg button').forEach(x=>x.classList.toggle('on',x.dataset.mode===pref.mode));
if(!lsInv && Object.keys(inv).length) toast(t('toastPreload'));
rerenderAll();
/*FH_JS*/
</script>
</body>
</html>
"""



def fill_header(html):
    """Insert the shared header, the "What's new?" dialog and the changelog.

    Fills the placeholders ``<!--FH_HEADER-->``, ``<!--FH_FONTS-->``, ``/*FH_CSS*/``,
    ``/*FH_JS*/`` and ``<!--FH_DIALOG-->`` from kopfzeile.py and the shared
    design (light/dark) from sc_design.py; the refresh button goes into the header.

    Args:
        html: The template with ``/*__RAW__*/`` already replaced.

    Returns:
        The complete page HTML.
    """
    refresh = ('<button class="btn fh-btn" id="btnRefresh" type="button" data-i18n="btnRefresh" '
               'data-i18n-title="btnRefreshTitle" title="Neuesten täglich gebauten Datenstand von GitHub laden">'
               '🔄 Neuesten Stand laden (GitHub)</button>')
    head = kz.header_html(
        "wikelo",
        eyebrow=("Wikelo Emporium · Ressourcen", "Wikelo Emporium · Resources"),
        title=("SC Wikelo-Planer", "SC Wikelo Planner"),
        lede=("Welche Wikelo-Angebote kann ich mit meinem Bestand erfüllen, und was fehlt noch? "
              "Daten von seeknd und star-head.de – im Spiel gegenprüfen.",
              "Which Wikelo offers can I fulfil with my inventory, and what is still missing? "
              "Data from seeknd and star-head.de – verify in game."),
        version=VERSION, refresh=refresh, data='<span id="meta"></span>',
        lang=kz.lang_seg("langSeg"))
    html = html.replace("<!--FH_HEADER-->", head).replace("<!--FH_FONTS-->", sd.FONTS)
    html = html.replace("/*FH_CSS*/", kz.CSS + sd.CSS).replace("/*FH_JS*/", kz.JS + sd.JS)
    return html.replace("<!--FH_DIALOG-->", kz.dialog_html("wikelo", VERSION) + "\n"
                        + kz.changelog_script(OUTDIR / "CHANGELOG.md"))


def main():
    """Build SC_Wikelo_Planer.html and data.json from freshly downloaded data.

    The raw bundle is embedded as JSON in the page (``</`` escaped so it cannot
    close the script tag); data.json gets the same bundle without the personal
    inventory and acquired marks.
    """
    raw = build_raw()
    payload = json.dumps(raw, ensure_ascii=False, separators=(",", ":"))
    payload = payload.replace("</", "<\\/")
    html = HTML_TEMPLATE.replace("/*__RAW__*/", payload)
    html = fill_header(html)
    OUTHTML.write_text(html, encoding="utf-8")
    # data.json: the same snapshot without the personal inventory. The app's "load latest"
    # button fetches this file from GitHub Pages instead of star-head/seeknd.
    pub = {k: v for k, v in raw.items() if k not in ("saved_inv", "saved_acq")}
    OUTJSON.write_text(json.dumps(pub, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print("gespeichert:", OUTJSON)
    n_off = len(raw["wikelo"]["ships"]) + len(raw["wikelo"]["items"]) + 1
    n_pr = sum(1 for v in raw["prices"].values() if v.get("buy") or v.get("sell"))
    print("gespeichert:", OUTHTML)
    print(f"  {n_off} Angebote, {len(raw['blueprints'])} Baupläne, {n_pr} Erz-Preise.")
    print("FERTIG:", STAMP, "-> Datei per Doppelklick im Browser oeffnen.")


if __name__ == "__main__":
    main()
