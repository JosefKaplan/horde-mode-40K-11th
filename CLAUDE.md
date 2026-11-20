# Horde Mode 40K 11th (Necron Horde)

Folder and future GitHub repository: `horde-mode-40K-11th` (renamed from `horde-mode` on 19 November 2026). A personal, single-page web app for playing **40K Horde Mode (11th edition, v0.9)** with a **Necron Horde** against 1 to 4 players on one device. It runs the turn sequence, rolls the Horde's Spawn Rolls and suggests **ranked unit options** from the Necron spawn tables and the group's collection, shows each Horde unit's **datasheet and what the Horde AI does with it**, deals the Misery, Secondary Mission and Secret Objective cards, tracks CP and SP, and runs the Resupply shop. First used on 18 November 2026 (2 players); reviewed and extended on 19 November 2026.

Same family as the other vibes (`../chsm-checklist-11`, `../necron-11th-test-checklist`): one file, no build, `localStorage`, a Playwright test. Personal use only. Rules by The Poorhammer Podcast (community format), spawn brackets by DigitalBeef, unit stats from Wahapedia.

**Only Necrons for now, more Horde factions later** (the user's plan). Keep faction-specific things in `FACTION`, the generated data and `reference/<faction>/`, so a new faction is mostly data: see "Adding a faction".

## Files

| Path                                | What it is                                                                                                                                                                  |
|-------------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `index.html`                        | The whole app: HTML, CSS and JS in one file. No build step, no dependencies.                                                                                                |
| `tools/embed_data.py [faction]`     | Builds the spawn tables (DigitalBeef CSVs) and the unit data (Wahapedia datasheets page) from `reference/<faction>/` and embeds them in `index.html` between `/*SPAWN_DATA_START*/ ... END*/` and `/*UNIT_DATA_START*/ ... END*/`. From the datasheets it keeps only the units the spawn tables use, and only stat lines, weapons with keywords, unit keywords, core abilities, ability **names** with derived tags (no ability text), default loadouts with model counts, Leader/Support attach lists, transport capacity, damaged range and Warlord notes. Fails if a spawn-table unit has no datasheet; prints the download commands if a source file is missing. `FACTIONS` in it holds each faction's sheet tab ids and Wahapedia slug. Needs no network. |
| `tests/test_app.py`                 | Playwright test (242 checks): data vs sources, unit rules, rules maths, game flow, ranking, random pick and replace, redo spawn, zone clearing, Warlord, reserves, Misery effects, Secondary resolve, rewards and saved cards, shop, secrecy, persistence and migration, layout. Compares the embedded data with `reference/<faction>/` through `embed_data.build()` when the sources are there, and skips those two checks when they are not (a fresh clone). |
| `README.md`                         | Short run and deploy guide, data update commands, sources. Keep its Sources in sync with the one below.                                                                     |
| `reference/` (git-ignored)          | **Every source file, never committed** (other people's material; the user's rule: list sources in the docs, do not host raw data in the repo). `reference/rules/`: `Horde Mode Rules 11t Edition v0.9.pdf`, `Hard Mode Addon ... v0.9.pdf`, `11th Edition v0.9 ... FAQ.csv` (only a table of contents; its sheet links were lost in the export). `reference/necrons/`: `spawn-standard.csv`, `spawn-detailed.csv` (DigitalBeef's Necrons and Necrons Detailed tabs), `wahapedia-datasheets.html` (Wahapedia's 11th edition Necron datasheets page). Read rules with `pdftotext -layout`. README.md has the download commands. |
| `.nojekyll`, `.gitignore`           | Empty `.nojekyll` (GitHub Pages serves files as they are); `.gitignore` ignores `.DS_Store`, `__pycache__/`, `.idea/`, `reference/`.                                         |
| `CLAUDE.md`                         | This file.                                                                                                                                                                  |

Open `index.html` in a browser to use it. The game is saved in that browser's `localStorage` only (key `horde-mode-necrons-v1`), so each device and each address has its own save.

**Git:** its own repository since 19 November 2026, branch `main`, remote `origin` = https://github.com/JosefKaplan/horde-mode-40K-11th.git. **Live:** https://josefkaplan.github.io/horde-mode-40K-11th/ (GitHub Pages from `main`, root; a push redeploys it). Note the live site keeps its own `localStorage` save, separate from a local copy. `README.md` has the GitHub Pages steps. The user plans to put it on the portfolio (`../josefkaplan`) later, like the other tools.
- It must work under a subpath, so the page references no files by relative or root-absolute path (everything is inline; the test checks it).
- `localStorage` is shared by every site on the same origin. The key `horde-mode-necrons-v1` is unique; keep keys unique per app.
- Google Fonts is the only outside request (blocked in tests). `<meta name="robots" content="noindex, nofollow">` stays in.
- Other people's documents and raw data stay out of git: keep them in `reference/`, list them under Sources. Only the data the app needs is embedded in `index.html`. If a source file was ever committed and pushed, removing it needs `git rm --cached` plus a commit (the user's job), and it stays in the history unless the history is rewritten.

## Hard rules for changes

1. **Keep it one self-contained static file.** No frameworks, no CDN scripts, no build tooling, no `fetch`, no paths that assume the domain root. A claude.ai artifact copy would block `fetch` and remote images.
2. **Rules and card text are short summaries in our own words.** Keep every number, distance, dice roll, `[ABILITY]` and keyword exact. Check against the PDF when you change one. **Datasheet ability text is never copied**: the app shows ability names, our derived tags and our own rule bullets only.
3. **Keep IDs stable.** Misery (`m01` to `m36`), Secondary (`s01` to `s24`), Secret (`o01` to `o34`), Resupply (`name`, `basic`, `air`, ...) ids and standing-effect keys are stored in saves. Add new ids instead of renaming or renumbering. Ids are unique across all four lists (the test checks it). Unit keys are the lower-case names from the spawn tables (`necron warriors`, `c'tan shard of the deceiver`).
4. **Saved-state changes need a migration.** State is `v: 1`. Add new fields with defaults in `freshGame()` and backfill them in `migrate()`. `tests/test_app.py` removes the newest fields from a save and checks it still loads; add the new field to that list.
5. **Be honest about uncertainty.** If a rule's exact meaning is not confirmed, set `verify: true` on the card (the UI shows "Check wording") and list it under "Rules decisions" below.
6. **All state changes go through `mutate(fn)`** (undo, save, redraw), or `quiet(fn)` for changes not worth an undo step (ticks, typing a name). Storage access stays wrapped in try/catch (`store.get/set`); the app must work without storage.
7. **Secret Objectives must never appear on screen by accident.** They render face down unless `ui.peek` is that player, or the player revealed it. The Card reference lists Misery and Secondary cards only, on purpose. Never name a Secret Objective anywhere else (unit sheets, hints, logs of random picks). The test checks this.
8. **Run `CHROME_PATH=... python3 tests/test_app.py` after every change** (see Testing) and add a check for every new feature.
9. **Never run `git add`, `git commit` or `git push`.** Tell the user when one is needed.

## How the code is organised (`<script>` in `index.html`)

Sections appear in this order. Find things by name, not line number.

- **Data**
  - `SPAWN`: generated from `reference/<faction>/spawn-*.csv`, do not edit by hand (`tools/embed_data.py`). `{updated, standard: {'3-4': [...], ..., '13+': [...]}, detailed: {...}}`; every entry is the sheet's cell text, for example `Immortals (10) + Imotekh the Stormlord + Chronomancer`.
  - `UNITS`: generated from `reference/<faction>/wahapedia-datasheets.html`, do not edit by hand. `{faction, source, version, armyRules, units: {key: {name, kw, kwDetail?, profiles: [{M, T, SV, W, LD, OC, model?}], inv?, ranged/melee: [{n, kw, r, a, sk, s, ap, d}], core, abilities: [{n, tags}], comp, loadouts: [{n, items}], leader?, support?, transport?, damaged?, warlord?: 'never'|'must'}}}`. Ability tags: `army-rule` (the text names one of the datasheet's ARMY RULES, for Necrons Reanimation Protocols) and `stratagem` (the Horde ignores both), `command`, `their-turn`, `aura`, `once-per-battle`.
  - `FACTION`: the Horde faction's key, name and Primary Faction Rule (`rule.name`, `rule.text`, `rule.effect`, `rule.chip`, `rule.appliesTo(unit)`; rules 7.5). Step texts, unit sheets and chips read it. `ARMY_RULES` is `UNITS.armyRules` joined, for "no Reanimation Protocols" style texts.
  - `BRACKET_KEYS`, `BRACKET_MIN` (3, 5, 7, 10, 13: the lowest roll of a bracket, added when a unit is cleared from a zone), `ROUND_TABLE` (normal and hard: Misery cards and Spawn Roll modifier per round), `HARD_SP_CAP`, `PLACEHOLDERS` (`Leader`, `Support`, `Transported Unit`).
  - `MISERY` (36), `SECONDARY` (24), `SECRET` (34), `RESUPPLY` (26): the card data. Secondary cards carry `rewFx` / `penFx` objects that `applyFx()` turns into state changes, `perk` (what a saved card does), `xMin` / `xMax` and `afterHordeMoveRedraw` (see below).
  - `STANDING` (fortified markers) and `STANDING_COUNTED` (Teleporters, Razor Wire, Minefield: **not** fortified), with the stages (`when`) in which they remind you.
  - `STAGES`, `STEP_ITEMS`, `SETUP_ITEMS`: the turn sequence text.
- **Helpers**: `randInt` (crypto, unbiased), `shuffle`, `hash01` (stable noise for ranking), `pretty`, `titleCase`, `parseEntry` (spawn cell to `{baseKey, size, named, placeholders, need, label, lastResort}`, cached), `catalog()` (every unit name for the Collection editor), `tableSizes`, `bracketOfRaw`.
  - Unit rules: `unitData`, `hasKw`, `lastResortOf` (AIRCRAFT or FORTIFICATION keyword), `loadouts` (default loadouts matched to weapon profiles), `betterMelee`, `TARGETING`, `hordeProfile(key)` (everything rules 5 needs from one datasheet: charges, heavy, deepStrike, scouts, fly, fnp, targeting, command, ignored, warlordOk, ...), `attachOptions` (who can be "+ Leader" / "+ Support"), `entryCharacters`, `entryHasVehicleOrMonster`.
- **State**: `freshGame()`, `migrate()`, `store`, `mutate`, `undo`, `addLog`, `toast`. `ui` is in-memory only (open sheet, peek, expanded sections, shop tag).
- **Rules logic**
  - Rounds: `totalRounds`, `roundRules`, `stagesFor`, `isHordeOnlyRound`.
  - Spawning: `bracketFor`, `spawnMods` (the list of modifiers), `spawnResult`, `zoneStatus`, `rebuildSlots`.
  - Ranking: `usedModels`, `freeModels`, `shortfalls`, `rankOptions`.
  - Decks: `activateMisery` (automatic side effects), `revealMisery`, `forceMisery`, `clearFortified`, `afterHordeMove`, `revealSecondary` (handles "if drawn in round 1, reveal another" and Calling Shots after the Horde Movement phase; records `secAt`), `resolveSecondary(s, id, success, x, who)`, `rewardNeedsPlayer`, `xProblem`, `autoX`, `missionX`, `missionHint`, `discardSecondary` (the **Discard** buttons), `redrawSecondary`, `applyFx`.
  - SP: `gainSP` (Hard Mode cap), `gainAll` (single-player doubling).
  - Shop: `shopPrice`, `shopCheck(s, item, pi, x, {free, discount})` (returns the reason a purchase is not possible), `payFor` (records `buys`), `takeFree`, `completePurchase`.
  - Saved reward cards: `perkOf`, `perkLabel`, `spendSaved`, `useSavedFree`, `useSavedDiscount`, `useSavedCancel`.
  - Secrets: `dealSecrets`, `keepSecret`, `startChangeOfPlans`, `changeOfPlansForAll` (Establish Orbital Comms), `resetSecrets` (Setup changes after dealing).
  - Zones and roster: `setDie`, `rollZone`, `pickUnit` (stores `bracket`, `zoneNo`), `rollDownSlot`, `destroyUnit` (moves the unit to `destroyed`), `setZoneCleared` / `restoreCleared` (rules 4 step 2), `hordeWarlord`, the random-pick drafts (`drawRandom`, `acceptDraft`, `cancelDraft`, `replaceUnit`), `resetSpawn` (the **Redo spawn** button: clears every zone and the units spawned in the current round, puts cleared units back, keeps earlier rounds' units, the manual modifier and extra Pincer zones; behind a confirm sheet and undoable).
  - Turn sequence: `beginRound`, `startGame`, `advance`, `retreat`, `stepDiscardMisery` / `stepRevealMisery` / `stepRevealSecondary` / `runRoundStart` (each runs once per round, guarded by `auto:` ticks), `roundStartDone`.
- **Rendering** (Turn tab order: the stage's actions first, then this phase's Horde units, then the reference checklist; the shop is compact rows with the item text behind a tap on the name): `render()` rebuilds `#tracker`, `#main`, `#tabbar` and `#sheet-root` from state. Views: `renderTurn`, `renderHorde`, `renderCards`, `renderPlayers`, `renderSetup`. Pieces: `renderShop`, `renderZone`, `renderSlot`, `renderStageExtras`, `renderInPlay`, `renderSheet`, and the Horde unit pieces `inReserves`, `unitChips`, `phaseNotes`, `renderHordePhase` (the "Horde units this phase" panel), `hordeBehaviour` (rule bullets in our words), `datasheetHtml`, `renderUnitSheet`. Sheets: `newgame`, `destroy`, `share`, `resetspawn`, `startearly` (Start round 1 before the deployment spawn is done), `reveal`, `unit`, `secwho` (who triggered a reward), `replace` (Advanced Tactics), `perk` (use a saved card).
- **Events**: one delegated `click` handler that looks up `data-act` in `ACTIONS`, one delegated `change` handler for `data-change` (dice, zone clearing, names, numbers), and Escape closes the sheet. Inputs commit on `change`, not `input`, so typing never loses focus.

## Look ("Cogitator CRT", 19 November 2026)

The whole app is one military terminal screen, generic 40K rather than one faction (inspired by retro CRT terminals; copy no game's actual layout, icons or art). The phosphor colour `--ph` says whose turn it is: **green for the Horde and setup, amber for the players** (`body[data-who]`). Every colour token is mixed from `--ph` on `body` (not `:root`, because `--ph` changes per turn); CP, SP, bad and warn keep their own tints. The screen: a bezel and rounded glass with vignette and reflection (`body::before`), scanlines (`body::after`), both without pointer events. Status bar line `COGITATOR-XI · HORDE TACTICAL FEED` (CSS `content`), `> ` prompts, a blinking cursor after the turn name, `[ ]` / `[x]` ticks, `[ NEXT ]` key, inverted fill for active items, double-line panel frames, `!! ALERT` on Misery cards (blinking border), `CLASSIFIED ████` on face-down Secret Objectives. Fonts: VT323 (headings, labels, numbers, dice), IBM Plex Sans (rule text, for reading on a phone). Motion (power-on sweep once at load, rare flicker, cursor, alert) only runs without `prefers-reduced-motion`; nothing animates per render, because `render()` rebuilds the page on every tap. **Light** = "paper printout": dark ink on green-bar teleprinter paper, no bezel, glow or scanlines. Use `font-variant-caps: all-small-caps`, **not** `text-transform: uppercase`: `innerText` (and the tests) would see the uppercased text. Decoration text lives in CSS `content`, so it never reaches `innerText` either.

## Data model

- `state.round` is 0 during setup and deployment; `state.stage` is `setup`, `start`, `h-command`, `h-move`, `h-shoot`, `h-charge`, `h-fight`, `p-command`, `p-move`, `p-shoot`, `p-charge`, `p-fight`, `end` or `over`. The Horde always goes first. A Hard Mode final round has no `p-*` stages.
- `state.decks`: `misery` and `secondary` are `{draw, active, discard}` arrays of ids; `secret` is `{draw}`. An empty draw pile reshuffles the discard.
- `state.carry` is what failed (or rewarding) Secondary Missions add to the **next** round: `{misery, spawn, first, force: [misery ids], lz}`. `beginRound()` moves it into `state.rnd`, which the current round reads. This is rules 3.6.
- `state.zones[]`: `{id, extra, removed, cleared, dice, usedFirst, slots, ns, seed}`. `dice` is `[d1, d2]` (three with Unlucky Night; 0 means unset). `removed` is the bracket of a unit cleared from the zone; `cleared` is that unit when the app knew it (so it can be put back). `slots[]` is `{id, bracket, filled, draft, rejected}`; rolling down replaces a slot with two lower ones. `draft` is a random pick waiting for a decision (spawn it or roll again) and `rejected` lists the options already turned down for that slot. `extra` zones come from Pincer Maneuver. `seed` keeps the ranking order steady.
- `state.horde[]`: units on the table `{uid, zone, zoneNo, round, raw, baseKey, need, bracket}`. `need` maps a unit key to the models it uses; `zoneNo` is 1 to 4 (0 for Pincer Maneuver, null in old saves); `bracket` is the bracket it spawned from.
- `state.destroyed[]`: the same objects plus `{dRound, by, seq}` (`by` is a player index, `'none'` or `'zone'`). Keeps the Warlord fixed and feeds the Back To Basics count.
- `state.secAt{}`: a sequence number (`s.uid`) per Secondary Mission when it was revealed. `state.buys[]`: this round's purchases `{seq, pi, item, sp, tags}` (cleared each round). `state.secStats`: `{won, lost}` this game.
- `state.collection`: `{unitKey: modelsOwned}`. A missing key means "any number".
- `state.players[]`: `{name, cp, sp, spRound, lzUsed, secret: {choices, kept, revealed}}`.
- `state.standing`: `{fob: true, ..., tele: 2}` markers on the table. `state.saved[]`: `{id, owner, perk?, left?}` reward cards a player holds (`perk` is set for handed-out freebies such as Paint Targets; otherwise the card's own `perk` applies; `left` counts uses for Tactical Withdrawal's two Teleporters). `state.removedShop[]`, `state.bought{}` (once-per-turn purchases), `state.secX{}` (typed X values), `state.ticks{}` (also `auto:discard`, `auto:misery`, `auto:secondary`), `state.log[]`.

### Spawn roll (rules section 4)

Roll 2D6 (3D6 keep the best two while Unlucky Night is active), add the modifiers from `spawnMods()`, then `bracketFor()`:

| Total | Bracket                         |
|-------|---------------------------------|
| 3 to 4 | `[3-4]`                        |
| 5 to 6 | `[5-6]`                        |
| 7 to 9 | `[7-9]`                        |
| 10+    | `[10+]` (10 to 12 when `[13+]` is on) |
| 13+    | `[13+]` only when the Setup switch is on |

An **unmodified** 2 never spawns. Modifiers: the round's value, last round's mission results (`rnd.spawn`), Jamming Station (-1), the first-roll bonus (`rnd.first`, given to the first zone that rolls), the manual modifier, and the bracket minimum of a unit cleared from that zone. The clear step lists the Horde units from earlier rounds (with the zone they spawned in); picking one destroys it (no SP) and adds its bracket; "Another unit, by its bracket" covers anything the app does not know.

### How options are ranked (`rankOptions`)

This is our own design, not a rule. Rules 4 step 4 say to pick from the bracket by available collection or at random. Higher score is better; the list is sorted by it.

| Signal                                         | Effect                                                         |
|------------------------------------------------|----------------------------------------------------------------|
| Missing models (collection minus units on the table) | -1000: listed last under "missing models", cannot be picked normally |
| AIRCRAFT or FORTIFICATION keyword (Doom Scythe, Convergence of Dominion) | -60. Rules 4 designer's note: aircraft and fortifications "only as a last resort" |
| Same unit already on the table                 | -12 each (max 4), and -18 more per copy spawned this round      |
| Stable noise from the zone seed                | +0 to +6, so equal options come out in a random but steady order |

The top 3 are shown, with reason chips ("You have the models", "New to the table", "Aircraft: last resort", "Deep Strike: starts in reserves" in rounds 2 to 4). Everything else is under "All options". **Random pick** ignores the ranking: it draws uniformly among the possible options as a *draft* (nothing is spawned). **Spawn this** commits it, **Roll again** turns it down and draws another that was not turned down yet (when all were turned down the list starts over, never the same twice in a row), and **Back to ranked options** drops the draft. A spawned unit still on the table has a **Replace** button that takes it off and draws another random one the same way. A collection entry left blank means "any number", so with an empty collection only variety and last-resort units matter. Every unit name is tappable and opens its unit sheet.

### Horde unit rules (`hordeProfile`, `hordeBehaviour`, `phaseNotes`)

Derived at runtime from `UNITS`, so the rules logic stays testable and the data stays raw:

| Rule (Horde Mode) | From the datasheet |
|-------------------|--------------------|
| 4.5a Deep Strike in rounds 2 to 4: strategic reserves, ingress in Horde Movement | core ability `Deep Strike`; `inReserves()` also covers the Pincer Maneuver unit, until the Horde Movement phase ends |
| 5.1 Scouts on the spawn turn | core ability `Scouts X"` |
| 5.3 FLY, [HEAVY] moves at most 3" | keyword `FLY`; [HEAVY] carried by most models (any for a single model) |
| 5.4 Advance when all guns are [ASSAULT] | default ranged weapons, Pistols excluded |
| 5.6 targeting | [ANTI-X], [X HUNTER], [PRECISION], [MELTA] on ranged weapons |
| 5.7 charges | most models carry a melee weapon with AP, Damage above 1 or a weapon ability (see Rules decisions) |
| 7.5 We're So Back (FNP 5+) | INFANTRY, BEAST(S) or SWARM, not CHARACTER |
| 3.1 / 5.1 no army rules or Stratagems | abilities tagged `reanimation` or `stratagem` are listed as "ignore" |
| 4 Warlord: first CHARACTER spawned | `hordeWarlord()`; skips datasheets that say "cannot be your Warlord" (C'tan); a destroyed Warlord is not replaced |

The Turn tab shows a "Horde units this phase" panel in every Horde phase (Command abilities, reserves, Scouts, [HEAVY], FLY, targeting, who charges, Fights First). The roster shows chips (Warlord, In reserves, Charges/No charge, Heavy, Deep Strike, FNP 5+). For "+ Leader" / "+ Support" the unit sheet lists the characters whose LEADER / SUPPORT section names that unit; for "+ Transported Unit" it shows the transport capacity.

### Secondary Mission effects (`rewFx` / `penFx`)

`sp` and `cp` go to every player (doubled in a single-player game); `spx` is a formula in X (`X`, `X+1`, `X*2`); `spLose`; `misery`, `miseryX`, `spawn`, `spawnX`, `first` go to `state.carry`; `force` adds a Misery card next round; `forceNow` resolves one now; `removeShop`; `clearFortified` (fortified markers only); `lz` (cheaper first purchase next Resupply); `save: 'random' | 'pick'` gives the card to a player (`'pick'` asks which, Tactical Withdrawal); `grants: [{item, to}]` hands out free purchases as saved rewards (Dragon Slayer, Paint Targets, Baiting the Trap, Stabilize Warp Beacons); `nobody` replaces the grants when the "Nobody" button is used (Dragon Slayer: 2 SP each); `plans: 'choose' | 'random'` runs A Change of Plans for every player with an unrevealed objective; `custom: 'use-it-or-lose-it'` rolls its D6. Card fields: `perk` is what a saved card does when used (`tag`: one free purchase with that tag, `item` + `uses`: free purchases of that item, `discount`: SP off that item, `cancelMisery`); `xMin` / `xMax` block Success outside the card's X limits; `afterHordeMoveRedraw` shuffles Calling Shots back when it is revealed after the Horde Movement phase. `autoX` fills X for Back To Basics (Horde units destroyed since the reveal, zone clearing excluded) and Use It Or Lose It (SP spent in the shop since the reveal); `missionHint` shows counts for Decapitation Strike, Dragon Slayer, The Smell of Napalm, Marching on Stomachs and Spruce This Place Up. Anything else (actions, conditions) stays as text on the card and is shown in a toast when you resolve it.

## Rules decisions

Where the rules text left room, this is what the app does. Change it here if the group rules otherwise.

- **The Horde has a Command phase** (`h-command`, added on 19 November 2026; before, it was skipped). This is an **inference**: no rule says it in so many words, and the user did not know either. The evidence: rules 3.1 apply the core rules "with the following additions and alterations", and the only ones touching the Horde's Command phase are no CP and no Stratagems; rules 7.5 (Tyranids) change "each time a Horde TYRANIDS unit makes a battle-shock roll", which only works if Horde units test; rules 5.1 "The Horde utilizes all datasheet abilities it can", which includes "in your Command phase" abilities (Imotekh, Trazyn, Canoptek Spyders, Psychomancer). So Horde units below half strength take battle-shock tests. Remove the stage from `stagesFor` if a later rules version or FAQ says otherwise.
- **No Reanimation Protocols for the Horde.** It is an army rule on the 11th edition datasheets; rules 3.1 remove army rules and 5.1 says to ignore abilities that stop working because of that. Abilities that only activate Reanimation Protocols (Their Number is Legion, Repair Barge, Resurrection Orb, Nanoscarab beams) are marked "ignore", as are those that need Stratagems or CP (My Will Be Done, Inescapable Death, Sentinel Construct).
- **"Better than a close combat weapon" (rules 5.7)** means a melee weapon with AP, Damage above 1 or any weapon ability. Close combat weapons and armoured bulk are AP 0, D 1 with no abilities. Charges are decided by the models carrying the default loadout: the Silent King does not charge (2 of 3 models have only armoured bulk). By this reading the Monolith (portal of exile), Triarch Stalker, Catacomb Command Barge and Canoptek Spyders do charge, and the Canoptek Doomstalker and Canoptek Reanimator (claws no better than armoured bulk) do not. Agreed by the user on 19 November 2026.
- **Side-arms**: a Pistol only counts as a Side-arm on a unit whose melee is better than a close combat weapon (rules 5.4 definition), so the Hexmark Destroyer (pistols, close combat weapon) does not charge.
- **Night Scythe is not an aircraft in 11th edition** (`VEHICLE; FLY; TRANSPORT`, with Hover), so it is no longer ranked as a last resort. The Doom Scythe (AIRCRAFT) and the Convergence of Dominion (FORTIFICATION) are.
- **Warlord**: the first CHARACTER spawned whose datasheet allows it (C'tan Shards and the Transcendent C'tan "cannot be your Warlord"). A "+ Leader"/"+ Support" placeholder counts as a CHARACTER. The Silent King's datasheet says it must be the Warlord; the app follows the Horde rule and says so on its sheet. A destroyed Warlord is not replaced.
- **A modified Spawn Roll under 3 spawns nothing** (there is no lower bracket). With `[13+]` off, a roll of 10 or more uses `[10+]`.
- **Only one cleared unit per zone** is a selectable bracket; use the manual modifier if more were cleared. The clear step also reminds that Player units in the zone are destroyed (rules 4 step 2 says "any units").
- **First-roll bonuses** (Dragon Slayer +6, Baiting the Trap +12) go to the first zone that rolls in the next round.
- **Study Behaviors** punishment reads "+3 to Spawn Roll" (singular) in the PDF; the app applies it to every Spawn Roll next round, like the other cards.
- **Secondary SP rewards go to every player** (rules 3.7), CP too for Decapitation Strike. Rewards that name "a random player" are drawn by the app; rewards for "the player whose unit completed it" (Tactical Withdrawal, Baiting the Trap, Dragon Slayer, Stabilize Warp Beacons) ask which player. Dragon Slayer with nobody triggering it gives 2 SP to each player.
- **Establish Orbital Comms punishment**: "they select one at random" is read as random among the old objective and the two drawn ones; the app picks unseen.
- **Saved reward cards** (free purchases, discounts, cancelling a Misery card) are used from the Players tab. A free purchase still obeys Misery restrictions, once-per-turn limits and marker limits, does not use the Secure the LZ discount, and counts as a purchase for The Smell of Napalm and Marching on Stomachs. The Reinforcements Arrive discount comes off the price after Seller's Market doubling. Cancelling a Misery card does not undo one-off effects that already happened.
- **Bunkers Busted and Spruce This Place Up** remove fortified markers only (FOB, Warp-Relic Outpost, War Trench, Field Hospital, Jamming Station, Ammo Dump, Shield Generator), not Teleporters, Razor Wire or Minefields (rules 3.9: fortified markers sit on objectives). Before 19 November 2026 the app removed every marker.
- **`verify: true` on Baiting the Trap:** the PDF lists "+12 to the first Spawn Roll" under **Reward** (checked on page 15 of the PDF). It reads oddly for a reward but is what the source says.
- **Hard Mode in an infinite game** uses the round 5 values from round 5 on and has no Horde-only round. The Hard Mode PDF is titled v0.9 but its page footer says v1.0.
- **Detachment Points shown in Setup** (2 Incursion, 3 Strike Force): the Horde rules state only the 3 for Strike Force; the 2 comes from the core rules as recorded in `../chsm-checklist-11/CLAUDE.md`.
- **Once-per-turn purchases** are tracked per round (and per player where the rules say per player).
- **Teleporters (max 3), Razor Wire (max 2), Minefield (max 1)** are counted as markers; Fortify purchases are unique (one of each).
- **Secret Objectives** are only dealt in a 5-round (non-infinite) game, as in rules section 2 step 6. Multiplayer-tagged cards are removed for a single player; Traitor cards can be removed in Setup (the rules let playgroups do this). Changing the player count or the Traitor switch during setup takes dealt cards back so they can be dealt again.

## Verification status

On 18 November 2026:
- The **Necron Standard and Detailed tables** were downloaded from DigitalBeef's sheet (last updated 25 June 2026) and are checked by the test against `reference/necrons/spawn-*.csv` entry by entry (Standard 19 / 44 / 25 / 10 / 1 entries per bracket, Detailed 19 / 57 / 132 / 48 / 1).
- **Rules, Misery cards (36), Secondary Missions (24), Secret Objectives (34), Resupply table (26) and the Hard Mode add-on** were written from `Horde Mode Rules 11t Edition v0.9.pdf` and `Hard Mode Addon ... v0.9.pdf` and read against the PDF text; the ambiguous Baiting the Trap layout was checked on the rendered page. They are summaries, not copies.
- The Drive folder also holds printable card PDFs and a "10th to 11th Changelog". **Those were not read**; the printables show the same cards, and the changelog may mention changes worth checking.
- **The ranking is our own design**, not part of the source documents.

On 19 November 2026 (review):
- The app was played through at 390 and 360 px in headless Chrome (setup, deal, spawn, every phase, shop, round end, round 2, dark mode) and the screens were read. Fixed from that: the shop was about 6,500 px of full-text cards (now compact rows, about 1,850 px), actions sat below long checklists, the Secondary card showed twice at round end, round 1 zones showed a useless clear-the-zone picker, and nothing warned that Secret Objectives were dealt but not kept.
- The live sheet was downloaded again: both tabs were byte-identical to the saved CSVs (still dated 25 June 2026).
- Every card was read again against the PDF text. Fixed: Untouchable (the +1 is for models that already had a **4+** invulnerable save), Bunkers Busted / Spruce This Place Up (fortified markers only), Horde AI texts (Side-arms Advance criterion, Deep Strike fallback when no spot is valid), Tactical Withdrawal (to the completing player, not a random one).
- **Unit data** was read from Wahapedia's 11th edition Necron datasheets page ("App. Necrons (11th edition, version 1.2)", core rules updated June 2026). All 52 units named in the spawn tables have a datasheet. The derived Horde behaviour was reviewed unit by unit; the tests pin the key cases. It is our reading of rules 4 and 5, not part of any source document. Wahapedia is a fan site: if the official app differs, the official app wins.

## Known gaps / next steps

- Only Necrons so far (see "Adding a faction" below). The Horde rules also allow a Horde built from several factions' tables; the app has one faction at a time.
- Not tracked: partial unit losses (units count whole, so below-half-strength battle-shock is up to the players), Secret Objective tallies, the Minefield damage tally, which units have Enhancements, which Leader joined a "+ Leader" unit, the players' own armies (Reinforcements Arrive, Deploy Fortification and Field Promotion use the player's faction table, which the app does not hold). Using a free Field Promotion, Reinforcements Arrive or Deploy Fortification marks it bought; the rest is done by hand.
- Datasheet ability text is not in the app (names and tags only); read it in the official app.
- Jamming Station and FOB assume the players control them; remove the marker or use the manual modifier when they do not.
- One device holds the game. There is no sync between phones.
- Secondary Mission conditions are not checked automatically; you press Success or Failed (the app shows counts where it can).

## Adding a faction

The user wants more Horde factions later. What a faction needs, and where it goes:

1. **Sources** in `reference/<faction>/` (never committed): `spawn-standard.csv` and `spawn-detailed.csv` from DigitalBeef's sheet, and `wahapedia-datasheets.html`. The sheet's tab ids are listed by `curl -sL "https://docs.google.com/spreadsheets/d/1LXfBsLU7fAgLwlA4bTLZSH1JyBc4K_8yqoL77HHGuw4/htmlview" | grep -o 'items.push({name: "[^"]*"[^}]*gid: "[0-9]*"'`; the Wahapedia page is `https://wahapedia.ru/wh40k11ed/factions/<slug>/datasheets.html`. The knight factions have no Detailed tab (the FAQ says it would be identical): point both at the Standard tab.
2. **An entry in `FACTIONS`** in `tools/embed_data.py` (name, `gid_standard`, `gid_detailed`, `wahapedia` slug). `python3 tools/embed_data.py <faction>` prints the download commands when files are missing, then embeds.
3. **The Primary Faction Rule** from rules 7.5 in `FACTION.rule` (our own words; `appliesTo` says which datasheets it changes). Some rules change the round (Orks: one more Misery card and +1 to Spawn Rolls in round 3; Adepta Sororitas: the first Spawn Roll from round 4 is an unmodified 12; Genestealer Cults bring units back): those need code in `roundRules` / `spawnMods`, not just text.
4. **Check the parser**: the Wahapedia markup was the same for every datasheet on the Necron page; another faction may have new section headers. Read the embed output and a few unit sheets.
5. Decide then how factions live side by side (one app with a faction switch and the data keyed by faction, or one build per faction). The `localStorage` key `horde-mode-necrons-v1` must keep working for the saved Necron game.

## Testing

```bash
pip install playwright && python3 -m playwright install chromium   # once
python3 tests/test_app.py                                          # tests ./index.html
CHROME_PATH="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" python3 tests/test_app.py   # use installed Chrome
python3 tests/test_app.py http://localhost:8000/                   # a local server (python3 -m http.server 8000 --bind 127.0.0.1)
```

Use `CHROME_PATH` when Playwright's pinned Chromium build is not installed (this happened on 18 and 19 November 2026). Without `reference/<faction>/` the two source-comparison checks print `skip` and the rest still runs. The test runs at phone size (390x844, then 360x740), blocks Google Fonts, and stops at the first failing check. It only talks to a local file or a server on `localhost` / `127.0.0.1` (it refuses any other URL), so it never touches the network.

Decks are stacked in the test with `PLAIN_DECKS` (cards without automatic side effects) so reveal counts are exact. Mutation-tested on 18 November 2026: changing the round table, the aircraft penalty, the unmodified-2 rule, Seller's Market doubling and the round carry-over each makes a check fail. On 19 November 2026: clearing every marker on Bunkers Busted, treating every melee weapon as better, never putting units in reserves, letting the round start run twice, and ignoring "cannot be your Warlord" each make a check fail.

## Sources

- The Poorhammer Podcast, Horde Mode 11th Edition v0.9 and Hard Mode add-on (Drive folder): https://drive.google.com/drive/folders/1r0-H8Po8rkLjP1jsWT7ja4cdCwgQDWm5 (rules, card decks, spawn brackets)
- DigitalBeef, Horde Mode Spawn Brackets (Google Sheet; Necrons tab `gid=2043610988`, Necrons Detailed `gid=216374006`): https://docs.google.com/spreadsheets/d/1LXfBsLU7fAgLwlA4bTLZSH1JyBc4K_8yqoL77HHGuw4/edit
- Wahapedia, Warhammer 40,000 11th edition, Necrons datasheets: https://wahapedia.ru/wh40k11ed/factions/necrons/datasheets.html (stats, weapons, keywords; unofficial fan site)
