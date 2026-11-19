#!/usr/bin/env python3
"""Builds the Horde's spawn tables and unit data from the source files in reference/<faction>/ and embeds them in index.html.

    python3 tools/embed_data.py            # the faction in DEFAULT_FACTION
    python3 tools/embed_data.py necrons

The sources are other people's data and are never committed: reference/ is git-ignored. When a source file is missing,
the script prints the command that downloads it. Download them yourself (see README.md, "Updating the data"); this script
needs no network.

Reads   reference/<faction>/spawn-standard.csv     DigitalBeef's spawn brackets, Standard tab
        reference/<faction>/spawn-detailed.csv     DigitalBeef's spawn brackets, Detailed tab
        reference/<faction>/wahapedia-datasheets.html   Wahapedia's 11th edition datasheets page for the faction
Writes  the blocks between /*SPAWN_DATA_START*/ ... /*SPAWN_DATA_END*/ and /*UNIT_DATA_START*/ ... /*UNIT_DATA_END*/
        in index.html.

From the datasheets it keeps only the units that appear in the spawn tables, and only what the Horde needs: stat lines,
weapon profiles and keywords, unit keywords, core abilities, the names of datasheet abilities with tags we derive from
them (the ability text itself is not copied), default loadouts with model counts, Leader/Support attach lists, transport
capacity, the damaged range and Warlord notes. Exits non-zero when a unit from the spawn tables has no datasheet.
tests/test_app.py imports build() to check the embedded data against the sources when they are present.
"""
import csv
import html
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SHEET_ID = "1LXfBsLU7fAgLwlA4bTLZSH1JyBc4K_8yqoL77HHGuw4"
# One entry per Horde faction. Sheet tab ids: see CLAUDE.md, "Adding a faction".
FACTIONS = {
    "necrons": {"name": "Necrons", "gid_standard": "2043610988", "gid_detailed": "216374006", "wahapedia": "necrons"},
}
DEFAULT_FACTION = "necrons"
BRACKET_KEYS = ["3-4", "5-6", "7-9", "10+", "13+"]
PLACEHOLDERS = {"leader", "support", "transported unit"}
STAT_NAMES = ["M", "T", "SV", "W", "LD", "OC"]
SECTION_HEADERS = {"CORE ABILITIES", "ARMY RULES", "ABILITIES", "WARGEAR OPTIONS", "WARGEAR ABILITIES", "UNIT COMPOSITION",
                   "LEADER", "SUPPORT", "TRANSPORT", "DEPLOYMENT", "FORTIFICATION", "KEYWORDS"}
BLOCK_TAGS = {"p", "div", "br", "tr", "li", "table", "td", "th", "ul"}
SPAWN_MARKERS = ("/*SPAWN_DATA_START*/", "/*SPAWN_DATA_END*/")
UNIT_MARKERS = ("/*UNIT_DATA_START*/", "/*UNIT_DATA_END*/")


def source_paths(faction):
    folder = ROOT / "reference" / faction
    return {"standard": folder / "spawn-standard.csv", "detailed": folder / "spawn-detailed.csv", "datasheets": folder / "wahapedia-datasheets.html"}


def download_commands(faction):
    config, paths = FACTIONS[faction], source_paths(faction)
    rel = {k: p.relative_to(ROOT) for k, p in paths.items()}
    sheet = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid="
    return [
        f"mkdir -p reference/{faction}",
        f'curl -L "{sheet}{config["gid_standard"]}" -o {rel["standard"]}',
        f'curl -L "{sheet}{config["gid_detailed"]}" -o {rel["detailed"]}',
        f'curl -L "https://wahapedia.ru/wh40k11ed/factions/{config["wahapedia"]}/datasheets.html" -o {rel["datasheets"]}',
    ]


def norm(name):
    """Same key the app uses: lower case, straight apostrophes, single spaces."""
    return " ".join(name.replace("’", "'").split()).lower()


# ---------------------------------------------------------------- spawn tables (DigitalBeef CSV)

def read_sheet(path):
    with open(path, newline="", encoding="utf-8") as handle:
        rows = list(csv.reader(handle))
    updated, header_row = "", None
    for index, row in enumerate(rows):
        if len(row) > 4 and row[1].strip() == "Last Updated:":
            updated = row[4].strip()
        if [cell.strip() for cell in row[1:6]] == [f"[{key}]" for key in BRACKET_KEYS]:
            header_row = index
            break
    if header_row is None:
        sys.exit(f"{path}: bracket header row ([3-4] ... [13+]) not found")
    brackets = {key: [] for key in BRACKET_KEYS}
    for row in rows[header_row + 1:]:
        for column, key in enumerate(BRACKET_KEYS, start=1):
            cell = row[column].strip() if len(row) > column else ""
            if cell:
                brackets[key].append(cell)
    return updated, brackets


def unit_names(tables):
    names = set()
    for brackets in tables:
        for cells in brackets.values():
            for cell in cells:
                for part in re.split(r"\s+\+\s+", cell):
                    part = re.sub(r"\s*\(\d+\)$", "", part.strip())
                    if part and part.lower() not in PLACEHOLDERS:
                        names.add(norm(part))
    return names


# ---------------------------------------------------------------- datasheets (Wahapedia HTML)

def strip_tags(fragment):
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", fragment)).split())


class TextLines(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts, self.skip = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.skip += 1
        if tag in BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self.skip -= 1
        if tag in BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)


def text_lines(fragment):
    parser = TextLines()
    parser.feed(fragment)
    return [line for line in (" ".join(raw.split()) for raw in "".join(parser.parts).split("\n")) if line]


def parse_weapons(block):
    """Ranged and melee weapon rows: name, keywords (one per kwbw span), range, A, BS/WS, S, AP, D."""
    ranged_at = [m.start() for m in re.finditer(r">RANGED WEAPONS<", block)]
    melee_at = [m.start() for m in re.finditer(r">MELEE WEAPONS<", block)]
    out = {"ranged": [], "melee": []}
    for row in re.finditer(r'<tr class="dsWeaponRow">(.*?)</tr>', block, re.S):
        cells = re.findall(r"<td[^>]*>(.*?)</td>", row.group(1), re.S)
        name_cell = next((c for c in cells if "dsWeaponName" in c), "")
        name = strip_tags(re.search(r'<b class="dsWeaponName">(.*?)</b>', name_cell, re.S).group(1))
        keywords = [strip_tags(re.sub(r"^[^>]*>", "", part, count=1)).upper() for part in name_cell.split('<span class="kwbw')[1:]]
        values = [strip_tags(v) for v in re.findall(r'<div class="ct pad2626">(.*?)</div>', row.group(1), re.S)]
        if len(values) != 6:
            sys.exit(f"weapon row for {name}: expected 6 values, got {values}")
        last_ranged = max([p for p in ranged_at if p < row.start()], default=-1)
        last_melee = max([p for p in melee_at if p < row.start()], default=-1)
        kind = "melee" if last_melee > last_ranged else "ranged"
        out[kind].append({"n": name, "kw": keywords, "r": values[0], "a": values[1], "sk": values[2], "s": values[3], "ap": values[4], "d": values[5]})
    return out


def parse_profiles(block):
    head = block[: block.find('class="ds2col"')]
    values = [strip_tags(v) for v in re.findall(r'class="dsCharValue[^"]*">(.*?)</div>', head, re.S)]
    models = [re.sub(r"\(.*$", "", strip_tags(m)).strip() for m in re.findall(r'class="dsProfileWrapRight">(.*?)<div', head, re.S)]
    models = [m for m in models if m]
    if len(values) % 6:
        sys.exit(f"stat line with {len(values)} values")
    profiles = []
    for index in range(0, len(values), 6):
        profile = dict(zip(STAT_NAMES, values[index:index + 6]))
        if len(values) > 6:
            profile["model"] = models[index // 6].title() if index // 6 < len(models) else ""
        profiles.append(profile)
    invuln = re.search(r'class="dsCharInvulValue[^"]*">(.*?)</div>', head, re.S)
    return profiles, strip_tags(invuln.group(1)) if invuln else ""


def parse_keywords(block):
    found = re.search(r'class="dsLeftСolKW[^"]*">(.*?)</div>', block, re.S)  # Wahapedia's class name has a Cyrillic С
    if not found:
        return [], ""
    keywords, groups = [], []
    for segment in found.group(1).split('<span class="dsVertLine"></span>'):
        label, _, rest = strip_tags(segment).partition(":")
        words = [w.strip() for w in rest.split(";") if w.strip()]
        keywords += [w for w in words if w not in keywords]
        groups.append((label.replace("KEYWORDS", "").strip(" –-") or "", words))
    detail = " / ".join((label.title() + ": " if label else "") + ", ".join(words) for label, words in groups) if len(groups) > 1 else ""
    return keywords, detail


def ability_tags(text, army_rules):
    """Tags we derive from an ability's text. 'army-rule' and 'stratagem' mean the Horde cannot use it (rules 3.1, 5.1)."""
    tags = []
    if any(rule in text for rule in army_rules):
        tags.append("army-rule")
    if re.search(r"Stratagem|\bCP\b", text):
        tags.append("stratagem")
    if re.search(r"Command phase", text):
        tags.append("command")
    if re.search(r"opponent’s|opponent's", text):
        tags.append("their-turn")
    if re.search(r"\(Aura\)", text):
        tags.append("aura")
    if re.search(r"Once per battle", text, re.I):
        tags.append("once-per-battle")
    return tags


def most_models(comp_line):
    return max(int(n) for n in re.findall(r"\d+", comp_line.split(" ", 1)[0]))


def parse_loadout(line, comp):
    """'Every model is equipped with: a; b.' -> {'n': models carrying it, 'items': ['a', 'b']}.
    'Every Triarchal Menhir is equipped with: ...' counts only the matching models from the composition lines."""
    subject, items = line.split("equipped with:", 1)
    subject = re.sub(r"^(Every|This|Each)\s+", "", subject.replace(" is ", " ").replace(" are ", " ").strip()).strip().lower()
    names = [re.sub(r"\s+", " ", re.sub(r"^[\d\-–]+\s+", "", c)).split(" – ")[0].lower() for c in comp]
    matches = [most_models(c) for c, n in zip(comp, names) if subject.rstrip("s") and subject.rstrip("s") in n]
    count = matches[0] if subject not in ("model", "") and matches else sum(most_models(c) for c in comp) or 1
    cleaned = [re.sub(r"^\d+\s+", "", item.strip().rstrip(".")).lower() for item in items.split(";")]
    return {"n": count, "items": [item for item in cleaned if item]}


def parse_sections(lines):
    """Splits the datasheet text after the weapon tables into sections by their headers."""
    start = next((i for i, line in enumerate(lines) if line in ("CORE ABILITIES", "ARMY RULES", "ABILITIES")), len(lines))
    sections, current = [], None
    for line in lines[start:]:
        is_header = line in SECTION_HEADERS or line.startswith("KEYWORDS") or line.startswith("DAMAGED:") or (
            line.isupper() and len(line) < 40 and not line.startswith("YOUR") and ";" not in line and not re.match(r"^[\d\-–]", line))
        if is_header and not (current and current[0] in ("LEADER", "SUPPORT") and line.isupper() and not line.startswith("KEYWORDS")):
            current = [line, []]
            sections.append(current)
        elif current:
            current[1].append(line)
    return sections


def parse_datasheet(block):
    name = strip_tags(re.search(r'class="dsH2Header"><div>(.*?)</div>', block, re.S).group(1))
    profiles, invuln = parse_profiles(block)
    weapons = parse_weapons(block)
    keywords, keyword_detail = parse_keywords(block)
    unit = {"name": name, "kw": keywords}
    if keyword_detail:
        unit["kwDetail"] = keyword_detail
    unit["profiles"] = profiles
    if invuln:
        unit["inv"] = invuln
    unit["ranged"], unit["melee"] = weapons["ranged"], weapons["melee"]
    unit["core"], unit["abilities"], unit["comp"], unit["loadouts"], army_rules = [], [], [], [], []
    stratagems_at = block.find(">STRATAGEMS<")
    sheet = block[:stratagems_at if stratagems_at > 0 else len(block)]
    sections = parse_sections(text_lines(sheet))
    for header, body in sections:
        if header == "ARMY RULES":
            army_rules = [line for line in body if line]
    for header, body in sections:
        if header == "CORE ABILITIES":
            unit["core"] = [a.strip() for a in ", ".join(body).split(",") if a.strip()]
        elif header == "ABILITIES":
            for line in body:
                found = re.match(r"^([^:]{2,60}):\s*(.*)$", line)
                if found and found.group(1)[0].isupper():
                    unit["abilities"].append({"n": found.group(1), "_text": found.group(2)})
                elif unit["abilities"]:
                    unit["abilities"][-1]["_text"] += " " + line
        elif header == "UNIT COMPOSITION":
            body = body[:next((i for i, line in enumerate(body) if line.startswith("YOUR")), len(body))]
            unit["comp"] = [line for line in body if re.match(r"^\d", line)]
            unit["loadouts"] = [parse_loadout(line, unit["comp"]) for line in body if "equipped with:" in line]
        elif header in ("LEADER", "SUPPORT"):
            unit["leader" if header == "LEADER" else "support"] = [line for line in body if line.isupper()]
        elif header == "TRANSPORT":
            capacity = re.search(r"transport capacity of (.*?)(?:\.|$)", " ".join(body))
            unit["transport"] = capacity.group(1) if capacity else " ".join(body)
        elif header.startswith("DAMAGED:"):
            unit["damaged"] = re.search(r"([\d\-–]+)\s+WOUNDS", header).group(1)
    sheet_text = strip_tags(sheet)
    if re.search(r"cannot be your WARLORD", sheet_text, re.I):
        unit["warlord"] = "never"
    elif re.search(r"must be your Warlord", sheet_text, re.I):
        unit["warlord"] = "must"
    unit["abilities"] = [{"n": a["n"], "tags": ability_tags(a["_text"], army_rules)} for a in unit["abilities"] if not a["n"].lower().startswith("designer")]
    for key in ("core", "abilities", "loadouts", "comp", "ranged", "melee"):
        if not unit[key]:
            del unit[key]
    return unit, army_rules


def read_units(path, wanted, faction):
    page = Path(path).read_text(encoding="utf-8-sig")
    version = re.search(r"App\. [^(<]+\((11th edition[^)]*)\)", page)
    starts = [m.start() for m in re.finditer(r'<div class="dsOuterFrame datasheet', page)] + [len(page)]
    units, army_rules = {}, []
    for begin, end in zip(starts, starts[1:]):
        unit, rules = parse_datasheet(page[begin:end])
        if norm(unit["name"]) in wanted:
            units[norm(unit["name"])] = unit
            army_rules += [r for r in rules if r not in army_rules]
    missing = sorted(wanted - set(units))
    if missing:
        sys.exit("no datasheet for: " + ", ".join(missing))
    return {
        "faction": faction,
        "source": f"Wahapedia, Warhammer 40,000 11th edition, {FACTIONS[faction]['name']} datasheets",
        "version": version.group(1) if version else "",
        "armyRules": army_rules,
        "units": dict(sorted(units.items())),
    }


# ---------------------------------------------------------------- building and embedding

def build(faction):
    """Returns (spawn, units) for a faction from its reference/ files, or exits with the download commands."""
    paths = source_paths(faction)
    missing = [p for p in paths.values() if not p.exists()]
    if missing:
        sys.exit("missing source files:\n  " + "\n  ".join(str(p.relative_to(ROOT)) for p in missing)
                 + "\ndownload them with:\n  " + "\n  ".join(download_commands(faction)))
    standard_updated, standard = read_sheet(paths["standard"])
    detailed_updated, detailed = read_sheet(paths["detailed"])
    if standard_updated != detailed_updated:
        print(f"warning: sheets say different update dates ({standard_updated} vs {detailed_updated})")
    spawn = {"updated": standard_updated, "standard": standard, "detailed": detailed}
    units = read_units(paths["datasheets"], unit_names([standard, detailed]), faction)
    return spawn, units


def format_spawn(data):
    lines = ["{", f'"updated": {json.dumps(data["updated"])},']
    for sheet in ("standard", "detailed"):
        lines.append(f'"{sheet}": {{')
        keys = list(data[sheet].keys())
        for position, key in enumerate(keys):
            comma = "," if position < len(keys) - 1 else ""
            lines.append(f"  {json.dumps(key)}: {json.dumps(data[sheet][key], ensure_ascii=False)}{comma}")
        lines.append("}," if sheet == "standard" else "}")
    lines.append("}")
    return "\n".join(lines)


def format_units(units):
    """One unit per line, so a changed datasheet shows up as a one-line diff."""
    head = {k: v for k, v in units.items() if k != "units"}
    lines = ["{"] + [f"{json.dumps(k)}: {json.dumps(v, ensure_ascii=False)}," for k, v in head.items()] + ['"units": {']
    keys = list(units["units"].keys())
    for position, key in enumerate(keys):
        comma = "," if position < len(keys) - 1 else ""
        lines.append(f"  {json.dumps(key, ensure_ascii=False)}: {json.dumps(units['units'][key], ensure_ascii=False, separators=(',', ':'))}{comma}")
    lines += ["}", "}"]
    return "\n".join(lines)


def replace_block(page, markers, block):
    start, end = markers
    pattern = re.compile(re.escape(start) + r".*?" + re.escape(end), re.S)
    if not pattern.search(page):
        sys.exit(f"markers {start} ... {end} not found in index.html")
    return pattern.sub(lambda _: start + block + end, page, count=1)


def main():
    faction = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_FACTION
    if faction not in FACTIONS:
        sys.exit(f"unknown faction {faction!r}; known: {', '.join(FACTIONS)}")
    spawn, units = build(faction)
    index_path = ROOT / "index.html"
    page = index_path.read_text(encoding="utf-8")
    page = replace_block(page, SPAWN_MARKERS, format_spawn(spawn))
    page = replace_block(page, UNIT_MARKERS, format_units(units))
    index_path.write_text(page, encoding="utf-8")
    print(f"{FACTIONS[faction]['name']}: {len(units['units'])} datasheets ({units['version']}), army rules {units['armyRules']}")
    print(f"Sheet last updated: {spawn['updated']}")
    for sheet in ("standard", "detailed"):
        print(f"  {sheet:9}", {key: len(spawn[sheet][key]) for key in BRACKET_KEYS})


if __name__ == "__main__":
    main()
