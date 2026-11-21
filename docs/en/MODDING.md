# Making M24GA Mods

[한국어](../MODDING.md) | **English**

M24GA is a loader that attaches mods to FM24 (Epic build; Steam build 24.4.2 is also supported). One mod is **a single `.24mod` file** (it is a zip); the user puts it in the mods folder and turns it on and configures it in the M24GA app.

This document is for people who make mods. The core version is **0.44.0**, and while it is `0.x` the names and shapes of core functions may change (a change is filtered out by the `core` condition in `mod.json`).

The fastest start is to copy [`examples/hello/`](../../examples/hello) and change it. It contains every setting type, the mod window, the Python part and the game-side JS once each.

**If you are asking an AI to build it**, read [AI_GUIDE.md](AI_GUIDE.md) first: what works and what does not, common mistakes, and a starter prompt to paste to the AI.

**Tools** (they run without the game):

| Command | What it does |
|---|---|
| `python -X utf8 tools/m24.py new <id> [--python] [--ui] [--dir folder]` | Creates a working mod skeleton (includes `AGENTS.md` for AIs) |
| `python -X utf8 tools/m24.py validate <mod> [--json] [--strict]` | Reports problems with location, reason and how to fix |
| `python -X utf8 tools/m24.py pack <mod folder>` | Validates and packs into a `.24mod` |

Editor support: put [`mod.schema.json`](../mod.schema.json) in `"$schema"` of `mod.json` for autocompletion and error markers, and `/// <reference path=".../docs/types/m24ga.d.ts" />` and `// @ts-check` at the top of `mod.js` so missing functions and wrong arguments get red underlines ([types/m24ga.d.ts](../types/m24ga.d.ts), [types/m24ga.pyi](../types/m24ga.pyi)). New mod skeletons include both.

## 1. Mod structure

```
my-mod-1.0.0.24mod   (zip)
  mod.json           required. Introduction and settings items
  mod.js             the part that runs inside the game (Frida JS). required
  python/main.py     the part that runs on the PC (AI calls, file work, …). optional
  ui/index.html      the mod window (a screen inside the app). optional
  builds/*.json      game address signatures used only by this mod. optional
```

- The mods folder is `Documents\M24GA\mods` (the app's "Open mods folder" button). If Documents is moved to OneDrive it is `M24GA\mods` inside that.
- **While developing, an unpacked folder** (a folder with `mod.json` in it) placed in the mods folder is recognised the same way. If you use the loader repository directly, the repository's `mods/` is read too.
- If two or more mods have the same `id`, none of them turns on and the app shows a conflict.
- Packing into `.24mod`: `python -X utf8 tools/pack_mod.py <mod folder> [output folder]` → `<id>-<version>.24mod` (`__pycache__` and hidden files are left out).

## 2. mod.json

| Item | Description |
|---|---|
| `id` | **Required.** Lowercase letters, digits, `-`, `_`, up to 64 characters. It is used in settings and data folder names, so do not change it once chosen |
| `name`, `version` | **Required.** The name and version shown in the app (`1.0.0` format recommended) |
| `description`, `author`, `license` | Shown on the app's info tab |
| `core` | Required core version: `">=0.2.0"`, `"==0.2.0"`, `"0.2.0"` (exactly equal). Using `api.send/recv` and `ctx.recv/post` needs `>=0.2.0`, `api.onUnload/alive` needs `>=0.3.0`. If it does not match, the app says it cannot be turned on |
| `js` | Game-side file name (default `mod.js`) |
| `python` | Python entry file (e.g. `python/main.py`). If absent there is no Python part |
| `ui` | Mod window HTML (e.g. `ui/index.html`). If absent the mod-window tab is disabled |
| `default_enabled` | Whether it is on at first install (default `true`). When the user changes it, it is stored in `enabled.json` |
| `data_dir` | Mod data folder (default `~/m24ga_data/<id>`). `~` can be used |
| `migrate_from` | An old data folder. If the new data folder is empty, it is **copied once** on first turn-on (the old folder is left as it is; if the new folder has content nothing is done). For mods that moved their data folder |
| `capabilities` | (core 0.4.0) List of capability names the mod uses. List and meanings: [`CAPABILITIES.md`](../CAPABILITIES.md) (section 11) |
| `settings_file` | File name to store settings in (default `settings.json`, inside the data folder) |
| `settings` | List of settings items (section 3) |
| `requires` | List of required Python package names. If missing the app only shows a warning (it does not block turning on) |
| `events` | List of events used (for reference; the loader does not check it) |

## 3. Settings (`settings`)

If you list items in `settings`, **the app's settings tab is generated automatically.** You do not need to write HTML. Values are stored in `<data folder>/<settings_file>` and survive when you replace the mod with a new version.

```json
{"key": "style.swear", "type": "select", "label": "Tone", "default": "normal", "group": "Tone",
 "options": [{"value": "normal", "label": "Normal"}, {"value": "wild", "label": "Wild"}], "help": "A line of explanation"}
```

- `key`: a dot (`.`) nests it inside the file (`style.swear` → `{"style": {"swear": ...}}`). Other items in the file are left alone.
- Common: `label` (name), `default`, `help` (grey explanation), `group` (card group name; "Settings" if omitted).

| `type` | Screen | Extra items |
|---|---|---|
| `bool` | Switch | |
| `int` | Number input | `min`, `max` |
| `number` | Number input; **a slider when both `min` and `max` are given** | `min`, `max`, `step`, `percent` (if `true` 0–1 is shown as %) |
| `text` | One-line input | `multiline`, `placeholder` |
| `password` | Masked input. The value is never sent to the screen; only "saved" is shown | `placeholder` |
| `select` | Segmented buttons for 4 or fewer, a dropdown for more | `options`: a list of strings or a list of `{"value", "label"}` |

A value out of range or in the wrong format is not saved and the reason is shown as a toast. A missing or wrong value in the file is read as `default`.

## 4. The game-side part (mod.js)

The loader bundles **the core + the enabled mods into a single Frida script** and loads it into the game (`fm.exe`). A mod is placed inside `registerMod('<id>', function (api) { /* mod.js */ })`, so a variable made with `var` is visible only inside that mod.

> Always declare with `var`. Assigning without `var` overwrites global variables of the core or other mods.

### What the loader provides

- `DIR`: the mod data folder (with a trailing `/`, e.g. `C:/Users/me/m24ga_data/my-mod/`). You may write a `var DIR = ...;` line (the loader replaces the value) or omit it.
- The game process cannot write inside `Program Files`, so keep files you exchange inside `DIR`. Use Frida's `File` (`File.readAllText(path)`, `new File(path, 'a')`).

### api

| Function | Description |
|---|---|
| `api.on('socialPanel', fn)` | When a social panel (one cell of the social feed) is drawn. `fn(ev)`, `ev = { th, type, dst, text }`: `th` panel object address, `type` text kind (0 news title, 2·4 fan comments, 3·5 official posts), `dst` address of the text slot, `text` the current text. Called on the thread that draws the screen |
| `api.on('frame', fn)` | Right after each frame of the screen thread (about 20 times a second). **Do not do slow work.** The mod controls its own interval (with `Date.now()`) |
| `api.on('dateChanged', fn)` | (core 0.5.0) When the game date changes. `ev = { from, to, days }`, dates are `{ y, m, d, doy, iso }`. The core checks every 0.5 s (not the screen thread) |
| `api.on('newsAdded', fn)` | (core 0.35.0, capability `event.newsAdded`) Every time the game adds a news item (hundreds a day: match reports, transfers, injuries, media opinions …). `ev = { cls, flags, toInbox, team, mine, text() }`. `cls` = news kind (class name), `mine` = addressed to my team, `text()` = the game's body text (plain text; expensive, so only when needed and only inside the callback). It runs on a game thread, so keep it short and hand long work to Python with `api.send`. Mail inserted by a mod with `api.inbox.send` does not trigger it. (core 0.37.0) `ev.id` (news number), `ev.date` ('YYYY-MM-DD'), `ev.refs()` = related records `{ people, teams, clubs, comps, refs }` (the people/teams/competitions the game attached to the news; only inside the callback) |
| `api.on('matchEnded', fn)` | (core 0.37.0, capability `event.matchEnded`) Once per match when a match report news item appears. `ev = { home, away, homeGoals, awayGoals, comp, stadium, mine, date, text() }`. Teams and competitions are objects: read them like `api.prop(ev.home, 'Tnam').Tsna` (team short name) and `api.prop(ev.comp, 'cnam')` (competition name). Only matches of leagues and cups the game reports arrive; penalty shoot-outs are not distinguished yet. Details: [NEWS.md](../NEWS.md) |
| `api.on('gameSaved', fn)` | (core 0.35.0, capability `event.gameSaved`) After a game save finishes (the .fm file is written). `ev = { ms, save }` |
| `api.on('saveLoaded', fn)` | (core 0.5.0) When a different save was loaded. `ev = { id, nonce, date }`. If the mod came up later it has already passed, so check with `saveInfo()` at the start |
| `api.every(ms, fn)` / `api.after(ms, fn)` | (core 0.5.0) Timers (minimum 50 ms). Stop with the returned `stop()`; **the core stops them automatically when the mod is unloaded** (do not use `setInterval` directly). Not the screen thread |
| `api.setPlayerPA(uid, pa, opts)` | (core 0.7.0, capability `write.player.pa`, **user permission required**) Changes a player's potential (see "Writing game values" below) |
| `api.hook(name, { before, after })` | (core 0.11.0, capability `hook.function`, **user permission required**) Hooks a game function in the function registry (see "Hooking game functions" below; list in [`FUNCTIONS.md`](../FUNCTIONS.md)) |
| `api.gate(name, on?)` | (core 0.15.0, capability `hook.gate`, user permission required) Switches on a registered gate: inside a specified game function only, a specified question gets a different answer (for example "is the manager human" in the value calculation). Several gates can be applied to the same slot (0.16.0). Returns `{ ok, set(on), stats(), stop() }`. List: 'Gates' in [`FUNCTIONS.md`](../FUNCTIONS.md) |
| `api.scale(name)` | (core 0.17.0, capability `hook.scale`, user permission required) For a function in the registry that has a scale (e.g. `player.value` = a player's value), multiplies the return value by a per-object factor: `s.set(player, 1.2)`. It is a native table, so it stays fast even when called tens of thousands of times a day. Clamped to the game's limits. One mod per function. Returns `{ ok, set, get, clear, enable, stats, stop }` |
| `api.setField(obj, name, value, opts)` | (core 0.10.0, capability `write.field` or that field's capability, **user permission required**) Changes a slot whose write is verified in the field registry (see "Writing game values" below; list in [`FIELDS.md`](../FIELDS.md)) |
| `api.setProp(target, code, value, opts)` | (core 0.42.0, capability `write.prop`, **user permission required**) Changes a property-code value with the game's own setter → Promise `{ok, before, after, code, key, error}` (see "Writing by property code" below; list in [`PROPERTIES.md`](../PROPERTIES.md) "Writing") |
| `api.saveData` | (core 0.44.0, capability `save.data`) Per-save mod data (see "Per-save mod data" below) |
| `api.settings()` / `api.onSettings(fn)` | (core 0.12.0) This mod's setting values `{key: value}` (`settings` in mod.json, `default` if none, **password types are left out**) and a function called with the new values when settings change in the app. No user permission needed. Do not read the settings file directly (it would require the `pc.file` permission). Python: `ctx.settings()` |
| `api.status(fn)` | The object `fn()` returns is merged into the loader status (`rpc status`) |
| `api.prepareData(th)` | Starts building the game data tables (the address book of clubs, players, staff) and gets the value types. Call it once inside a social panel. The tables take 1–2 minutes. When ready, the global `mapsReady` becomes `true` |
| `api.log(msg)` | Goes to the loader log (`~/m24ga_data/loader.log`) as `game: [<id>] msg` |
| `api.send(obj)` | Sends a message to this mod's **Python part** (received with `ctx.recv()`). `obj` must be JSON-serialisable |
| `api.onUnload(fn)` | (core 0.3.0) Called when the mod is unloaded (turned off, new version installed, reloaded). The core removes what you registered through `api`, but clean up here what the mod attached **itself**: `Interceptor.attach`, `setInterval`/`setTimeout`, and changed screen text. `api.log/send` work inside |
| `api.alive()` | (core 0.3.0) `true` while still loaded. Check it in leftover timers etc. (after unloading, `api` calls do nothing) |
| `api.recv(fn)` | Receives messages sent by Python's `ctx.post(obj)`. Only one `fn(obj)` can be registered (a later one replaces the earlier one), and it is called on another thread of the game (JS runs one at a time, so mod variables are safe) |

**Turning mods on and off (hot reload, core 0.3.0):** When a mod is turned on or off or a new version is installed in the app, the loader unloads and loads **only that mod, leaving the core script and the game data tables alone** (it used to reload the whole script and rebuild the tables for a minute and a half). For a development-folder mod, after editing `mod.js` press **Reload game side** on the app's info tab and it is applied without restarting the game (pressing **Refresh** in the mods folder also reloads only the changed mods). A reloaded mod's variables start fresh, so send a `hello` each time it comes up to align state with Python. The Python part needs an app restart for new code.

Errors in mod callbacks are caught by the core with `try/catch`, so **other mods and the game do not stop.** Still, wrap code that reads game memory in your own `try/catch` and, on failure, change nothing and move on.

### Core functions (usable from a mod as they are)

- **Player ability and identity (core 0.6.0, `read.player`):** `playerOf(o)` (person data object → player object, `null` if not a player), `playerByUid(uid)`, `playerInfo(p)` → `{ uid, ca, pa, dob, name }` (CA/PA 1–200), `playerUids()` (all player UIDs), `personUid(o)` (unique ID), `personOf(p)` (core 0.9.0, player object → person data object: the object you read properties from with `getVal`). They work even before a social panel has been drawn.
- **Competition and award info (core 0.20.0, `read.award`):** `compInfo(number)` → `{ idx, uid, name, short, nation, continent }`, `awardInfo(number)` → `{ idx, name, short, comp, nation, continent }` (comp = number of the competition the award belongs to; nation and continent are names), `compIds()`, `awardIds()`. Core 0.21.0: `compLatest(number)` → `{ comp, start, end, winner, runnerUp, third }` (the most recently finished season; team number = db::TEAM +0x8). The numbers are the same as in the save records (Python `m24awards` award and competition numbers), so when Python sends a number the game side can attach a name. The tables are built after a save is loaded (`null` if absent).
- **Player value (core 0.17.0, `read.player.value`):** `playerValue(p, club?)` → `{ value, reasons: [{code, a, b}], club }` (internal currency units, KRW = ×1664.7). It calls the game's value function as it is (with the gates and scale tables applied). If you pass a club, it is the value that club assesses (a transfer offer). While the game is running it returns `{ error, busy }`. Call it **from a timer (`api.after/every`)**: called inside a `frame` or `api.hook` callback it returns a value without the gates and scales. Meanings of the reason codes: `player.value` in [`FUNCTIONS.md`](../FUNCTIONS.md).
- **Field registry (core 0.10.0, `read.field`):** `getField(obj, 'player.askingPrice')`, `findObj('player', uid)`, `fieldInfo(name)`, `fieldNames('player.season.league.')`. Reads, by name, the slots registered in [`core/fields.json`](../../core/fields.json) (list in [`FIELDS.md`](../FIELDS.md)). It checks the object's kind by class name and returns `null` for a different kind. Slots that the dedicated functions (`playerInfo`, …) do not have can be read here if they are registered, and **adding one line to `fields.json` for a new slot** makes it available to all mods.
- **An object's class name (core 0.9.0, `read.rtti`):** `className(obj)` → `'db::ACTUAL_PLAYER'` (`null` if none), `isA(obj, 'db::PERSON')`, `rttiInfo(obj)` → `{ name, off, top, bases }`. Reads the class information (RTTI) left in fm.exe, so you can check an object's kind by name instead of vtable address. For investigating the game use the CLI `explore` and `classes` ([`CLI.md`](CLI.md)).
- **Player season record, positions, traits, team (core 0.8.0, `read.player`):** `playerSeason(p, kind)` → `{ apps, starts, subs, minutes, rated, ratingSum, avg, goals, assists, pens }` (kind: `'club'` club competitive total (default) · `'league'` · `'cup'` · `'continental'` · `'international'`), `playerSeasonDetail(p, kind)` → `{ xg, xa, npxg, shots, keyPasses, ... }` (only xG has been checked against the game properties), `playerPositions(p)` → `{ GK: 1, DC: 20, ... }` (1–20), `playerPosition(p)` → `{ code, level }`, `playerTraits(p)` → `{ ambition, professionalism, determination, workRate, flair }` (1–20), `playerTeam(p)` → `{ team, club, name, short, compUid }`, `playerInjury(p)` → `{ injured, proneness, type, daysSince, remainMin, remainMax }` (core 0.8.1, after the person table is built). All take a player object (`playerByUid`/`playerOf`).
- **Social panel helpers (core 0.6.0, `read.panel`):** `panelAt(addr, type)` (find a panel again from an address string), `panelText(th)`, `panelTextHandle(th)`, `panelDst(th)`, `panelThread(th)`, `panelFanUid(th)`. Club names: `clubFullName(cd)`, `clubShortName(cd)`, `clubObj(cd)` (`read.data`). For what these helpers can do, do not use direct reads such as `ptr()` and `.readU32()` (`raw.read`, which needs user permission).
- **Property codes:** the verified 4-letter codes used with `getVal`/`getInt` are in [`PROPERTIES.md`](../PROPERTIES.md).
- **Game date and save (core 0.5.0):** `gameDate()` → `{ y, m, d, doy, iso }` or `null` (no save), `saveInfo()` → `{ id, nonce }` or `null`. For data that must be recorded per save, use `api.saveData` (below), or Python `ctx.save_dir()` for caches that can be rebuilt.

Core global functions live in the same script, so call them by name. For exact behaviour the comments in `core/core.js` are the most accurate. The main ones:

| Name | What it does |
|---|---|
| `getVal(obj, 'xxxx')`, `getInt(obj, code)` | Read a property of a game data object (e.g. `getVal(club, 'Tfrm')`). If the object is not a club/person data object it throws, which prevents a game crash |
| `lookup(map, idx, vt)` | Take an object out of an address book by number and confirm it is still the same object. `null` if absent |
| `clubs`, `persons`, `staff` | Address books (number → object address). Usable after `mapsReady` |
| `linkIds(text)` | Unpacks the links in a text into `[{name, type, idx}]` |
| `newsBody(news)` | Body of a news article (`''` on failure) |
| `myInfo()` | My manager's name and club `{mgr, co, club, full}` (only `mgr` when unemployed, `null` if unknown) |
| `fanClub(uid)` | A fan's unique ID → supported team `{uid, name, full, mine}` |
| `clubManagerObj(idx)`, `personName(id)`, `personForm`, `topPlayer`, `clubExtra`, `clubSituation`, `mainPosition` | Read manager, name, form, key player and club information |
| `setStr(dst, str)` | Replace a social panel's text slot with a new text |
| `refreshPanel(th)` | Redraw a panel. **Only on the screen thread** (inside `socialPanel` / `frame` callbacks) |
| `hash64(s)`, `dbg(msg)`, `B` (base address of fm.exe), `uiTid` (screen thread number) | Helpers |

> This list is still "core global functions exposed as they are". Names and shapes may be reorganised into `api.*` during `0.x`. For a feature that needs a new game address, putting a signature in the mod's `builds/` rather than in the core is recommended (section 6).

### Match engine tables (core 0.31.0, capabilities `read.engine` · `write.engine`)

- `api.engine.dump(table)`: reads the match-engine tables from game memory as they are. Tables are `'weights'` (selection weights), `'physics'` (player physics), `'momentum'` (match flow), `'ratings'` (match ratings), (core 0.32.0) `'styles'` (tactical styles: the range from which the AI manager picks team instructions and tendencies per style, `tactics/styles.xml`).
- `styles` is loaded **on the first matchday** after the game loads a save. Before that it is `{error}`, and it is loaded again when the language changes (`key` changes).
- (core 0.33.0) `'xg'`: per-version and per-shot-type coefficients and intercepts of the xG model (`expected_goals/models`) (f32 = JSON ÷ 1e7). `spec = {models: [{ver, coef?, icpt?}]}` writes only to existing lines and only when the number of coefficients matches. `spec = {styles: [{folder, attr?, tend?}]}` replaces the whole list of that style, and if slots grow the core creates a new buffer that the game may free later.
- `api.engine.write(table, spec)`: writes only to existing slots. While the game is running it returns `{error}`. It takes effect from the next selection/match and is not stored in the save.
- What to write is decided in Python with `pylib/m24engine.py`: reading engine packs (.json/.jsb), reading the original `simatch.fmf` (`load_game_original(ctx.game_dir())`), and `plan(pack, original, memory)` → a write list and warnings.
- A real example is `mods/dynamic-me`: JS only reads and writes, Python makes the plan.

### Reading game properties (core 0.36.0, capability `read.prop`)

Mods use the same **4-letter property codes** the game screen uses to ask for values. The core has a registry (`core/properties.json`, about 2,300 codes) made by asking every code of 16 kinds of game object (team, club, national team, player, staff, human manager, competition, award, and since 0.39.0 nation, stadium, city, continent, media, contract, loan, injury). List and meanings: [PROPERTIES.md](../PROPERTIES.md).

```js
// mod.json "capabilities": ["read.prop"]
var rank = api.prop('myteam', 'TpoN');                 // league position
var money = api.props('myclub', { re: '^Cc' });        // club finance codes {code: value}
var opp = api.deref(api.prop('myteam', 'Topp'));       // next opponent team object
if (opp) api.log('next opponent position ' + api.prop(opp, 'TpoN'));
api.log(JSON.stringify(api.propInfo('Pced')));         // { code: 'Pced', t: 'date', k: ['player','staff','human'] }
```

- Target: an object pointer (any slot of a player object works) or `'me'`, `'myteam'`, `'myclub'`, `'myjob'` (my manager's contract), a person reference `'p123'`/`'s45'`, `'team:<number>'`, `'comp:<number>'`.
- Value: integer, float, text, `true/false`, date `'2038-06-30'`, colour `'#rrggbbaa'`, record `{key: value}`, list `[...]`. Another object is `{dref: number}` → `api.deref`.
- Read-only. They are values the game screen shows, so it is safe, but for a code without a meaning (`ko`) in the registry, check the meaning of the value yourself.
- (core 0.40.0) **League match results**: `api.leagueResults('myleague')` = the league matches finished since you last called it `[{home, away, homeGoals, awayGoals, date}]` (including matches that are not reported; [NEWS.md](../NEWS.md)).
- (core 0.41.0) **Game commands (actions)**: `api.actionsFor(target)` = the list of commands the game menu shows for that target (capability `read.action`), `api.action('SUBS', target)` = run one (capability `game.action`; it changes the save, so user permission, 10 per minute, logged by the loader). Only commands the game shows, with the arguments the game builds. For a command that goes through a confirmation dialog (assigning a captain, `PmcP`), pass the post-confirmation event (`confirm` in the registry): `{event: 'pmcC'}`, applied at the next day's processing. Commands with an empty handler (screen-navigation LINKs, resignation, etc., `canRun: false`) cannot be run. Targets: person, team, club, competition. Python mods: `ctx.actions_for(target)` / `ctx.action(id, target, event=None)`. List and events: [ACTIONS.md](../ACTIONS.md).
- Python works too (core 0.39.0): `ctx.props('myclub', '^Cc')`, `ctx.prop('myteam', 'TpoN')`. An object address (`String(ptr)`) sent by JS with `api.send` also works as a target. Handy for collecting values to put in an AI prompt directly in Python.
- When developing: `cli.py props myteam ^T` (all values), `cli.py prop-find me 2038-06-30` (find a code by value), `cli.py prop-info position` (list without the game).
- `api.props(target)`, which reads about 1,000 values at once, takes 0.5–1 s. Narrow it with `re` or `codes`.

### Inbox mail (core 0.34.0, capability `ui.inbox`)

Puts one mail into the game inbox. It is the game's "message between managers" kind, so it shows in the list as **"Sender says: Title"**.

```js
// mod.json "capabilities": ["ui.inbox", "read.me"]  (it stays in the save, so user permission is needed)
var p = personByName('Jaume Munill');                      // sender: staff or players work too (my manager if none)
api.inbox.send({ title: 'Fitness report this week', body: 'Boss, no players are at high injury risk.', from: p && p.person })
  .then(function (r) { if (!r.ok) api.log('mail failed: ' + r.error); });
```

- The recipient is my manager. The manager must be in charge of a team (`{ok: false}` if unemployed).
- Title up to 200 characters, body up to 8000. Up to 10 per minute.
- **It stays in the save and cannot be undone.** After saving, it is still there when reloaded. The user can delete the mail in the game.
- Sent mail is recorded in the app's mod log.
- The mail's "Reply" button does nothing when pressed (it is a feature for online games).
- It is inserted on the screen thread. You may call it from any thread; the result comes as a Promise.

### In-game panels (core 0.23.0, capability `ui.panel`)

Use this to show an FM-style dialog inside the game so the user can choose or be informed. A mod does not write game panel XML; it only writes a **form**. The core generates the XML, writes it to a panel slot in the FM user folder (`Documents\Sports Interactive\Football Manager 2024\panels\m24ga\slot01~08.xml`) and shows it as the game's ordinary dialog. It does not use skin files, so it is the same on any skin.

```js
if (!api.panel.available()) api.log('In-game panels are not usable yet (restart the game)');
var p = api.panel.open({
  title: 'Manager playing career', text: 'Choose your playing career',
  fields: [
    { id: 'club', type: 'text', label: 'Club played for' },
    { id: 'year', type: 'number', label: 'Retirement year', min: 1970, max: 2035 },
    { id: 'intl', type: 'check', label: 'International', value: true },
    { id: 'pos', type: 'select', label: 'Position', options: [{ value: 'GK', label: 'Goalkeeper' }, { value: 'FW', label: 'Forward' }] },
    { type: 'label', label: 'A line of guidance' }
  ],
  buttons: [{ id: 'apply', label: 'Apply' }]      // the core always adds a close button (change its text with closeLabel)
}, function (ev) {                                // called on the screen thread. Keep it short!
  if (ev.id === 'apply') api.log(JSON.stringify(ev.values()));   // { club, year, intl, pos }
  if (ev.id === 'close') api.log('closed');
});
if (!p.ok) api.log(p.error);
```

- Event `ev.id`: a field or button id, or `'open'` (shown), `'close'` (closed), `'error'` (could not show, `ev.error`). `ev.kind`: `button`, `change` (per character), `check`, `select`. `ev.value` = that field's current value.
- Values: `p.get(id)`, `p.values()`. number is a number (null if out of range), select is the option's value, check is true/false.
- **Person and club search fields (core 0.29.0):** field types `person` and `club` are the game's own search fields. As you type, the game shows candidates (name, position/job, club); when one is picked, `ev.kind === 'pick'`, `ev.value = { type, ref | uid, name, age, club, role, label }` arrives and the window is redrawn showing "Now: …" (other field values stay). In `values()` it is the picked one, the typed text `{ text }` if none was picked, or null if neither. If you give `{ ref }` (person) or `{ uid }` (club) as a field's `value`, it shows "Now: …" from the start. To avoid redrawing after a pick, set `refreshOnPick: false` on the form. A select field also opens with that item chosen if you give it a `value`.
  ```js
  { id: 'mentor', type: 'person', label: 'Mentor', value: { ref: 'p95264' } },
  { id: 'fav', type: 'club', label: 'Favourite club' }
  ```
- Close with `p.close()`. When a mod is unloaded the core closes its panels. Up to 8 at a time.
- It is not opened while the game is running (`error`). Open it on a paused screen.
- **The first time:** after the loader first creates the panel slot files, the game must be restarted (the game reads the file list when it starts). If `api.panel.available()` is false, this is the case.
- Example: `examples/panel`.

### In-game JS ↔ Python messages (since core 0.2.0)

JS and Python exchange **messages** instead of files. No polling and no file locks are needed.

```js
// mod.js
api.recv(function (m) { if (m.t === 'answer') use(m.text); });
api.send({ t: 'question', q: '...' });
```
```python
# python/main.py
def run(ctx):
    while not ctx.stop.is_set():
        m = ctx.recv(0.5)                      # wait 0.5 s to receive one (None if none)
        if m and m.get("t") == "question":
            ctx.post({"t": "answer", "text": "..."})
```

- `ctx.recv(timeout=0)`: 0 does not wait, a number waits that many seconds, `None` waits until one comes. The inbox holds up to 20,000 and drops the oldest when it overflows.
- `ctx.post(obj)` returns `False` when the game is not attached or the script is unloaded, and **that message is dropped**. So **design assuming messages can be lost.**
  - When the game side loads, send a message like `hello` first so Python sends the state it needs (cache, settings) all at once. The script is reloaded every time a mod is turned on or off, so this sequence happens each time.
  - If a request sent by JS gets no answer, have JS remember it and resend it when Python announces "ready". Make Python tolerate the same request twice (the social feed has a key per request: for a key already made it only resends the result, and for a key being made it skips).
  - Messages JS sends while Python is not up yet are queued by the host and can be handed over when Python starts (Python starts before the loader loads the JS script).
- The messages the social-feed mod uses are in `mods/ai-social-feed`'s `mod.js` and `python/bridge.py` (the comment above `main`). Use them as a reference when designing.

## 5. The PC-side part (Python)

If you put `run(ctx)` in the file `python` in `mod.json` points to, the loader calls it **in a thread when the mod is turned on** (it also runs while the loader waits for the game).

```python
def run(ctx):
    ctx.log("started")
    while not ctx.stop.wait(1.0):     # leave immediately when told to stop
        ...                           # work to do

def status():                          # optional. When the app asks for the mod state
    return {"ticks": 1}

def ui_hello(name):                    # optional. From the mod window: m24.call('hello', 'name')
    return "Hello, " + name
```

- `ctx.id`, `ctx.data_dir` (data folder), `ctx.stop` (`threading.Event`), `ctx.log(msg)` (`[<id>] msg` in loader.log), `ctx.settings()` (settings dict, read from the file on each call), `ctx.game()` (core 0.5.0, `{"date": "2035-04-25", "save": {"id", "nonce"}}`, None if the game is not attached), `ctx.save_dir()` (core 0.5.0, a folder for the current save `<data folder>/saves/<save id>/`, None if there is no save), `ctx.game_dir()` (core 0.31.0, the install folder of the attached game = the fm.exe folder, for reading original game data), `ctx.save_data()` (core 0.44.0, see "Per-save mod data").
- When you turn the mod off or stop the loader, `ctx.stop` is set. **Finish within 15 seconds.** If `run` raises an exception, the loader **restarts** it after 2 seconds, and after 3 failures within 60 seconds it **turns the mod off automatically** (section 10). So handle temporary errors (network, …) yourself inside `run`. When it cannot run because a user setting is missing (no API key, …), do not raise; wait with `ctx.stop.wait(2.0)` (the social feed does it this way).
- Other `.py` files in the same folder are simply `import`ed (the folder with the entry file goes on `sys.path`). A `.24mod` is unpacked on turn-on into `~/m24ga_data/cache/<id>-<version>/`, **only the folder that holds the entry file (`python/`)**, and only re-unpacked when the zip changed.
- If **module names collide** between mods (e.g. both have a `config.py`), the mod turned on later is blocked. Put the mod name in the name or put them in a package (folder).
- Bring pure-Python libraries inside `python/`. The distribution exe only includes common packages. If one is missing, announce it with `requires`.
- **Shared library `pylib/` (core 0.18.0):** libraries shared by several mods are in M24GA's `pylib/`, and the loader puts them at the end of `sys.path` (the mod's own modules come first). Currently: `dpa` (FM24 Dynamic PA 0.9.5 model and save-file reading, GPL-3.0, do not modify), `m24hist` (from the save file, league records of the past 2 seasons → comparison-group percentiles, cached: `m24hist.load(save_id, evaluation_date, dpa.rules.validate(dpa.rules.DEFAULTS), cache_path, ctx.log)` → `(prior, current, info)`). Mods that use it need `core` `>=0.18.0`. Core 0.19.0: `m24awards` (all-time award winners and competition winners from the save: `m24awards.load(save_id, cache)` → records `[(year, award number, [(rank, person number, team number)])]`, `by_person(records)`, `load_trophies(save_id, start_year, cache)`, about a minute; core 0.20.0: best elevens and league history parsers). Core 0.22.0: `m24career` (career events per person: `m24career.load(save_id, cache)`, `.of(list number, kind)`, `.transfers(number)`, `.finals`, `.loans`, `.league_finishes`, `.awards`, `.iter_kind(kind)`; about a second). Sources: `pylib/NOTICE.md`.
- **Secrets such as API keys are recommended not to go into the settings file.** A `password` item is not sent to the screen but is stored in the file as it is. The social feed keeps the key in a separate file (`~/.deepseek_key`) and puts only the file path in the settings.

## 6. Game builds and addresses

When the game is updated its code addresses change. So before loading, the loader compares the code bytes and values of the running `fm.exe` with **signatures**.

- Core addresses are held by the loader's `builds/*.json`. If they do not match, **the whole loader** loads nothing. Two builds are defined at present: FM24 Epic (2026-10-24 file build) and FM24 Steam 24.4.2.
- If a mod uses an address the core does not have, put `builds/<build>.json` inside the mod. **If it does not match, only that mod** is turned off (the app shows "Turned off for this game build").

```json
{"build": "FM24 Epic, fm.exe 2026-10-24 build",
 "sig": {"0x61ae80": "0100004889ce31d2e85362b00084c00f"},
 "vt":  {"0x56cc008": "64c350"}}
```

- `build`: the same text as the `name` of the core build file. If the mod's `builds/` has any signature with a `build` but none for the current build, that mod is turned off.
- `sig`: offset from `fm.exe` → the 16 bytes at that spot (lowercase hex). `vt`: the pointer value at the offset minus the `fm.exe` base address (hex).
- For a spot inside a function that you hook with `Interceptor`, compare the bytes before the hook overwrites them, or use the 16 bytes after the hook as the signature.
- The loader reports a build it does not know with a build diagnostic report (app home screen, "Copy build diagnostic report").

## 7. The mod window (ui)

The HTML you give in `ui` appears inside the app's **mod-window tab**. For security it runs in a `sandbox="allow-scripts"` iframe, so it cannot directly access the app screen, files or other mods. There is only one way to talk to the mod:

```js
const r = await m24.call('greet', 'Minsu');   // → the mod's Python ui_greet('Minsu')
m24.toast('Saved');                           // a toast at the bottom of the app
```

- `m24.call(name, ...args)` calls the mod Python's `ui_<name>(*args)` (only `[a-z][a-z0-9_]*`; only functions with `ui_` in front of the name are called). Arguments and results travel as JSON. An exception arrives as an `Error`.
- It opens only while the mod's Python part is running (if the mod is off or the loader is off a notice is shown). It opens automatically the moment it turns on.
- The loader injects a **theme CSS**. Colours are variables: `--bg --card --blue --text --text2 --text3 --line --grey --red --amber ...`. Common classes: `.card`, `.card.list`, `.row` (`.name` `.hint` `.val`), `.stats`/`.stat` (`.label` `.value`), `.btn` (`.primary` `.ghost` `.grey` `.wide`), `.field` (input line), `.switch`, `.seg`, `.pill`, `.badge`, `.sec-title`, `.empty`, `.cmt`. All are in `loader/ui/theme.css`.
- **Insert text made by a mod only with `textContent`** (with `innerHTML`, HTML inside the text would run as it is).
- The font (Pretendard) is loaded from the internet, and Malgun Gothic is used if unavailable. Avoid other external addresses where possible.

## 8. Where user data lives

```
~/m24ga_data/
  enabled.json              {mod id: true/false}
  loader.log                record of the loader and scripts inside the game
  cache/<id>-<version>/     where the Python part of a .24mod is unpacked
  <mod id>/                 mod data folder (settings.json, …)
  savedata/<save id>/<mod id>/   per-save mod data (core 0.44.0)
  trash/                    .24mod files deleted in the app or replaced by a new version (move them back to the mods folder to restore)
Documents\M24GA\mods\       where you put .24mod files
```

## 9. Order of building and checking

1. Create a skeleton with `python -X utf8 tools/m24.py new <id>` (or copy `examples/hello` and change the `id` first).
2. Check with `python -X utf8 tools/m24.py validate <folder>` (until there are 0 errors).
3. Put the folder as it is in the mods folder and press **Refresh** in the app (for a `.24mod`, pick it with the **Install mod** button at the bottom left of the app and it is installed after validation; if the same id exists it is replaced by the new version and the old file goes to `trash/`; to delete, use **Delete mod** on the mod's info tab; a development-folder mod is not deleted by the app) → the mod appears in the list. `mod.json` errors show on the app home screen (red notice) and in `loader.log`.
4. You can check from a terminal (at the repository root):
   - `python -X utf8 loader/host.py --list`: found mods and their state
   - `python -X utf8 loader/host.py --check`: attach to the game and only check the build
   - `python -X utf8 loader/bundle.py out.js` then `node --check out.js`: syntax-check the bundled JS
5. Check in the game, and when everything works make a `.24mod` with `tools/pack_mod.py`.
6. For a mod that reads game data, build **reading first**. Features that write to game memory need a user permission (see "Writing game values").

## 10. Safeguards: automatic turn-off and safe mode

Even if a mod misbehaves, the loader protects the game and other mods. Mod authors only need to know that these things can happen.

| Situation | What the loader does |
|---|---|
| **Syntax error** in `mod.js` | Before loading, it syntax-checks each mod and leaves out only that mod. The core and other mods keep working |
| `mod.js` **throws while loading** (load failure) | It withdraws everything that mod registered and turns it off automatically |
| A game-side callback (`socialPanel`, `frame`, `api.recv`) **throws more than 25 times in 5 seconds** | The core stops calling that mod's callbacks (the game and other mods are unaffected) and turns it off automatically |
| Python `run(ctx)` **ends with an exception 3 times within 60 seconds** | It restarts after 2 seconds up to twice, and turns the mod off automatically on the third |
| The game **crashes** (exit code `0xC...`, e.g. `0xC0000005`) while mods were loaded | On the next start, **safe mode**: it starts without loading mods. A notice appears on the app home screen, and you can turn mods on **one at a time** to find the cause. When you think it is fine, "End safe mode and turn all mods on" |

- A mod that was turned off automatically is shown in the app as **"Turned off automatically"** with the reason and time. When the user turns it on with the switch or the **Turn on again** button, the record is cleared and it is tried again. The record is `~/m24ga_data/autodisabled.json`.
- Safe mode is applied **only once** after a crash. Crash records are in `~/m24ga_data/session.json` and `crashes.json`. It is not applied when the exit code is unknown (for example the loader was closed first) or when the game crashed while no mod had ever been loaded (it is not the mods' fault).
- A game crash may be caused by the core or the game itself rather than a mod. If it crashes even in safe mode, it is not the mods.

### Per-mod log tab

When you open a mod in the app there is a **Log tab**. It shows that mod's records with time and source (**JS** = `api.log` and game-side errors, **PY** = `ctx.log` and Python errors with stacks, **Loader** = turning on/off, automatic turn-off, …). When there are errors a red count appears on the tab. You can filter with `Errors only` and use `Copy log` and `Clear`. The latest 500 are kept only while the app is running (the full record is `~/m24ga_data/loader.log`). For a mod with a problem (turned off automatically, Python error) the log tab opens first.

**`Copy report for AI`**: copies the mod state, the reason it was turned off automatically, the `validate` result and the recent log in one go. Paste it to an AI and have it find and fix the cause.

### Writing game values (core 0.7.0, field registry 0.10.0)

The values you can write are the slots marked **write: safe** in [`FIELDS.md`](../FIELDS.md) (a player's potential (PA), a manager's past playing experience value, the **54 player attributes** `player.attr.*` (core 0.42.0): attributes are written as a **stored value 1–100** = screen value × 5, while reading with `getField` gives the screen value 1–20; and the contract wage fields `player.contract.wage`, `staff.contract.wage`, `human.contract.wage`). `api.setField(obj, 'name', value, { expect, reason })` → `{ ok, before, after, name, error }`. `obj` is a game object or the key of its kind (a UID for a player). PA can also be written with `api.setPlayerPA(uid, pa, { expect, reason })` as before (same checks and record).

- Each slot has a capability it needs (default `write.field`, PA is `write.player.pa`). You must declare it in `mod.json`, and the user must allow it in the app for the mod to turn on. A mod that calls without declaring gets `ok: false`. `validate` reports a non-existent field name and writing to a read-only slot as errors.
- What the core checks: that a save is loaded; that it is the same object (the kind's key and the `check` slot are unchanged before and after the write, for players the UID and date of birth); the type range and the slot's `range` (PA 1–200); `gte`/`lte` (PA **not lower than CA**); only integers for integer slots; if you gave `expect`, that the current value is that value; and no more than 600 per minute per mod. If any fails it does not write and returns the reason in `error`.
- Every write is recorded in `~/m24ga_data/writes.jsonl` (mod, player, before → after, save, game date, `reason`) and also in the mod log tab. The app's mod info tab has a **Game value write log** and a button **Undo values this mod changed in this save**. Undo goes from the latest, **only when the current value is the value the mod wrote** (values changed afterwards by the game or another mod are not touched).
- **When you save the game, the changed values stay in the save file.** After undoing, you must save again. Tell the user to copy important saves beforehand.
- For a person data object, get the UID with `personUid(o)` or `playerInfo(playerOf(o)).uid`.

> If you need a value or function that is not in the registries, add one line to `core/fields.json` / `core/functions.json` following the procedure in [`EXTENDING.md`](EXTENDING.md).

### Per-save mod data (core 0.44.0)

Put mod data that is kept per save (per-player records, career progress, …) in `api.saveData`. Declare the capability `save.data` (no user permission needed).

```js
if (api.saveData.ready()) {
  var wins = api.saveData.get('wins', 0);
  api.saveData.set('wins', wins + 1);
}
```

- It is **committed when the game is saved** (`~/m24ga_data/savedata/<save id>/<mod id>/<key>.json`, only the changed keys).
- **If you reload the same save without saving**, it goes back to the value at the last save; **if you load a different save**, to that save's value. Even if you roll the save back, the mod's records and the game do not get out of step.
- Only JSON-serialisable values; up to 64 MB per value and 128 MB per mod. A key is 1–200 characters. **A value larger than 256 KB is PC-side (Python) only** (absent from JS `get`): handle large records in Python.
- `ready()` is true when a save is loaded and the data is ready. When the save changes the data changes after the `saveLoaded` event.
- The same mod's Python sees the same data with `ctx.save_data().get/set/delete/keys/all`.
- Data written directly to `ctx.save_dir()` (the per-save folder), as before, does not follow save/undo. Move data whose rollback matters to saveData. (DynamicPA 1.2.0 and the Manager Career mod 0.7.0 were moved this way; they import their old files once on first read.)

### Writing by property code (core 0.42.0)

Of the 4-letter codes you read with `api.prop`, those whose writes are verified can be changed with `api.setProp`. It does not edit memory slots directly but calls **the game's own setter** (the same path as editing on screen), so the game handles clamping and change notifications.

```js
api.setProp('myclub', 'Ctfc', 300000000, { reason: 'extra board budget' }).then(function (r) {
  if (!r.ok) api.log('failed: ' + r.error); else api.log('transfer budget ' + r.before + ' -> ' + r.after);
});
api.propInfo('PCAB').writable   // 'safe' | 'tested' | 'deny' | false
```

- Writable codes: the "Writing" section of [`PROPERTIES.md`](../PROPERTIES.md). The **56 `safe`** ones (finances, facilities, a player's CA/PA/reputation/hidden traits/height/weight/morale/match sharpness, team and competition reputation, staff attributes, contract expiry, …) work as they are; the **221 `tested`** ones (only checked with +1 and undo plus a side-effect check) are written only if you pass `{ tested: true }`.
- Target: the same as `api.prop` (`'me'`, `'myteam'`, `'myclub'`, an object, `'p123'`). The record key is the target's dref, so undo works even after reloading the game.
- Integers, booleans, floats and dates work. A date code is written as `'YYYY-MM-DD'`, and the result's `before`/`after` are date text too.
- **Contracts**: targets `'contract:p123'` (a player), `'contract:s45'` (a staff member's current-club contract) and `'contract:me'` (= `'myjob'`, my manager) read and write contract properties (expiry `Ceda`, …). The wage is not accepted by the setter, so write the fields `player.contract.wage`, `staff.contract.wage`, `human.contract.wage` with `api.setField` (internal units, same as the property `Cwwa`).
- Several at once: `api.setProps('myclub', { Ctfc: 3e8, Cwwb: 9000000 }, { reason })` → Promise `{ok, results, error, rolledBack}`. If any fails, what was changed before is undone in reverse (the undo is recorded too). Python `ctx.set_props(target, {code: value})`.
- It checks the range (`range`) and relations (PA not below CA, CA not above PA); if the game clamps the value differently it restores the original and returns `ok: false`. If the game replaces the object during the write (codes like the person-type `Ptyp`, which the registry blocks) it reports failure.
- It runs on the screen thread, so it is a Promise. Recording, undo and the 600-per-minute limit are the same as `setField`. **When saved, it stays in the save.**
- Python mods: `ctx.set_prop('myclub', 'Ctfc', 300000000, reason='...')` (declare capability `write.prop`).
- New codes are opened with the **semi-automatic discovery** commands (`cli.py cand`, `verify`, `promote`) on a test save: [`EXTENDING.md`](EXTENDING.md) section D.

### Hooking game functions (core 0.11.0)

Hook game functions registered in [`core/functions.json`](../../core/functions.json) (list in [`FUNCTIONS.md`](../FUNCTIONS.md)). Declare the capability `hook.function` and get user permission.

```js
var h = api.hook('player.updateAskingPrice', {
  before: function (ev) { ev.data.t = Date.now(); },                       // just before the function is called
  after: function (ev) { api.log((Date.now() - ev.data.t) + 'ms, called from ' + ev.caller); }   // just after the function ends
});
if (!h.ok) api.log(h.error);   // unknown function, core-only function, signature differs from this build
```

- `ev.args` (arguments converted per the `args` format in functions.json), `ev.raw(i)` (the original pointer, including arguments beyond the registered ones), `ev.caller` (`'fm+0x...'`), `ev.tid`, `ev.data` (a slot to pass from before to after), and in after `ev.ret`.
- **Hooking: modify** — only functions verified as modify allow `ev.setArg(i, v)` (before) / `ev.setRet(v)` (after). Calling them on an observe function is an error (`validate` warns).
- The core attaches **only one** per function and shares it among mods. One mod's callback error is contained within that mod (if repeated only that mod is turned off), and unloading the mod detaches it automatically. When the last mod detaches, the hook is released. You can also detach yourself with `h.stop()`.
- Callbacks are called on a **game thread**. If they take long the game slows down, so keep them short and hand heavy work to Python with `api.send`. The CLI `hooks` shows per-mod call counts, errors and time taken.
- A function the core has already hooked (`owner: core`, e.g. every frame) cannot be hooked. Use an event such as `api.on('frame')`.
- Attaching `Interceptor` directly to an unregistered function (`raw.hook`) still works, but there is no signature check, cleanup or error isolation. Register a function you found in functions.json before using it (how to find: CLI `watch-write` and `watch-call`, [`CLI.md`](CLI.md)).

## 11. The capability registry and permissions (core 0.4.0)

The capabilities the core opens to mods are registered one by one in [`core/capabilities.json`](../../core/capabilities.json) (human-readable list: [`CAPABILITIES.md`](../CAPABILITIES.md)). Each capability has a name, a **risk level** and the game builds it supports.

- A mod lists the capabilities it uses in `mod.json`: `"capabilities": ["event.socialPanel", "read.data", "ui.social.text"]`.
- `validate` finds the capabilities actually used in `mod.js` and reports an **error if you use one without declaring it**, an error for an unknown name (with a similar-name suggestion), and a warning if `capabilities` is absent altogether (it tells you the list to put in).
- The loader treats **the declared ones plus the ones found in the code** as the mod's capabilities.
  - `read` (reading) and `ui` (screen text): just turn on.
  - `pc` (the Python part, files), `raw` (direct reads such as `ptr`, `.readU32`, `NativeFunction`), `hook` (`Interceptor`) and `write` (memory writes): **turn on only when the user allows them in the app.** Before permission it is shown as "Permission needed", and the info tab says what the capability does. If a new version uses more risky capabilities, it asks again.
  - If a capability does not work on the current game build, only that mod is turned off as "Does not match this game build" (it also says which capability is the problem).
- The permission record is `~/m24ga_data/permissions.json`. When a mod is deleted in the app, its permissions are deleted too. When 0.4.0 was first installed, the capabilities of the mods that were on at the time were recorded once as allowed (so mods in use did not suddenly turn off).
- **This is not a sandbox.** The mod JS runs in the same script as the core, and Python runs on the PC as it is. Finding capabilities is done by text shape, so deliberate hiding is not detected. The purpose is to inform the user and get consent, and to tell mod authors and AIs exactly which capabilities are available.
- When the core gets a new capability, it is added to the registry first. A capability not in the registry does not exist in the core.

## 12. Trust and licence

- A mod **runs arbitrary code** in game memory and on the user's PC. Install only mods from sources you know. If you distribute a mod, describe in its description what it does.
- The M24GA core is **GPL-3.0-or-later**. Because a mod runs in the same script as the core code, mods are recommended to use a GPL-compatible licence too. (This is not legal advice. If unsure, check the licence yourself.)
