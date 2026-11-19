#!/usr/bin/env python3
"""Smoke test for Necron Horde Mode (index.html).

Setup once:   pip install playwright && python3 -m playwright install chromium
Run:          python3 tests/test_app.py            (tests ../index.html)
              python3 tests/test_app.py path/to/index.html
              python3 tests/test_app.py http://localhost:8000/    (a local server, to test it the way GitHub Pages serves it)
Use a local Chrome instead of Playwright's Chromium:  CHROME_PATH=/path/to/chrome python3 tests/test_app.py

Exits non-zero on the first failed check and prints which one. Nothing leaves the machine: Google Fonts are blocked,
and only a server on localhost or 127.0.0.1 is accepted.

The embedded spawn tables and unit data are compared with the source files in reference/<faction>/ (git-ignored, see
README.md) when they are present; without them those checks are skipped and the rest still run.
"""
import importlib.util
import json
import os
import re
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
TARGET = sys.argv[1] if len(sys.argv) > 1 else str(ROOT / "index.html")
if TARGET.startswith(("http://", "https://")):
    if not re.match(r"http://(localhost|127\.0\.0\.1)(:\d+)?/", TARGET):
        sys.exit(f"Refusing {TARGET}: tests only talk to a server on localhost or 127.0.0.1.")
    URL = TARGET
else:
    URL = Path(TARGET).resolve().as_uri()
KEY = "horde-mode-necrons-v1"

passed = 0


def check(name, cond, detail=""):
    global passed
    if not cond:
        print(f"FAIL  {name}  {detail}")
        sys.exit(1)
    passed += 1
    print(f"ok    {name}")


def ev(pg, expression):
    return pg.evaluate(expression)


def fresh(pg):
    """Clears the saved game and reloads, so each section starts from a new game."""
    pg.evaluate(f"localStorage.removeItem('{KEY}')")
    pg.reload()
    pg.wait_for_selector("#tracker .tracker")


def tab(pg, name):
    pg.click(f'.tab[data-tab="{name}"]')


def nxt(pg):
    pg.click('[data-act="next"]')
    if pg.locator('[data-act="startearly-do"]').count():
        pg.click('[data-act="startearly-do"]')


def load_embed_tool():
    """tools/embed_data.py, loaded by path: its build() reads the same sources the embedded data came from."""
    spec = importlib.util.spec_from_file_location("embed_data", ROOT / "tools" / "embed_data.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# Cards with no automatic side effect, so a deterministic deck lets the tests count reveals exactly.
PLAIN_DECKS = """() => {
  state.decks.misery.draw = MISERY.filter(c => !c.auto).map(c => c.id);
  state.decks.secondary.draw = SECONDARY.filter(c => !c.r1redraw).map(c => c.id);
  render();
}"""

DATA_CHECK = r"""() => {
  const problems = [];
  const ids = new Set();
  [...MISERY, ...SECONDARY, ...SECRET, ...RESUPPLY].forEach(c => { if (ids.has(c.id)) problems.push('duplicate id ' + c.id); ids.add(c.id); });
  if (MISERY.length !== 36) problems.push('Misery count ' + MISERY.length);
  if (SECONDARY.length !== 24) problems.push('Secondary count ' + SECONDARY.length);
  if (SECRET.length !== 34) problems.push('Secret count ' + SECRET.length);
  if (RESUPPLY.length !== 26) problems.push('Resupply count ' + RESUPPLY.length);
  MISERY.forEach((c, i) => { if (c.n !== i + 1 || !c.name || !c.text) problems.push('misery ' + c.id); });
  SECONDARY.forEach((c, i) => {
    if (c.n !== i + 1 || !c.cond || !c.rew || !c.pen) problems.push('secondary ' + c.id + ' incomplete');
    const known = ['sp', 'spx', 'cp', 'spLose', 'misery', 'miseryX', 'spawn', 'spawnX', 'first', 'force', 'forceNow', 'removeShop', 'clearFortified', 'lz', 'save', 'grants', 'nobody', 'plans', 'custom'];
    ['rewFx', 'penFx'].forEach(k => Object.keys(c[k] || {}).forEach(f => { if (!known.includes(f)) problems.push(c.id + ' unknown fx ' + f); }));
    [c.rewFx, c.penFx].forEach(fx => { if (fx && fx.force && !MIS[fx.force]) problems.push(c.id + ' bad force id'); if (fx && fx.forceNow && !MIS[fx.forceNow]) problems.push(c.id + ' bad forceNow id'); if (fx && fx.removeShop && !SHOP[fx.removeShop]) problems.push(c.id + ' bad removeShop id'); });
    (c.rewFx && c.rewFx.grants || []).forEach(g => { if (!SHOP[g.item] || !['pick', 'random'].includes(g.to)) problems.push(c.id + ' bad grant'); });
    if (c.rewFx && c.rewFx.save && !c.perk) problems.push(c.id + ' saves a card that does nothing');
    if (c.perk && !(c.perk.cancelMisery || (c.perk.tag && SHOP_TAGS.includes(c.perk.tag)) || SHOP[c.perk.item])) problems.push(c.id + ' bad perk');
  });
  SECRET.forEach((c, i) => { if (c.n !== i + 1 || !c.tags.length) problems.push('secret ' + c.id); });
  RESUPPLY.forEach(c => {
    if (!c.tags.length || !c.text) problems.push('shop ' + c.id + ' incomplete');
    if (c.stand && !STANDING[c.stand]) problems.push(c.id + ' bad stand');
    if (c.count && !STANDING_COUNTED[c.count[0]]) problems.push(c.id + ' bad count');
  });
  const autos = new Set(['dice3', 'extra-zone', 'no-hard-feelings', 'lose5', 'draw2', 'clear-fortified', 'fetters']);
  MISERY.forEach(c => { if (c.auto && !autos.has(c.auto)) problems.push(c.id + ' unknown auto'); });
  for (const sheet of ['standard', 'detailed']) {
    BRACKET_KEYS.forEach(b => (SPAWN[sheet][b] || []).forEach(raw => {
      const e = parseEntry(raw);
      if (!e.label || !e.baseName) problems.push('unparsable ' + raw);
    }));
  }
  Object.keys(STAGES).forEach(k => { if (k !== 'setup' && k !== 'over' && k !== 'start' && k !== 'end' && !STEP_ITEMS[k]) problems.push('no step items for ' + k); });
  catalog().forEach(c => { if (!unitData(c.key)) problems.push('no datasheet for ' + c.key); });
  Object.keys(UNITS.units).forEach(k => { const u = UNITS.units[k]; if (!u.kw.length || !u.profiles.length || !(u.ranged || u.melee)) problems.push('incomplete datasheet ' + k); });
  return problems;
}"""


def main():
    launch = {"headless": True}
    if os.environ.get("CHROME_PATH"):
        launch["executable_path"] = os.environ["CHROME_PATH"]
    with sync_playwright() as p:
        browser = p.chromium.launch(**launch)
        ctx = browser.new_context(viewport={"width": 390, "height": 844})
        external = []
        ctx.route(re.compile(r"https://fonts\.(googleapis|gstatic)\.com/.*"), lambda route: route.abort())

        def on_request(req):
            if not (req.url.startswith("file:") or req.url.startswith("data:") or re.match(r"http://(localhost|127\.0\.0\.1)", req.url) or "fonts.g" in req.url):
                external.append(req.url)

        pg = ctx.new_page()
        errors = []
        pg.on("pageerror", lambda e: errors.append(str(e)))
        pg.on("console", lambda m: errors.append(m.text) if m.type == "error" and "fonts" not in m.text.lower() and "ERR_FAILED" not in m.text else None)
        pg.on("request", on_request)
        pg.goto(URL)
        pg.wait_for_selector("#tracker .tracker")

        # ---------- Boot ----------
        check("title", "Necron Horde Mode" in pg.title())
        check("five tabs", pg.locator(".tab").count() == 5)
        check("starts at setup, round 0", ev(pg, "state.stage === 'setup' && state.round === 0"))
        check("robots noindex kept", pg.locator('meta[name="robots"][content="noindex, nofollow"]').count() == 1)
        refs = re.findall(r'(?:src|href)="([^"]+)"', Path(ROOT / "index.html").read_text(encoding="utf-8"))
        bad_refs = [r for r in refs if not (r.startswith(("https://fonts.googleapis.com", "https://fonts.gstatic.com", "data:", "#")))]
        check("page references no files by relative or root-absolute path (portfolio-safe)", not bad_refs, str(bad_refs[:3]))

        # ---------- Data ----------
        problems = pg.evaluate(DATA_CHECK)
        check("data integrity", not problems, "; ".join(problems[:6]))
        tool = load_embed_tool()
        faction = ev(pg, "FACTION.key")
        check("the embedded data and FACTION name the same faction", ev(pg, "UNITS.faction") == faction and faction in tool.FACTIONS)
        if all(path.exists() for path in tool.source_paths(faction).values()):
            spawn, units = tool.build(faction)
            check(f"embedded spawn tables equal reference/{faction}/spawn-*.csv", ev(pg, "SPAWN") == spawn, "run tools/embed_data.py")
            check(f"embedded unit data equals what reference/{faction}/wahapedia-datasheets.html gives", ev(pg, "UNITS") == units, "run tools/embed_data.py")
        else:
            print(f"skip  source comparison: reference/{faction}/ is missing (see README.md, Updating the data)")
        check("unit data is 11th edition", "11th edition" in ev(pg, "UNITS.version"), ev(pg, "UNITS.version"))
        check("spawn sheet has a date", re.match(r"\d+/\d+/\d{4}", ev(pg, "SPAWN.updated")) is not None)
        check("collection catalog has characters and units", ev(pg, "catalog().length") > 40 and ev(pg, "catalogName('imotekh the stormlord')") == "Imotekh the Stormlord")
        check("entry parsing", ev(pg, "(() => { const e = parseEntry('Immortals (10) + Imotekh the Stormlord + Chronomancer'); return e.size === 10 && e.need.immortals === 10 && e.need['imotekh the stormlord'] === 1 && e.need.chronomancer === 1; })()"))
        check("placeholders are not units", ev(pg, "(() => { const e = parseEntry('Necron Warriors (20) + Leader + Support'); return e.placeholders.length === 2 && Object.keys(e.need).length === 1; })()"))
        check("last resort comes from the datasheet keywords", ev(pg, "[parseEntry('Doom Scythe').lastResort, parseEntry('Convergence Of Dominion (2)').lastResort, parseEntry('Monolith').lastResort, parseEntry('Night Scythe + Transported Unit').lastResort]") == ["Aircraft", "Fortification", None, None])

        # ---------- Round table and brackets ----------
        normal = ev(pg, "[1,2,3,4,5,6,9].map(r => roundRules(r))")
        check("normal round table (rules 3.3 to 3.5)", normal == [{"misery": 0, "spawn": 0}, {"misery": 1, "spawn": 0}, {"misery": 1, "spawn": 1}, {"misery": 1, "spawn": 1}, {"misery": 3, "spawn": 2}, {"misery": 3, "spawn": 2}, {"misery": 3, "spawn": 2}])
        hard = ev(pg, "(() => { const s = JSON.parse(JSON.stringify(state)); s.setup.hard = true; return [1,2,3,4,5,6].map(r => roundRules(r, s)); })()")
        check("hard round table (add-on)", hard == [{"misery": 1, "spawn": 0}, {"misery": 1, "spawn": 1}, {"misery": 2, "spawn": 2}, {"misery": 2, "spawn": 3}, {"misery": 3, "spawn": 3}, {"misery": 3, "spawn": None}])
        edges = ev(pg, "[2,3,4,5,6,7,9,10,12,13,20].map(t => bracketFor(t, false))")
        check("bracket edges", edges == [None, "3-4", "3-4", "5-6", "5-6", "7-9", "7-9", "10+", "10+", "10+", "10+"])
        check("13+ only when enabled", ev(pg, "bracketFor(13, true) === '13+' && bracketFor(15, false) === '10+'"))

        # ---------- Setup tab ----------
        tab(pg, "setup")
        check("setup shows points each", "500 pts each" in pg.inner_text("#main"))
        pg.click('[data-act="next"]')
        check("Start round 1 asks first while the deployment spawn is unfinished", pg.locator('[data-act="startearly-do"]').count() == 1 and ev(pg, "state.stage") == "setup")
        pg.click('[data-act="sheet-close"]')
        tab(pg, "horde")
        pg.locator('[data-act="rollzone"]').first.click()
        first_zone_button = pg.locator('[data-act="rollzone"]').first
        check("a rolled zone offers Re-roll, not the primary Roll for me", "Re-roll" in first_zone_button.inner_text() and "primary" not in first_zone_button.get_attribute("class"))
        ev(pg, "resetSpawn(state), render(), true")
        tab(pg, "turn")
        pg.locator('[data-act="tick"]').first.click()
        check("a ticked checklist item collapses to one line", pg.evaluate("getComputedStyle(document.querySelector('.item.done .txt')).whiteSpace") == "nowrap")
        pg.locator('[data-act="tick"]').first.click()
        tab(pg, "setup")
        pg.click('[data-act="set"][data-k="points"][data-v="2000"]')
        check("2000 pts gives 4 zones", ev(pg, "state.zones.length") == 4)
        pg.click('[data-act="set"][data-k="players"][data-v="3"]')
        check("3 players: 666 each, 3 player objects", "666 pts each" in pg.inner_text("#main") and ev(pg, "state.players.length") == 3)
        pg.click('[data-act="set"][data-k="points"][data-v="1000"]')
        pg.click('[data-act="set"][data-k="players"][data-v="2"]')
        check("back to 1000 pts, 2 players, 2 zones", ev(pg, "state.zones.length === 2 && state.players.length === 2"))
        pg.fill('[data-change="pname"][data-i="0"] >> nth=0', "Ana")
        pg.dispatch_event('[data-change="pname"][data-i="0"] >> nth=0', "change")
        check("player rename", ev(pg, "state.players[0].name") == "Ana")

        # ---------- Horde tab: spawn roll maths ----------
        tab(pg, "horde")
        z1 = ev(pg, "state.zones[0].id")
        pg.select_option(f'select[data-z="{z1}"][data-i="0"]', "3")
        pg.select_option(f'select[data-z="{z1}"][data-i="1"]', "4")
        check("2D6 3+4 in round 1 gives 7 and the [7-9] bracket", ev(pg, f"spawnResult(zoneOf(state, '{z1}')).bracket") == "7-9")
        check("a slot appears for the bracket", pg.locator(".slot .opt").count() >= 3)
        check("three ranked options shown first", pg.locator(".slot .opt").count() == 3)
        check("options are ranked 1 2 3", pg.eval_on_selector_all(".slot .opt .rk", "els => els.map(e => e.textContent)") == ["1", "2", "3"])

        # unmodified 2 never spawns, even with a big modifier
        pg.select_option(f'select[data-z="{z1}"][data-i="0"]', "1")
        pg.select_option(f'select[data-z="{z1}"][data-i="1"]', "1")
        for _ in range(8):
            pg.click('[data-act="manual"][data-d="1"]')
        res = ev(pg, f"(() => {{ const r = spawnResult(zoneOf(state, '{z1}')); return [r.none, r.total, r.bracket || null]; }})()")
        check("unmodified 2 spawns nothing even at +8", res == [True, 10, None])
        check("zone shows nothing spawns", "Nothing spawns" in pg.inner_text("#main"))
        for _ in range(8):
            pg.click('[data-act="manual"][data-d="-1"]')

        # cleared unit adds its bracket minimum (nothing can stand in a zone in round 1, so the picker is hidden)
        check("round 1 zones show no clear-the-zone picker", pg.locator(f'select[data-change="removed"][data-z="{z1}"]').count() == 0)
        ev(pg, f"mutate(s => setZoneCleared(s, '{z1}', 'b:5-6'))")
        pg.select_option(f'select[data-z="{z1}"][data-i="0"]', "2")
        pg.select_option(f'select[data-z="{z1}"][data-i="1"]', "2")
        check("cleared [5-6] unit adds 5 (4+5 = 9)", ev(pg, f"spawnResult(zoneOf(state, '{z1}')).total") == 9)
        ev(pg, f"mutate(s => setZoneCleared(s, '{z1}', ''))")

        # a modified roll under 3 has no bracket
        ev(pg, "state.manualMod = -4; render()")
        pg.select_option(f'select[data-z="{z1}"][data-i="0"]', "2")
        pg.select_option(f'select[data-z="{z1}"][data-i="1"]', "3")
        check("modified roll under 3 has no bracket", ev(pg, f"spawnResult(zoneOf(state, '{z1}')).none") is True)
        ev(pg, "state.manualMod = 0; render()")

        # ---------- Ranking and collection ----------
        pg.select_option(f'select[data-z="{z1}"][data-i="0"]', "4")
        pg.select_option(f'select[data-z="{z1}"][data-i="1"]', "3")
        ranked = ev(pg, "rankOptions('7-9', 'seed').map(o => [o.raw, o.available])")
        check("all options available with an empty collection", all(a for _, a in ranked) and len(ranked) == 25)
        top = ev(pg, "rankOptions('7-9', 'seed').slice(0, 3).map(o => o.entry.lastResort)")
        check("aircraft and fortifications are never in the top 3", not any(top))
        check("the [7-9] bracket really contains an aircraft and a fortification", ev(pg, "rankOptions('7-9', 'seed').filter(o => o.entry.lastResort).map(o => o.entry.lastResort).sort()") == ["Aircraft", "Fortification"])
        check("last-resort options are ranked below every other option", ev(pg, "(() => { const r = rankOptions('7-9', 'seed'); const first = r.findIndex(o => o.entry.lastResort); return r.slice(0, first).every(o => !o.entry.lastResort) && r.slice(first).every(o => o.entry.lastResort); })()"))
        ev(pg, "state.collection['immortals'] = 5; render()")
        short = ev(pg, "rankOptions('7-9', 'seed').filter(o => !o.available).map(o => o.raw)")
        check("owning 5 Immortals removes the 10-model entries", short and all("Immortals (10)" in n for n in short))
        best_avail = ev(pg, "rankOptions('7-9', 'seed')[0].available")
        check("unavailable options sort last", best_avail is True and ev(pg, "(() => { const r = rankOptions('7-9', 'seed'); const f = r.findIndex(o => !o.available); return r.slice(f).every(o => !o.available); })()"))
        check("reason chips explain the ranking", pg.locator(".slot .opt .chip").count() >= 3)
        ev(pg, "delete state.collection['immortals']; render()")

        # spawn, variety and roster
        pg.click('.slot .opt >> nth=0 >> [data-act="pick"]')
        check("spawning fills the slot and the roster", ev(pg, "state.horde.length") == 1 and "On the table (1)" in pg.inner_text("#main"))
        spawned = ev(pg, "state.horde[0].baseKey")
        check("an already-spawned unit is ranked down", ev(pg, f"(() => {{ const r = rankOptions('7-9', 'x2').filter(o => o.entry.baseKey === '{spawned}'); return r.every(o => o.reasons.some(x => x.text.includes('already on the table'))); }})()"))
        check("filled zone locks its dice", pg.locator(f'select[data-z="{z1}"][data-i="0"]').is_disabled())

        # collection uses up models
        ev(pg, f"state.collection['{spawned}'] = 1; render()")
        check("models on the table count against the collection", ev(pg, f"freeModels('{spawned}')") == (1 - ev(pg, f"usedModels('{spawned}')")))
        ev(pg, f"delete state.collection['{spawned}']; render()")

        # destroying a unit gives SP
        pg.click('[data-act="sheet"][data-type="destroy"]')
        check("destroy sheet opens", pg.locator(".sheet").count() == 1)
        pg.click('[data-act="destroy-by"][data-i="1"]')
        check("kill gives the killer 1 SP and removes the unit", ev(pg, "state.players[1].sp") == 1 and ev(pg, "state.horde.length") == 0)

        # roll down splits a slot into two lower ones
        z2 = ev(pg, "state.zones[1].id")
        pg.select_option(f'select[data-z="{z2}"][data-i="0"]', "6")
        pg.select_option(f'select[data-z="{z2}"][data-i="1"]', "5")
        check("roll of 11 uses [10+]", ev(pg, f"zoneOf(state, '{z2}').slots[0].bracket") == "10+")
        pg.click(f'[data-act="rolldown"][data-z="{z2}"]')
        brackets = ev(pg, f"zoneOf(state, '{z2}').slots.map(s => s.bracket)")
        check("roll down gives 2 slots one bracket lower", brackets == ["7-9", "7-9"])
        pg.click(f'[data-act="rolldown"][data-z="{z2}"] >> nth=0')
        brackets = ev(pg, f"zoneOf(state, '{z2}').slots.map(s => s.bracket)")
        check("each slot can roll down on its own", sorted(brackets) == ["5-6", "5-6", "7-9"])
        pg.click(f'[data-act="random"][data-z="{z2}"] >> nth=0')
        check("random pick proposes a unit without spawning it", ev(pg, "state.horde.length") == 0 and ev(pg, f"zoneOf(state, '{z2}').slots.some(s => s.draft)"))
        pg.click(f'[data-act="draft-accept"][data-z="{z2}"]')
        check("accepting the random pick spawns it", ev(pg, "state.horde.length") == 1)

        # the lowest bracket cannot roll down
        ev(pg, "state.zones.push(newZone(state)); render()")
        z3 = ev(pg, "state.zones[state.zones.length - 1].id")
        ev(pg, f"zoneOf(state, '{z3}').slots = [{{id: 1, bracket: '3-4', filled: null}}]; zoneOf(state, '{z3}').dice = [1, 2]; render()")
        check("[3-4] slot has no roll-down button", pg.locator(f'[data-act="rolldown"][data-z="{z3}"]').count() == 0)

        # ---------- Redo spawn ----------
        fresh(pg)
        tab(pg, "horde")
        redo = '[data-act="sheet"][data-type="resetspawn"]'
        check("Redo spawn is disabled when nothing has been rolled", pg.locator(redo).is_disabled())
        zr = ev(pg, "state.zones[0].id")
        pg.select_option(f'select[data-z="{zr}"][data-i="0"]', "4")
        pg.select_option(f'select[data-z="{zr}"][data-i="1"]', "3")
        check("Redo spawn is enabled once a die is set", not pg.locator(redo).is_disabled())
        pg.click('.slot .opt >> nth=0 >> [data-act="pick"]')
        ev(pg, "mutate(s => { s.horde.push({uid: s.uid++, zone: 'old', round: 9, raw: 'Monolith', baseKey: 'monolith', need: {monolith: 1}}); s.zones.push(newZone(s, true)); s.manualMod = 2; })")
        check("setup: one unit spawned now, one from an earlier round, one extra zone", ev(pg, "state.horde.length") == 2 and ev(pg, "state.zones.length") == 3)
        pg.click(redo)
        check("Redo spawn asks for confirmation and says how many units go", "Redo this round's spawn?" in pg.inner_text(".sheet") and "1 Horde unit" in pg.inner_text(".sheet"))
        pg.click('.sheet [data-act="sheet-close"]')
        check("Cancel changes nothing", ev(pg, "state.horde.length") == 2 and ev(pg, f"zoneOf(state, '{zr}').dice") is not None)
        pg.click(redo)
        pg.click('[data-act="resetspawn-do"]')
        check("Redo spawn removes only this round's units", ev(pg, "state.horde.map(h => h.round)") == [9])
        check("Redo spawn clears dice and slots in every zone", ev(pg, "state.zones.every(z => z.dice === null && z.slots.length === 0 && z.removed === null && !z.usedFirst)"))
        check("Redo spawn keeps the zone count and the extra zone", ev(pg, "state.zones.length") == 3 and ev(pg, "state.zones.filter(z => z.extra).length") == 1)
        check("Redo spawn keeps the manual modifier and logs it", ev(pg, "state.manualMod") == 2 and "spawn reset" in ev(pg, "state.log[0].text"))
        check("a fresh zone can be rolled again", pg.locator('[data-act="rollzone"]').count() == 3)
        pg.click('[data-act="undo"]')
        check("undo brings the spawn back", ev(pg, "state.horde.length") == 2 and ev(pg, f"zoneOf(state, '{zr}').dice") == [4, 3])

        # ---------- Random pick, roll again, replace ----------
        fresh(pg)
        tab(pg, "horde")
        zq = ev(pg, "state.zones[0].id")
        pg.select_option(f'select[data-z="{zq}"][data-i="0"]', "4")
        pg.select_option(f'select[data-z="{zq}"][data-i="1"]', "3")
        sel = f'[data-z="{zq}"][data-s="1"]'
        pg.click(f'[data-act="random"]{sel}')
        d1 = ev(pg, f"zoneOf(state, '{zq}').slots[0].draft")
        check("Random pick shows a draft and spawns nothing yet", bool(d1) and ev(pg, "state.horde.length") == 0 and pg.locator(".draft").count() == 1)
        check("the draft is one of the possible [7-9] options", d1 in ev(pg, "SPAWN.standard['7-9']"))
        drafts = [d1]
        for _ in range(12):
            pg.click(f'[data-act="random"]{sel}')
            drafts.append(ev(pg, f"zoneOf(state, '{zq}').slots[0].draft"))
        check("rolling again never repeats an option that was turned down", len(set(drafts)) == len(drafts), str(drafts))
        check("turned-down options are remembered", ev(pg, f"zoneOf(state, '{zq}').slots[0].rejected.length") == 12)
        pg.click(f'[data-act="draft-accept"]{sel}')
        check("Spawn this commits the draft and clears it", ev(pg, "state.horde.map(h => h.raw)") == [drafts[-1]] and ev(pg, f"zoneOf(state, '{zq}').slots[0].draft") is None)
        pg.click(f'[data-act="replace"]{sel}')
        d2 = ev(pg, f"zoneOf(state, '{zq}').slots[0].draft")
        check("Replace takes the unit off the table and draws a different one", ev(pg, "state.horde.length") == 0 and bool(d2) and d2 != drafts[-1])
        pg.click(f'[data-act="draft-cancel"]{sel}')
        check("Back to ranked options clears the draft", ev(pg, f"zoneOf(state, '{zq}').slots[0].draft") is None and pg.locator(".slot .opt").count() == 3)
        pg.click(f'[data-act="random"]{sel}')
        pg.click(f'[data-act="draft-accept"]{sel}')
        pg.click('[data-act="sheet"][data-type="destroy"]')
        pg.click('[data-act="destroy-by"][data-i="-1"]')
        check("no Replace button once the unit was destroyed", pg.locator('[data-act="replace"]').count() == 0)
        exhaust = ev(pg, "(() => { const s = JSON.parse(JSON.stringify(state)); const z = s.zones[0]; z.dice = [1, 2]; z.slots = [{id: 1, bracket: '3-4', filled: null, draft: null, rejected: []}]; const seen = []; let prev = null, ok = true; for (let i = 0; i < 45; i++) { drawRandom(s, z.id, 1); const d = z.slots[0].draft; if (!d || d === prev) ok = false; prev = d; seen.push(d); } return [ok, new Set(seen.slice(0, 19)).size]; })()")
        check("once every option was turned down the list starts over, never the same twice in a row", exhaust == [True, 19], str(exhaust))
        legacy = ev(pg, "(() => { const s = JSON.parse(JSON.stringify(state)); const z = s.zones[0]; z.dice = [4, 3]; z.slots = [{id: 1, bracket: '7-9', filled: null}]; drawRandom(s, z.id, 1); return !!z.slots[0].draft; })()")
        check("a slot saved before random drafts existed still works", legacy is True)
        migrated_slot = ev(pg, "(() => { const copy = JSON.parse(JSON.stringify(state)); copy.zones[0].slots = [{id: 1, bracket: '7-9', filled: null}]; const m = migrate(copy); return [m.zones[0].slots[0].draft, m.zones[0].slots[0].rejected.length]; })()")
        check("migration backfills draft and rejected on old slots", migrated_slot == [None, 0], str(migrated_slot))

        # ---------- Game flow ----------
        fresh(pg)
        ev(pg, PLAIN_DECKS)
        nxt(pg)
        check("Next from setup starts round 1", ev(pg, "state.round === 1 && state.stage === 'start'"))
        stages = []
        for _ in range(11):
            stages.append(ev(pg, "state.stage"))
            nxt(pg)
        stages.append(ev(pg, "state.stage"))
        check("round 1 stage order: Horde first (with its Command phase), then players", stages[:12] == ["start", "h-command", "h-move", "h-shoot", "h-charge", "h-fight", "p-command", "p-move", "p-shoot", "p-charge", "p-fight", "end"])
        nxt(pg)
        check("Next after the last stage begins round 2", ev(pg, "state.round === 2 && state.stage === 'start'"))
        check("tracker shows the round", "Round 2 / 5" in pg.inner_text(".round"), pg.inner_text(".round"))
        check("Back is disabled at the start of round 2 (rounds never rewind)", pg.locator('[data-act="back"]').is_disabled())

        # misery reveals per round and carry-over
        fresh(pg)
        ev(pg, PLAIN_DECKS)
        counts = []
        nxt(pg)
        for r in range(1, 6):
            pg.click('[data-act="roundstart"]')
            counts.append(ev(pg, "state.decks.misery.active.length"))
            check(f"round {r} start also reveals a Secondary", ev(pg, "state.decks.secondary.active.length") == 1)
            while ev(pg, "state.stage") != "end":
                nxt(pg)
            ev(pg, "state.decks.secondary.discard.push(...state.decks.secondary.active); state.decks.secondary.active = []; render()")
            nxt(pg)
        check("Misery cards per round are 0, 1, 1, 1, 3", counts == [0, 1, 1, 1, 3], str(counts))

        fresh(pg)
        ev(pg, PLAIN_DECKS)
        nxt(pg)
        while ev(pg, "state.round") < 5 or ev(pg, "state.stage") != "end":
            nxt(pg)
        nxt(pg)
        check("5 rounds then game over", ev(pg, "state.stage") == "over")
        check("game over disables Next", pg.locator('[data-act="next"]').is_disabled())

        # hard mode: six rounds, round 6 is Horde-only
        fresh(pg)
        tab(pg, "setup")
        pg.click('[data-act="set"][data-k="hard"][data-v="1"]')
        check("hard mode makes 6 rounds", ev(pg, "totalRounds()") == 6)
        ev(pg, PLAIN_DECKS)
        tab(pg, "turn")
        nxt(pg)
        while ev(pg, "state.round") < 6:
            nxt(pg)
        check("round 6 has no player phases", ev(pg, "stagesFor(6)") == ["start", "h-command", "h-move", "h-shoot", "h-charge", "h-fight", "end"])
        check("round 6 has no Spawn Rolls", ev(pg, "roundRules(6).spawn") is None)
        tab(pg, "horde")
        check("round 6 zones say the Horde does not spawn", "does not spawn" in pg.inner_text("#main"))
        tab(pg, "turn")
        while ev(pg, "state.stage") != "end":
            nxt(pg)
        nxt(pg)
        check("hard mode ends after round 6", ev(pg, "state.stage") == "over")

        # infinite mode never ends and skips secrets
        fresh(pg)
        tab(pg, "setup")
        pg.click('[data-act="set"][data-k="rounds"][data-v="inf"]')
        check("infinite mode has no round limit", ev(pg, "totalRounds() === Infinity"))
        tab(pg, "players")
        check("infinite mode has no Secret Objectives", "No Secret Objectives" in pg.inner_text("#main"))

        # ---------- Misery effects ----------
        fresh(pg)
        nxt(pg)
        ev(pg, "mutate(s => { s.players[0].sp = 7; s.players[1].sp = 3; activateMisery(s, 'm15'); })")
        check("Bad Investment removes 5 SP (min 0)", ev(pg, "state.players.map(p => p.sp)") == [2, 0])
        ev(pg, "mutate(s => { s.standing.jamming = true; s.standing.fob = true; s.standing.tele = 2; s.standing.wire = 1; activateMisery(s, 'm21'); })")
        check("Bunkers Busted removes fortified markers but keeps Teleporters and Razor Wire", ev(pg, "state.standing") == {"tele": 2, "wire": 1})
        ev(pg, "mutate(s => { activateMisery(s, 'm07'); })")
        check("Unlucky Night switches to 3 dice", ev(pg, "diceNeeded()") == 3)
        tab(pg, "horde")
        check("3 dice selects are shown", pg.locator(f'select.die[data-z="{ev(pg, "state.zones[0].id")}"]').count() == 3)
        zz = ev(pg, "state.zones[0].id")
        for i, v in enumerate(["1", "5", "6"]):
            pg.select_option(f'select[data-z="{zz}"][data-i="{i}"]', v)
        check("3D6 keeps the best two (5+6)", ev(pg, f"spawnResult(zoneOf(state, '{zz}')).unmodified") == 11)
        ev(pg, "mutate(s => { activateMisery(s, 'm13'); })")
        check("Pincer Maneuver adds an extra zone", ev(pg, "state.zones.some(z => z.extra)"))
        ev(pg, PLAIN_DECKS)  # Lamentable Luck draws 2: a random card with its own side effect would change the count
        n_before = ev(pg, "state.decks.misery.active.length")
        ev(pg, "mutate(s => { activateMisery(s, 'm20'); })")
        check("Lamentable Luck reveals 2 more cards", ev(pg, "state.decks.misery.active.length") == n_before + 3)

        # ---------- Shop ----------
        fresh(pg)
        nxt(pg)
        ev(pg, "mutate(s => { s.players[0].sp = 20; s.stage = 'p-command'; })")
        tab(pg, "turn")
        check("shop is shown in the Resupply step", pg.locator('[data-act="buy"]').count() == 26)
        check("shop rows are compact: item text only after tapping the name", "Gain 1 CP." not in pg.inner_text("#main"))
        pg.click('.shoprow [data-act="exp"][data-k="shop:basic"]')
        check("tapping an item's name shows what it does", "Gain 1 CP." in pg.inner_text("#main"))
        check("the Command phase shows its actions before the checklist", ev(pg, "(() => { const panel = document.querySelector('.turnbar'); const income = panel.querySelector('[data-act=\"income\"]'); const firstTick = panel.querySelector('.tick'); return !!(income.compareDocumentPosition(firstTick) & Node.DOCUMENT_POSITION_FOLLOWING); })()"))
        pg.click('[data-act="buy"][data-id="basic"]')
        check("Basic Tactics costs 2 SP and gives 1 CP", ev(pg, "[state.players[0].sp, state.players[0].cp]") == [18, 3])
        ev(pg, "mutate(s => { activateMisery(s, 'm24'); })")
        check("Seller's Market doubles prices", ev(pg, "shopPrice(state, SHOP.air, 0, 0)") == 6)
        ev(pg, "mutate(s => { activateMisery(s, 'm22'); activateMisery(s, 'm23'); })")
        check("Comms Jammed blocks Strike purchases", "Comms Jammed" in ev(pg, "shopCheck(state, SHOP.air, 0, 0)"))
        check("The Mind Killer blocks Tactics purchases", "Mind Killer" in ev(pg, "shopCheck(state, SHOP.basic, 0, 0)"))
        ev(pg, "mutate(s => { s.decks.misery.active = []; s.players[0].sp = 20; })")
        pg.click('[data-act="buy"][data-id="fob"]')
        check("Fortify purchase creates a standing marker", ev(pg, "state.standing.fob") is True)
        check("a unique marker cannot be bought twice", "already exists" in ev(pg, "shopCheck(state, SHOP.fob, 0, 0)"))
        ev(pg, "mutate(s => { s.players[0].sp = 20; })")
        pg.click('[data-act="buy"][data-id="tele"]')
        pg.click('[data-act="buy"][data-id="tele"]')
        pg.click('[data-act="buy"][data-id="tele"]')
        ev(pg, "mutate(s => { s.players[0].sp = 20; })")
        pg.click('[data-act="buy"][data-id="tele"]')
        check("Teleporters stop at 3", ev(pg, "state.standing.tele") == 3)
        ev(pg, "mutate(s => { s.players[0].sp = 30; })")
        check("X purchases need an X", "Enter X" in ev(pg, "shopCheck(state, SHOP.patched, 0, 0)"))
        pg.fill('[data-change="shopx"][data-id="patched"]', "4")
        pg.dispatch_event('[data-change="shopx"][data-id="patched"]', "change")
        pg.click('[data-act="buy"][data-id="patched"]')
        check("Patched Up with X=4 costs 4 SP", ev(pg, "state.players[0].sp") == 26)
        check("once per turn per player is enforced", "already bought" in ev(pg, "shopCheck(state, SHOP.patched, 0, 4)"))
        check("another player can still buy it", "already bought" not in ev(pg, "shopCheck(state, SHOP.patched, 1, 4)"))
        check("not enough SP is explained", "needs" in ev(pg, "shopCheck(state, SHOP.reinforce, 1, 0)"))

        # SP income, FOB and single-player doubling
        ev(pg, "mutate(s => { s.players.forEach(p => { p.sp = 0; p.spRound = 0; }); s.objectives = 2; s.ticks = {}; })")
        pg.click('[data-act="income"]')
        check("SP income is objectives plus FOB", ev(pg, "state.players.map(p => p.sp)") == [3, 3])
        check("income button locks after use", pg.locator('[data-act="income"]').is_disabled())
        check("single-player gains are doubled", ev(pg, "(() => { const s = JSON.parse(JSON.stringify(state)); s.setup.players = 1; s.players.length = 1; s.players[0].sp = 0; gainAll(s, 2); return s.players[0].sp; })()") == 4)
        check("hard mode caps SP per round", ev(pg, "(() => { const s = JSON.parse(JSON.stringify(state)); s.setup.hard = true; s.players[0].sp = 0; s.players[0].spRound = 0; gainSP(s, 0, 20); return [s.players[0].sp, s.players[0].spRound]; })()") == [8, 8])

        # ---------- Secondary Missions ----------
        fresh(pg)
        nxt(pg)
        ev(pg, "mutate(s => { s.decks.secondary.active = ['s03']; s.stage = 'end'; })")
        tab(pg, "turn")
        pg.click('[data-act="sec-fail"][data-id="s03"]')
        check("failing Show No Fear carries +2 Misery and +1 Spawn", ev(pg, "[state.carry.misery, state.carry.spawn]") == [2, 1])
        check("the failed card is discarded", ev(pg, "state.decks.secondary.discard.includes('s03') && state.decks.secondary.active.length === 0"))
        ev(pg, "mutate(s => { s.decks.secondary.active = ['s03']; })")
        pg.click('[data-act="sec-ok"][data-id="s03"]')
        check("succeeding Show No Fear gives every player 3 SP", ev(pg, "state.players.map(p => p.sp)") == [3, 3])
        ev(pg, "mutate(s => { s.decks.secondary.active = ['s02']; })")
        pg.fill('[data-change="secx"][data-id="s02"]', "4")
        pg.dispatch_event('[data-change="secx"][data-id="s02"]', "change")
        pg.click('[data-act="sec-ok"][data-id="s02"]')
        check("Back To Basics pays X+1 SP", ev(pg, "state.players.map(p => p.sp)") == [8, 8])
        ev(pg, "mutate(s => { s.decks.secondary.active = ['s05']; s.players.forEach(p => p.sp = 0); })")
        pg.click('[data-act="sec-ok"][data-id="s05"]')
        check("a saveable card goes to one player, not the discard", ev(pg, "state.saved.length === 1 && !state.decks.secondary.discard.includes('s05')"))
        ev(pg, "mutate(s => { s.decks.secondary.active = ['s09']; })")
        pg.click('[data-act="sec-fail"][data-id="s09"]')
        check("Paint Targets failure resolves Stray Orbital now", ev(pg, "state.decks.misery.active.includes('m06')"))
        ev(pg, "mutate(s => { s.decks.secondary.active = ['s19']; })")
        pg.click('[data-act="sec-fail"][data-id="s19"]')
        check("Tactical Withdrawal failure queues Pincer Maneuver", ev(pg, "state.carry.force.includes('m13')"))
        ev(pg, "mutate(s => { s.decks.secondary.active = ['s06']; })")
        pg.click('[data-act="sec-fail"][data-id="s06"]')
        check("Clear the Evac Zone failure removes Reinforcements Arrive", ev(pg, "state.removedShop.includes('reinforce')") and "removed" in ev(pg, "shopCheck(state, SHOP.reinforce, 0, 0)"))

        # discarding a Secondary Mission without resolving it
        fresh(pg)
        nxt(pg)
        ev(pg, "mutate(s => { s.decks.secondary.active = ['s03']; s.stage = 'p-move'; s.secX.s03 = 5; })")
        tab(pg, "turn")
        check("Turn tab offers Discard Secondary in the middle of a round", pg.locator('[data-act="sec-drop"][data-id="s03"]').count() == 1)
        pg.click('[data-act="sec-drop"][data-id="s03"]')
        check("discarding moves the card to the discard pile", ev(pg, "state.decks.secondary.discard.includes('s03') && state.decks.secondary.active.length === 0"))
        check("discarding gives no reward and no punishment", ev(pg, "[state.carry.misery, state.carry.spawn, state.players.map(p => p.sp)]") == [0, 0, [0, 0]])
        check("discarding forgets the typed X", ev(pg, "'s03' in state.secX") is False)
        ev(pg, "mutate(s => { s.decks.secondary.active = ['s03']; s.stage = 'end'; })")
        check("the end of round shows one discard button per card, not two", pg.locator('[data-act="sec-drop"][data-id="s03"]').count() == 1)
        check("and the card itself only once (in the resolver)", pg.locator('.gcard.secondary').count() == 1)
        ev(pg, "mutate(s => { s.stage = 'p-move'; })")
        tab(pg, "cards")
        pg.click('[data-act="sec-drop"][data-id="s03"]')
        check("Cards tab Discard leaves no active Secondary and reveals nothing", ev(pg, "state.decks.secondary.active.length") == 0)
        ev(pg, "mutate(s => { s.decks.secondary.active = ['s03']; })")
        before = ev(pg, "state.decks.secondary.draw.length")
        pg.click('[data-act="sec-redraw"][data-id="s03"]')
        check("Discard and reveal a new one still reveals exactly one", ev(pg, "state.decks.secondary.active.length") == 1 and ev(pg, "state.decks.secondary.draw.length") == before - 1)
        ev(pg, "undo()")
        check("undo brings back the card replaced by Discard and reveal a new one", ev(pg, "state.decks.secondary.active.includes('s03')"))

        # carry-over becomes the next round's reveal count and Spawn modifier
        fresh(pg)
        nxt(pg)
        ev(pg, PLAIN_DECKS)
        ev(pg, "mutate(s => { s.carry.misery = 2; s.carry.spawn = 1; s.carry.first = 6; s.carry.force = ['m13']; s.stage = 'end'; })")
        nxt(pg)
        check("carried values move into the new round", ev(pg, "[state.rnd.misery, state.rnd.spawn, state.rnd.first, state.carry.misery]") == [2, 1, 6, 0])
        check("round 2 reveal count is base 1 plus carried 2", ev(pg, "miseryCountThisRound()") == 3)
        pg.click('[data-act="roundstart"]')
        check("the forced Pincer Maneuver card is active", ev(pg, "state.decks.misery.active.includes('m13')"))
        check("Pincer's extra zone was added", ev(pg, "state.zones.filter(z => z.extra).length") == 1)
        check("forced card plus 3 revealed", ev(pg, "state.decks.misery.active.length") == 4)
        tab(pg, "horde")
        z_a = ev(pg, "state.zones[0].id")
        pg.select_option(f'select[data-z="{z_a}"][data-i="0"]', "3")
        pg.select_option(f'select[data-z="{z_a}"][data-i="1"]', "3")
        mods = ev(pg, f"spawnResult(zoneOf(state, '{z_a}')).mods.map(m => m.val)")
        check("round 2 modifiers: carried +1 and first-roll +6", sorted(mods) == [1, 6], str(mods))
        z_b = ev(pg, "state.zones[1].id")
        pg.select_option(f'select[data-z="{z_b}"][data-i="0"]', "3")
        pg.select_option(f'select[data-z="{z_b}"][data-i="1"]', "3")
        mods_b = ev(pg, f"spawnResult(zoneOf(state, '{z_b}')).mods.map(m => m.val)")
        check("only the first zone to roll gets the first-roll bonus", mods_b == [1], str(mods_b))

        # ---------- Secret Objectives stay secret ----------
        fresh(pg)
        tab(pg, "turn")
        pg.click('[data-act="deal"]')
        check("each player is dealt 2 cards", ev(pg, "state.players.every(p => p.secret.choices.length === 2)"))
        check("setup says who still has to keep an objective", "2 players still have to keep a Secret Objective" in pg.inner_text("#main"))
        names = ev(pg, "SECRET.map(c => c.name)")
        tab(pg, "players")
        text = pg.inner_text("#main")
        check("dealt objectives are hidden by default", not any(n in text for n in names))
        pg.click('[data-act="peek"][data-i="0"]')
        text = pg.inner_text("#main")
        check("peeking shows only that player's cards", sum(1 for n in names if n in text) == 2)
        pg.click('[data-act="keep"][data-i="0"] >> nth=0')
        check("keeping one returns the other to the deck", ev(pg, "state.players[0].secret.kept !== null && state.players[0].secret.choices.length === 0"))
        deck_size = ev(pg, "state.decks.secret.draw.length")
        check("deck size is 34 minus 3 held cards", deck_size == 34 - 3, str(deck_size))
        text = pg.inner_text("#main")
        check("a kept objective is hidden until revealed", not any(n in text for n in names))
        pg.click('[data-act="sheet"][data-type="reveal"][data-i="0"]')
        pg.click('[data-act="reveal-do"]')
        check("revealing shows the card to everyone", ev(pg, "state.players[0].secret.revealed") and pg.locator(".gcard.secret .nm").count() == 1)
        ev(pg, "mutate(s => { s.players[0].sp = 20; s.players[1].secret.choices = []; s.players[1].secret.kept = 'o01'; })")
        check("A Change of Plans needs an unrevealed objective", "already revealed" in ev(pg, "shopCheck(state, SHOP.plans, 0, 0)"))
        ev(pg, "mutate(s => { s.players[1].sp = 20; })")
        check("A Change of Plans is allowed for player 2", ev(pg, "shopCheck(state, SHOP.plans, 1, 0)") == "")
        ev(pg, "mutate(s => { payFor(s, SHOP.plans, 1, 0); completePurchase(s, SHOP.plans, 1); })")
        check("Change of Plans offers the old card plus 2 new ones", ev(pg, "state.players[1].secret.choices.length") == 3 and ev(pg, "state.players[1].secret.choices.includes('o01')"))
        # eligibility filters
        fresh(pg)
        ev(pg, "mutate(s => { s.setup.excludeTraitor = true; s.decks.secret = buildDecks(s).secret; })")
        check("removing Traitor objectives shrinks the deck", ev(pg, "state.decks.secret.draw.length") == ev(pg, "SECRET.filter(c => !c.tags.includes('Traitor')).length"))
        ev(pg, "mutate(s => { s.setup.excludeTraitor = false; s.setup.players = 1; syncPlayers(s); s.decks.secret = buildDecks(s).secret; })")
        check("single player drops Multiplayer objectives", ev(pg, "state.decks.secret.draw.every(id => !OBJ[id].tags.includes('Multiplayer'))"))

        # ---------- Standing effects show in the right phase ----------
        fresh(pg)
        nxt(pg)
        ev(pg, "mutate(s => { s.standing.warp = true; s.standing.shield = true; s.stage = 'p-fight'; })")
        tab(pg, "turn")
        check("Warp-Relic Outpost is reminded in the Players' Fight phase", "Warp-Relic Outpost" in pg.inner_text("#main"))
        ev(pg, "mutate(s => { s.stage = 'p-move'; })")
        check("and not in the Movement phase", "Warp-Relic Outpost:" not in pg.inner_text("#main"))
        ev(pg, "mutate(s => { s.stage = 'h-shoot'; })")
        check("Shield Generator is reminded in the Horde Shooting phase", "Shield Generator" in pg.inner_text("#main"))
        pg.click('[data-act="unstand"][data-k="warp"]')
        check("a marker can be removed", ev(pg, "state.standing.warp") is None)
        ev(pg, "mutate(s => { s.standing.jamming = true; s.stage = 'setup'; s.round = 0; })")
        tab(pg, "horde")
        zj = ev(pg, "state.zones[0].id")
        pg.select_option(f'select[data-z="{zj}"][data-i="0"]', "4")
        pg.select_option(f'select[data-z="{zj}"][data-i="1"]', "4")
        check("Jamming Station subtracts 1 from Spawn Rolls", ev(pg, f"spawnResult(zoneOf(state, '{zj}')).total") == 7)

        # ---------- Turn tab content ----------
        fresh(pg)
        nxt(pg)
        ev(pg, "mutate(s => { s.stage = 'h-move'; })")
        tab(pg, "turn")
        check("Horde movement rules are shown", "closest visible enemy" in pg.inner_text("#main"))
        ev(pg, "mutate(s => { s.stage = 'p-shoot'; })")
        check("Necron faction rule (and no Reanimation Protocols) is reminded when players shoot", "We're So Back" in pg.inner_text("#main") and "no Reanimation Protocols" in pg.inner_text("#main"))
        ev(pg, "mutate(s => { s.stage = 'h-move'; })")
        pg.click(".tick >> nth=0")
        check("steps can be ticked", ev(pg, "Object.values(state.ticks).some(Boolean)"))

        # ---------- Undo ----------
        fresh(pg)
        nxt(pg)
        nxt(pg)
        pg.click('[data-act="undo"]')
        check("undo reverts the last Next", ev(pg, "state.stage") == "start")

        # ---------- Persistence and migration ----------
        fresh(pg)
        nxt(pg)
        nxt(pg)
        ev(pg, "mutate(s => { s.players[0].name = 'Saved'; s.collection.immortals = 12; })")
        pg.reload()
        pg.wait_for_selector("#tracker .tracker")
        check("game survives a reload", ev(pg, "state.stage === 'h-command' && state.players[0].name === 'Saved' && state.collection.immortals === 12"))
        ev(pg, "mutate(s => { s.horde.push({ uid: s.uid++, zone: 'old', round: 1, raw: 'Lychguard (10)', baseKey: 'lychguard', need: { lychguard: 10 } }); })")
        old = ev(pg, "(() => { const copy = JSON.parse(localStorage.getItem('%s')); ['saved', 'rnd', 'carry', 'removedShop', 'bought', 'secX', 'standing', 'buyer', 'secretDealt', 'destroyed', 'secAt', 'buys', 'secStats'].forEach(k => delete copy[k]); copy.players.forEach(p => { delete p.spRound; delete p.lzUsed; delete p.secret; }); copy.zones.forEach(z => delete z.cleared); copy.horde.forEach(h => { delete h.bracket; delete h.zoneNo; }); return JSON.stringify(copy); })()" % KEY)
        pg.evaluate("v => localStorage.setItem('%s', v)" % KEY, old)
        pg.reload()
        pg.wait_for_selector("#tracker .tracker")
        migrated = ev(pg, "[Array.isArray(state.saved), state.rnd.misery, state.carry.force.length, typeof state.standing, state.players[0].secret.kept, state.players[0].spRound, state.destroyed.length, state.buys.length, state.secStats.won, state.zones[0].cleared, state.horde[0].bracket, state.horde[0].zoneNo]")
        check("a save without the newest fields migrates", migrated == [True, 0, 0, "object", None, 0, 0, 0, 0, None, "5-6", None], str(migrated))
        pg.evaluate("localStorage.setItem('%s', '{broken json')" % KEY)
        pg.reload()
        pg.wait_for_selector("#tracker .tracker")
        check("a corrupt save starts a fresh game", ev(pg, "state.stage") == "setup")
        tab(pg, "setup")
        pg.click('[data-act="sheet"][data-type="newgame"]')
        ev(pg, "state.players[0].name = 'Keep'; state.collection.immortals = 3; render()")
        pg.click('[data-act="newgame-do"]')
        check("new game keeps the collection but resets the table", ev(pg, "state.collection.immortals === 3 && state.stage === 'setup' && state.horde.length === 0"))

        # ---------- Theme ----------
        tab(pg, "setup")
        pg.click('[data-act="theme"][data-v="dark"]')
        check("dark theme sets the attribute", ev(pg, "document.documentElement.getAttribute('data-theme')") == "dark")
        pg.click('[data-act="theme"][data-v="auto"]')
        check("auto theme removes it", ev(pg, "document.documentElement.getAttribute('data-theme')") is None)

        # ---------- Horde unit rules (datasheets + rules section 5) ----------
        fresh(pg)
        prof = ev(pg, """(() => { const f = k => { const p = hordeProfile(k); return { charges: p.charges, heavy: p.heavy.length > 0, ds: p.deepStrike, fnp: p.factionRule, tgt: p.targeting.length, ignored: p.ignored, warlord: p.warlordOk, scouts: p.scouts }; };
          return { deathmarks: f('deathmarks'), lychguard: f('lychguard'), warriors: f('necron warriors'), lokhust: f('lokhust destroyers'), shard: f("c'tan shard of the deceiver"), overlord: f('overlord'), king: f('the silent king'), blades: f('tomb blades') }; })()""")
        check("Deathmarks: Deep Strike, [HEAVY], [PRECISION] targeting, FNP 5+, no charge", prof["deathmarks"]["ds"] and prof["deathmarks"]["heavy"] and prof["deathmarks"]["tgt"] == 1 and prof["deathmarks"]["fnp"] is True and not prof["deathmarks"]["charges"], str(prof["deathmarks"]))
        check("Lychguard charge (warscythe beats a close combat weapon)", prof["lychguard"]["charges"])
        check("Necron Warriors do not charge and ignore abilities that need Reanimation Protocols", not prof["warriors"]["charges"] and prof["warriors"]["ignored"] == ["Their Number is Legion"])
        check("We're So Back skips MOUNTED units and CHARACTERs", prof["lokhust"]["fnp"] is False and prof["overlord"]["fnp"] is False)
        check("a C'tan Shard can never be the Warlord, an Overlord can", not prof["shard"]["warlord"] and prof["overlord"]["warlord"])
        check("The Silent King does not charge (2 of 3 models only have armoured bulk)", not prof["king"]["charges"])
        check("Tomb Blades have Scouts 9\"", prof["blades"]["scouts"] == '9"')
        check("Standard sheet + Leader lists the leaders that can attach", ev(pg, "attachOptions('immortals', 'leader')") == ["Imotekh the Stormlord", "Overlord", "Overlord with Translocation Shroud", "Royal Warden", "Trazyn the Infinite"])
        check("Standard sheet + Support lists the Crypteks that can attach", "Technomancer" in ev(pg, "attachOptions('canoptek wraiths', 'support')"))
        check("Horde rule texts: Command phase, battle-shock, no Reanimation Protocols", "battle-shock" in ev(pg, "STEP_ITEMS['h-command'].join(' ')").lower() and "Reanimation Protocols" in ev(pg, "STEP_ITEMS['h-command'].join(' ')"))
        n_sheets = ev(pg, "(() => { let n = 0; for (const sh of ['standard', 'detailed']) for (const b of BRACKET_KEYS) for (const raw of SPAWN[sh][b]) { if (renderUnitSheet(raw).includes('Horde rules')) n++; } return n; })()")
        check("every spawn-table entry has a unit sheet with Horde rules", n_sheets == ev(pg, "BRACKET_KEYS.reduce((t, b) => t + SPAWN.standard[b].length + SPAWN.detailed[b].length, 0)"))

        # Warlord, roster chips and the unit sheet
        ev(pg, """mutate(s => { const z = s.zones;
          z[0].dice = [6, 6]; rebuildSlots(z[0], s); pickUnit(s, z[0].id, 1, "C'tan Shard Of The Deceiver");
          z[1].dice = [3, 3]; rebuildSlots(z[1], s); pickUnit(s, z[1].id, 1, 'Immortals (5) + Leader'); })""")
        check("the first CHARACTER that may be Warlord becomes the Horde Warlord", ev(pg, "hordeWarlord().name") == "the Leader with Immortals")
        tab(pg, "horde")
        check("the roster marks the Warlord", "Warlord: the Leader with Immortals" in pg.inner_text("#main"))
        pg.click('.rost .linkbtn >> nth=0')
        sheet_text = pg.inner_text(".sheet")
        check("tapping a unit opens its datasheet and Horde rules", "Horde rules" in sheet_text and "Cosmic insanity" in sheet_text and "can never be the Warlord" in sheet_text)
        pg.click('.sheet [data-act="sheet-close"] >> nth=0')
        check("the unit sheet closes", pg.locator(".sheet").count() == 0)
        uid_imm = ev(pg, "state.horde[1].uid")
        ev(pg, f"mutate(s => destroyUnit(s, {uid_imm}, 0))")
        check("a destroyed Warlord stays the Warlord (it does not pass on)", ev(pg, "[hordeWarlord().name, hordeWarlord().alive]") == ["the Leader with Immortals", False])

        # Clear Spawn Zone (rules 4 step 2) with a real unit, Deep Strike reserves, phase panel
        ev(pg, "mutate(s => { startGame(s); s.stage = 'end'; })")
        nxt(pg)
        tab(pg, "horde")
        zc = ev(pg, "state.zones[0].id")
        uid_shard = ev(pg, "state.horde[0].uid")
        options = pg.eval_on_selector_all(f'select[data-change="removed"][data-z="{zc}"] option', "els => els.map(e => e.value)")
        check("the clear step lists Horde units from earlier rounds", f"u:{uid_shard}" in options and "b:3-4" in options)
        pg.select_option(f'select[data-change="removed"][data-z="{zc}"]', f"u:{uid_shard}")
        check("clearing a unit destroys it without SP and adds its bracket minimum", ev(pg, "state.horde.length") == 0 and ev(pg, f"zoneOf(state, '{zc}').removed") == "10+" and ev(pg, "state.players.map(p => p.sp)") == [1, 0] and ev(pg, "state.destroyed.some(d => d.by === 'zone')"))
        pg.select_option(f'select[data-change="removed"][data-z="{zc}"]', "")
        check("choosing no unit puts the cleared unit back", ev(pg, "state.horde.length") == 1 and not ev(pg, "state.destroyed.some(d => d.by === 'zone')"))
        pg.select_option(f'select[data-change="removed"][data-z="{zc}"]', "b:7-9")
        check("a unit the app does not know can be cleared by its bracket (+7)", ev(pg, f"[zoneOf(state, '{zc}').removed, state.horde.length]") == ["7-9", 1])
        pg.select_option(f'select[data-change="removed"][data-z="{zc}"]', "")
        ev(pg, f"mutate(s => {{ const z = zoneOf(s, '{zc}'); z.dice = [3, 3]; rebuildSlots(z, s); pickUnit(s, z.id, 1, 'Deathmarks (10)'); }})")
        dm = ev(pg, "state.horde.find(h => h.baseKey === 'deathmarks').uid")
        check("round 2: a spawned Deep Strike unit waits in reserves", ev(pg, f"inReserves(state.horde.find(h => h.uid === {dm}))") and "In reserves" in pg.inner_text("#main"))
        ev(pg, "mutate(s => { s.stage = 'h-shoot'; })")
        check("after the Horde Movement phase it is on the table", not ev(pg, f"inReserves(state.horde.find(h => h.uid === {dm}))"))
        check("and never in reserves once the game is over", not ev(pg, f"(() => {{ const s = JSON.parse(JSON.stringify(state)); s.stage = 'over'; return inReserves(s.horde.find(h => h.uid === {dm}), s); }})()"))
        ev(pg, "mutate(s => { s.stage = 'h-charge'; })")
        tab(pg, "turn")
        panel = pg.inner_text("#main")
        check("the Turn tab tells per unit who charges", "Horde units this phase" in panel and "Does not charge" in panel and "Charges the closest legal target" in panel)
        ev(pg, "mutate(s => { s.stage = 'h-shoot'; })")
        check("the Shooting phase panel shows [PRECISION] targeting", "Leader or Support model first" in pg.inner_text("#main"))

        # ---------- Round start runs once ----------
        fresh(pg)
        ev(pg, PLAIN_DECKS)
        nxt(pg)
        pg.click('[data-act="roundstart"]')
        check("Run steps 1 to 3 is disabled once done", pg.locator('[data-act="roundstart"]').is_disabled() and pg.locator('[data-act="r-secondary"]').is_disabled())
        ev(pg, "mutate(runRoundStart)")
        check("running the round start again reveals nothing more", ev(pg, "state.decks.secondary.active.length") == 1)

        # ---------- Rewards that go to a chosen player, saved cards in use ----------
        fresh(pg)
        nxt(pg)
        ev(pg, "mutate(s => { s.decks.secondary.active = ['s19']; s.stage = 'end'; })")
        tab(pg, "turn")
        pg.click('[data-act="sec-ok"][data-id="s19"]')
        check("Tactical Withdrawal asks which player completed it", "which player" in pg.inner_text(".sheet").lower())
        pg.click('[data-act="secwho-do"][data-i="1"]')
        check("that player saves the card", ev(pg, "state.saved.map(sv => [sv.id, sv.owner])") == [["s19", 1]])
        tab(pg, "players")
        pg.click('[data-act="sheet"][data-type="perk"]')
        pg.click('[data-act="perk-free"][data-item="tele"]')
        check("first free Teleporter: placed for no SP, card stays with 1 use left", ev(pg, "[state.standing.tele, state.saved[0].left, state.players[1].sp]") == [1, 1, 1])
        pg.click('[data-act="perk-free"][data-item="tele"]')
        check("second free Teleporter: placed, card discarded", ev(pg, "[state.standing.tele, state.saved.length, state.decks.secondary.discard.includes('s19')]") == [2, 0, True])

        ev(pg, "mutate(s => { s.saved = [{ id: 's01', owner: 0 }]; s.players[0].sp = 0; })")
        pg.click('[data-act="sheet"][data-type="perk"]')
        pg.click('[data-act="perk-free"][data-item="basic"]')
        check("Secure Drop Zones card: a free Tactics purchase (Basic Tactics gives 1 CP, costs nothing)", ev(pg, "[state.players[0].cp, state.players[0].sp, state.saved.length]") == [3, 0, 0])

        ev(pg, "mutate(s => { s.saved = [{ id: 's10', owner: 0 }]; s.decks.misery.active = ['m02', 'm03']; })")
        pg.click('[data-act="sheet"][data-type="perk"]')
        pg.click('[data-act="perk-cancel"][data-mid="m02"]')
        check("Study Behaviors card cancels a revealed Misery card", ev(pg, "[state.decks.misery.active, state.decks.misery.discard.includes('m02')]") == [["m03"], True])

        ev(pg, "mutate(s => { s.saved = [{ id: 's14', owner: 0 }]; s.decks.misery.active = []; s.players[0].sp = 10; })")
        pg.click('[data-act="sheet"][data-type="perk"]')
        pg.click('[data-act="perk-discount"]')
        check("Marching on Stomachs card: Reinforcements Arrive for 7 SP", ev(pg, "state.players[0].sp") == 3)

        ev(pg, "mutate(s => { s.decks.secondary.active = ['s08']; s.stage = 'end'; s.players.forEach(p => { p.sp = 0; p.spRound = 0; }); })")
        tab(pg, "turn")
        pg.click('[data-act="sec-ok"][data-id="s08"]')
        pg.click('[data-act="secwho-do"][data-i="-1"]')
        check("Dragon Slayer with nobody triggering it gives 2 SP each", ev(pg, "state.players.map(p => p.sp)") == [2, 2] and ev(pg, "state.saved.length") == 0)
        ev(pg, "mutate(s => { s.decks.secondary.active = ['s08']; })")
        pg.click('[data-act="sec-ok"][data-id="s08"]')
        pg.click('[data-act="secwho-do"][data-i="0"]')
        check("Dragon Slayer triggered by a player gives that player a free Field Promotion", ev(pg, "state.saved.map(sv => [sv.owner, sv.perk.item])") == [[0, "promo"]])

        # X limits and counts
        ev(pg, "mutate(s => { s.decks.secondary.active = ['s02']; s.secAt.s02 = s.uid++; s.saved = []; })")
        pg.click('[data-act="sec-ok"][data-id="s02"]')
        check("Back To Basics cannot succeed with X = 0", ev(pg, "state.decks.secondary.active") == ["s02"])
        ev(pg, "mutate(s => { s.horde.push({ uid: s.uid++, zone: 'x', round: s.round, raw: 'Immortals (5)', baseKey: 'immortals', need: { immortals: 5 }, bracket: '3-4' }); destroyUnit(s, s.horde[s.horde.length - 1].uid, 0); })")
        check("Back To Basics X is counted from destroyed units", ev(pg, "missionX(state, 's02')") == 1 and "App count: 1" in pg.inner_text("#main"))
        ev(pg, "mutate(s => { s.decks.secondary.active = ['s11']; s.secAt.s11 = s.uid++; s.players[0].sp = 20; payFor(s, SHOP.artillery, 0, 0); })")
        check("Use It Or Lose It X is the SP spent since it was revealed", ev(pg, "autoX(state, 's11')") == 8)

        # Establish Orbital Comms runs A Change of Plans without showing secrets
        fresh(pg)
        ev(pg, "mutate(s => { dealSecrets(s); s.players.forEach((p, i) => keepSecret(s, i, p.secret.choices[0])); startGame(s); s.decks.secondary.active = ['s04']; s.stage = 'end'; })")
        kept_before = ev(pg, "state.players.map(p => p.secret.kept)")
        tab(pg, "turn")
        pg.click('[data-act="sec-fail"][data-id="s04"]')
        names = ev(pg, "SECRET.map(c => c.name)")
        check("Establish Orbital Comms failure picks new objectives at random, unseen", ev(pg, "state.players.every(p => p.secret.kept && !p.secret.choices.length)") and not any(n in pg.inner_text("body") for n in names))
        check("the deck still holds every other objective", ev(pg, "state.decks.secret.draw.length") == 34 - 2, str(kept_before))
        ev(pg, "mutate(s => { s.decks.secondary.active = ['s04']; })")
        pg.click('[data-act="sec-ok"][data-id="s04"]')
        check("Establish Orbital Comms success offers each player a choice of 3", ev(pg, "state.players.every(p => p.secret.choices.length === 3)"))

        # Calling Shots after the Horde Movement phase, Advanced Tactics
        fresh(pg)
        nxt(pg)
        ev(pg, "mutate(s => { s.stage = 'p-command'; s.decks.secondary.draw = ['s03', 's18']; s.decks.secondary.active = []; revealSecondary(s); })")
        check("Calling Shots revealed after the Horde Movement phase is shuffled back", ev(pg, "state.decks.secondary.active") == ["s03"])
        ev(pg, "mutate(s => { s.players[0].sp = 20; s.decks.secondary.draw = ['s05', 's07']; })")
        pg.click('[data-act="buy"][data-id="advanced"]')
        check("Advanced Tactics with one active mission replaces it", ev(pg, "state.decks.secondary.active.length === 1 && !state.decks.secondary.active.includes('s03')"))
        ev(pg, "mutate(s => { s.decks.secondary.active.push('s12'); s.bought = {}; s.decks.secondary.draw = ['s20', 's21']; })")
        pg.click('[data-act="buy"][data-id="advanced"]')
        check("with two active missions it asks which one", "replace which" in pg.inner_text(".sheet").lower())
        pg.click('.sheet [data-act="sec-redraw"][data-id="s12"]')
        check("the chosen one is replaced", ev(pg, "state.decks.secondary.active.length === 2 && !state.decks.secondary.active.includes('s12')"))

        # Secret Objectives are taken back when the player count changes during setup
        fresh(pg)
        pg.click('[data-act="deal"]')
        tab(pg, "setup")
        pg.click('[data-act="set"][data-k="players"][data-v="3"]')
        check("changing players after dealing takes the objectives back", ev(pg, "!state.secretDealt && state.players.every(p => !p.secret.choices.length) && state.decks.secret.draw.length === 34"))
        pg.click('[data-act="exp"][data-k="coll"]')
        check("the collection editor says which unit sizes the tables use", "tables use 5 or 10" in pg.inner_text("#main"))

        # ---------- Layout: no sideways scrolling at phone sizes ----------
        for width, height in ((390, 844), (360, 740)):
            pg.set_viewport_size({"width": width, "height": height})
            fresh(pg)
            ev(pg, """mutate(s => { const z = s.zones;
              z[0].dice = [4, 3]; rebuildSlots(z[0], s); pickUnit(s, z[0].id, 1, 'Ghost Ark + Transported Unit');
              z[1].dice = [3, 3]; rebuildSlots(z[1], s); pickUnit(s, z[1].id, 1, 'Deathmarks (10)');
              startGame(s); s.stage = 'p-command'; activateMisery(s, 'm07'); revealSecondary(s); dealSecrets(s); s.players[0].sp = 9; s.saved = [{ id: 's01', owner: 0 }]; })""")
            for name in ("turn", "horde", "cards", "players", "setup"):
                tab(pg, name)
                if name == "cards":
                    pg.click('[data-act="exp"][data-k="ref-m"]')
                    pg.click('[data-act="exp"][data-k="ref-s"]')
                if name == "setup":
                    pg.click('[data-act="exp"][data-k="coll"]')
                overflow = ev(pg, "document.documentElement.scrollWidth - document.documentElement.clientWidth")
                check(f"{width}px {name} tab has no horizontal scroll", overflow <= 0, f"overflow {overflow}px")
            for raw in ("Immortals (10) + Overlord with Translocation Shroud + Chronomancer", "The Silent King (3)"):
                pg.evaluate("raw => { ui.sheet = { type: 'unit', raw }; render(); }", raw)
                overflow = ev(pg, "(() => { const el = document.querySelector('.sheet'); return el.scrollWidth - el.clientWidth; })()")
                check(f"{width}px unit sheet for {raw} has no horizontal scroll", overflow <= 0, f"overflow {overflow}px")
            pg.evaluate("() => { ui.sheet = { type: 'perk', idx: 0 }; render(); }")
            overflow = ev(pg, "(() => { const el = document.querySelector('.sheet'); return el.scrollWidth - el.clientWidth; })()")
            check(f"{width}px saved-card sheet has no horizontal scroll", overflow <= 0, f"overflow {overflow}px")
            pg.evaluate("() => { ui.sheet = null; render(); }")
        pg.set_viewport_size({"width": 390, "height": 844})

        # ---------- Hygiene ----------
        check("no console or page errors", not errors, "; ".join(errors[:3]))
        check("no outside requests besides blocked Google Fonts", not external, ", ".join(external[:3]))
        browser.close()
    print(f"\nAll {passed} checks passed.")


if __name__ == "__main__":
    main()
