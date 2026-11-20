# Horde Mode 40K 11th

**Live:** https://josefkaplan.github.io/horde-mode-40K-11th/

Repository `horde-mode-40K-11th`. The app is titled "Necron Horde Mode": only the Necron Horde for now, more factions later.

Companion app for **40K Horde Mode (11th edition, v0.9)** with a **Necron Horde**. It runs the turn sequence, rolls and ranks the Horde's spawns, tells you what each Horde unit does under the Horde AI rules, and deals the Misery, Secondary and Secret Objective cards. For 1 to 4 players on one phone or laptop. Built for phones. One file, no build.

## What it does

- **Turn:** the whole battle round as a checklist (setup, round start, Horde phases including its Command phase, Players' phases, round end), the Resupply shop, and every active Misery card and Secondary Mission. In each Horde phase a **"Horde units this phase"** panel says what every unit on the table does: who ingresses from reserves, who is slowed by [HEAVY] weapons, who charges and who does not, which guns pick special targets.
- **Horde:** per Spawn Zone, clear the zone (pick the unit still standing in it), roll 2D6 (or type in your dice), add every modifier, get the bracket, then pick from **ranked options** based on your Necron collection. Roll a slot down into two lower units, or take a **random pick** and roll again until you like it (a spawned unit can be **replaced** the same way). **Redo spawn** starts the round's spawn over (units from earlier rounds stay). Tap any unit name for its **unit sheet**: stats, weapons, keywords, the Horde rules that apply to it (Deep Strike reserves, charges or not, We're So Back, Warlord...), and which characters can be its "+ Leader" or "+ Support".
- **Cards:** Misery deck and Secondary Missions with draw, active and discard piles. Failed missions carry Misery cards and Spawn Roll modifiers into the next round by themselves. A Secondary Mission you do not want can be **discarded** without resolving it (Turn and Cards tabs), or discarded and replaced by a new reveal. At the end of the round the app fills in X where it can count it.
- **Players:** CP and SP, Secret Objectives (face down, peek and reveal), saved reward cards you can **use** (free purchases, discounts, cancelling a Misery card), and the Resupply table with Misery restrictions applied.
- **Setup:** 1,000 or 2,000 points, players, 5 rounds or infinite, Hard Mode add-on, Standard or Detailed spawn sheet, your collection.

## Run it locally

Open `index.html` in a browser, or serve the folder the way GitHub Pages does:

```bash
python3 -m http.server 8000 --bind 127.0.0.1
```

Then open http://localhost:8000/. Stop it with Ctrl+C. Before every deploy, run `python3 tests/test_app.py` (see `CLAUDE.md`).

## Updating the data

The spawn brackets (DigitalBeef's sheet) and the unit stats, weapons and keywords (Wahapedia's 11th edition datasheets) are embedded in `index.html`. Their source files are other people's data, so they are **not in the repository**: download them into the git-ignored `reference/` folder, then embed. When the sheet or the datasheets change (a new balance dataslate, a new codex):

```bash
mkdir -p reference/necrons
curl -L "https://docs.google.com/spreadsheets/d/1LXfBsLU7fAgLwlA4bTLZSH1JyBc4K_8yqoL77HHGuw4/export?format=csv&gid=2043610988" -o reference/necrons/spawn-standard.csv
curl -L "https://docs.google.com/spreadsheets/d/1LXfBsLU7fAgLwlA4bTLZSH1JyBc4K_8yqoL77HHGuw4/export?format=csv&gid=216374006" -o reference/necrons/spawn-detailed.csv
curl -L "https://wahapedia.ru/wh40k11ed/factions/necrons/datasheets.html" -o reference/necrons/wahapedia-datasheets.html
python3 tools/embed_data.py necrons
python3 tests/test_app.py
```

`embed_data.py` stops if a unit in the spawn tables has no datasheet, and prints these download commands if a file is missing. The test compares the embedded data with the files in `reference/` when they are there, and skips that comparison when they are not. Adding another Horde faction is described in `CLAUDE.md` ("Adding a faction").

## Deploy to GitHub Pages

First-time setup (already done for this folder): create an empty **public** repository named `horde-mode-40K-11th` on GitHub (no README, licence or .gitignore), then in this folder:

```bash
git init -b main
git status --short        # check: nothing from reference/ is listed
git add .
git commit -m "Horde Mode 40K 11th"
git remote add origin https://github.com/<your-user>/horde-mode-40K-11th.git
git push -u origin main
```

In the repository open **Settings → Pages**, set **Source** to **Deploy from a branch**, pick **main** and **/ (root)**, and save. The site is live after a minute or two. **To update:** commit and push.

## Putting it on the portfolio

It is one self-contained file, so either link to the deployed page like the other tools, or copy `index.html` and `.nojekyll` into the portfolio. It uses no relative paths, so it works under any subpath. Its saved game lives in `localStorage` under the key `horde-mode-necrons-v1`, which does not clash with the other tools.

## Good to know

- Anyone with the link can open the site. Search engines are asked not to list it.
- The game is saved in your browser, so one device holds the game. Secret Objectives hide behind a Peek button, which relies on trust like the physical cards do.
- On your phone, use **Add to Home Screen** to open it like an app.
- The page loads two fonts from Google Fonts when online. Offline it falls back to system fonts.
- Notes for changes, the data model and the rules decisions are in `CLAUDE.md`.
- `reference/` holds every source file (rules PDFs and the sheet's FAQ in `reference/rules/`, the spawn CSVs and the saved Wahapedia page in `reference/necrons/`). It is in `.gitignore` and must never be committed: they are other people's documents and data. The Sources below link to all of them.

## Sources

- [Horde Mode 11th Edition v0.9 rules and Hard Mode add-on](https://drive.google.com/drive/folders/1r0-H8Po8rkLjP1jsWT7ja4cdCwgQDWm5) by The Poorhammer Podcast. Turn sequence, spawning, the Horde AI, Misery deck, Secondary Missions, Secret Objectives, Resupply table and faction rules.
- [11th Edition v0.9 Horde Mode Spawn Brackets](https://docs.google.com/spreadsheets/d/1LXfBsLU7fAgLwlA4bTLZSH1JyBc4K_8yqoL77HHGuw4/edit) courtesy of DigitalBeef (Necrons and Necrons Detailed tabs, last updated 25 June 2026).
- [Wahapedia, Necrons datasheets (11th edition)](https://wahapedia.ru/wh40k11ed/factions/necrons/datasheets.html): unit stats, weapons and keywords (Necrons app version 1.2, read 19 November 2026). Ability text is not copied.

All rules and card text are short summaries in our own words, with numbers kept exact. Check the source documents for exact wording; the community rules are updated from time to time. The "Horde rules" on each unit sheet are our reading of the Horde Mode rules, not part of any source.

Unofficial, for personal use. Warhammer 40,000 belongs to Games Workshop. Horde Mode is a community format by The Poorhammer Podcast.
