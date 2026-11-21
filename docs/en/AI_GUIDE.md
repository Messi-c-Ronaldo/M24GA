# M24GA AI Modding Guide

[한국어](../AI_GUIDE.md) | **English**

This document is for **people who ask an AI to build a mod** and for **the AI that builds it**. It is shorter than the reference ([MODDING.md](MODDING.md)) and focuses on "what works, what doesn't, and how people get it wrong".

Written for core version **0.44.0**. The core is still 0.x, so function names may change.

---

## 1. For humans: how to instruct the AI

Paste the text below into an AI (Claude Code, Cursor, ChatGPT, …) and fill in only the `<...>` parts. Change the paths if your M24GA folder is somewhere else.

**Creating a new mod**
```
Build a mod for M24GA (an FM24 mod loader).
1. Read C:\Program Files\Epic Games\M24GA\docs\en\AI_GUIDE.md to the end.
2. Create a skeleton with
   python -X utf8 "C:\Program Files\Epic Games\M24GA\tools\m24.py" new <mod id> --dir "<folder to create the mod in>" [--python] [--ui]
   and start from it. (--python = needs PC-side processing, --ui = needs a window inside the app)
3. The mod I want: <describe it in detail>
4. If I need something the core does not have, do not invent it. Tell me it does not exist yet.
5. After every change run tools\m24.py validate until there are 0 errors, and show me the result.
```

**Changing an existing mod**
```
Change the M24GA mod in this folder. First read the AGENTS.md in this folder and the AI_GUIDE.md it points to.
What I want changed: <what you want>
After changing it, run validate and bring the errors down to 0.
```

**When something does not work**, open the mod in the app, go to the **Log tab → "Copy report for AI"** and paste it to the AI. It contains the mod state, why it was switched off automatically, the `validate` result and the recent log (including error stacks) in one go. Hand it over and say "find the cause and fix it". (The report contains the path of the mod folder on your PC.)

---

## 2. For the AI: working rules

1. **Do not guess.** A function or item that is not in this document, [`types/m24ga.d.ts`](../types/m24ga.d.ts) (game-side JS), [`types/m24ga.pyi`](../types/m24ga.pyi) (Python) or [`examples/hello`](../../examples/hello) **does not exist.** Do not use it because it "might" exist.
2. **Build small and validate every time.** Do not write everything at once: skeleton → reading → UI/settings → polish, and run `validate` at each step.
3. **Trust the validator output and fix accordingly.** Each `[error]` from `validate` comes with a location and a "how to fix". Fix until there are 0 errors. For warnings, read the reason and fix only what is needed.
4. **Be honest when asked for something that is not possible.** If it is in the "Not available" list in section 4, answer that "the core does not have it yet, so a mod cannot do it" and suggest an alternative. Do not write code that pokes game memory by force.
5. **Protect the game.** Read a game object only after confirming it with `lookup`, wrap game-side code in `try/catch`, and on failure **change nothing** and move on. A single wrong address crashes the game.
6. **Declare the capabilities you use.** Find the capability name in [`CAPABILITIES.md`](../CAPABILITIES.md) and list it under `"capabilities"` in `mod.json`. `validate` reports an error if you use one without declaring it. `read`/`ui` capabilities just turn on, but `pc` (Python), `raw` (direct reads such as `ptr`, `.readU32`), `hook` (`Interceptor`) and `write` (memory writes) **only turn on after the user allows them in the app.** If a core function can do the job, use the core function.
7. **Ask the user when unsure.** Ask first, in particular, when it is unclear "which text on which screen" they want to change.

---

## 3. File layout and rules

```
<mod folder>/
  mod.json          name, version, settings items (the settings screen is generated from it)
  mod.js            JS that runs inside the game (Frida). Do not use registerMod
  python/main.py    PC side (optional): run(ctx) and ui_name() functions
  ui/index.html     window inside the app (optional). Only calls Python's ui_name() via m24.call('name')
```

**mod.js (game side)**
- `api` and `DIR` already exist. You cannot use `registerMod`, `require`, `import`, `document`, `window` or `fetch`.
- **Always declare variables with `var`** (assigning without `var` overwrites variables of the core or other mods).
- Log with `api.log('...')`. `console.log` is not shown.
- Callbacks called from the thread that draws the screen (`socialPanel`, `frame`) **must finish quickly.** Hand slow work to Python with `api.send`.

**python/main.py (PC side)**
- Define `def run(ctx):` and keep working until `ctx.stop` is set (`while not ctx.stop.is_set():`). It must finish within 15 seconds after being switched off.
- Do network calls (AI APIs, etc.) and file work here. Log with `ctx.log('...')`.
- Settings are `ctx.settings()["key"]`. They are read from the file on every call, so a change made in the app takes effect immediately.

**mod.json**
- Settings item types: `bool`, `int`, `number`, `text`, `password`, `select`. Details in [MODDING.md section 3](MODDING.md) and [`mod.schema.json`](../mod.schema.json).
- If you put `"$schema": "<path to mod.schema.json>"` at the top of `mod.json`, the editor gives autocompletion and error markers (new mod skeletons already have it).

**ui/index.html (mod window)**
- Draw the screen by asking Python's `ui_name(args...)` with `m24.call('name', args...)`. The `ui_` function name and `m24.call('name')` **must match exactly**.
- Insert text **only with `textContent`** (no `innerHTML`; if text made by a mod or an AI contains HTML it would run).
- The loader injects the app's look (`.card`, `.btn`, `.stat`, `.field` …) automatically.

---

## 4. What exists / what does not

**What exists** (core 0.44.0; names and risk levels in [`CAPABILITIES.md`](../CAPABILITIES.md))

| What you want | How |
|---|---|
| Read social-feed text | `ev.text`, `ev.type` of `api.on('socialPanel', ev => ...)` (0 title, 2·4 fan comments, 3·5 official posts) |
| Change social-feed text | `setStr(ev.dst, 'new text')` then `refreshPanel(ev.th)` (**only inside the callback on the screen thread**) |
| Read game data of clubs, players and managers mentioned in the text | `linkIds(text)` → `lookup(clubs/persons/staff, idx, VT)` → `getVal` / `getInt` (field table in section 5) |
| A player's current ability (CA), potential (PA) and date of birth | `playerInfo(playerOf(lookup(persons, idx, PERSON_VT)))` (all players: `playerUids()` + `playerByUid`) |
| A player's season stats (per competition), xG, positions, traits, league | `playerSeason(p, 'league')`, `playerSeasonDetail(p)`, `playerPositions(p)`/`playerPosition(p)`, `playerTraits(p)`, `playerTeam(p)` (p = `playerByUid(uid)`) |
| The 54 player attributes (technical, mental, physical, GK, hidden, feet) | `getField(p, 'player.attr.crossing')` … (1–20, list in [`FIELDS.md`](../FIELDS.md) `player.attr.*`), CLI `get player:<uid> player.attr.` |
| Read a property (`getVal`) from a player object | `getVal(personOf(p), 'PCRP')` (core 0.9.0) |
| Read registered game values by name (asking price, season stats, positions, club names …) | `getField(findObj('player', uid), 'player.askingPrice')` (core 0.10.0, `read.field`, list in [`FIELDS.md`](../FIELDS.md), CLI `fields`) |
| Change a game value whose write has been verified | `api.setField(obj, 'player.pa', 150, { expect: 149, reason })` (only entries marked **write: safe** in FIELDS.md, that field's write capability + user permission, logged and undoable) |
| Know when a game function is called / see its arguments and return value | `api.hook('player.updateAskingPrice', { before(ev), after(ev) })` (core 0.11.0, `hook.function`, list in [`FUNCTIONS.md`](../FUNCTIONS.md), CLI `functions`; only modify functions get `ev.setArg`/`ev.setRet`) |
| What class a game object is | `className(obj)` → `'db::ACTUAL_PLAYER'`, `isA(obj, 'db::PERSON')`, `rttiInfo(obj)` (core 0.9.0, `read.rtti`) |
| The thread, current text and author's supported team of a social panel | `panelThread(th)`, `panelText(th)`, `panelFanUid(th)`, find a stored panel again with `panelAt(addr, type)` |
| **Read any game value by its 4-letter property code** (teams, clubs, players, staff, managers, competitions, awards, nations, stadiums, contracts …) | `api.prop('myteam', 'TpoN')`, `api.props('myclub', { re: '^Cc' })`, follow links with `api.deref(v)`, Python `ctx.props('me')` (core 0.36.0–0.39.0, `read.prop`, about 2,300 registered codes in [`PROPERTIES.md`](../PROPERTIES.md)). **If you do not know the code**, use `cli.py prop-find <target> <value>` with a value visible on the game screen; list with `cli.py prop-info <regex>` |
| **Change game values by property code** (club balance, budgets, facilities, player CA/PA/reputation/hidden traits/morale, team and competition reputation, contract expiry …) | `api.setProp('myclub', 'Ctfc', value, {reason})` → Promise, `api.setProps(target, {code: value})` (all or nothing), Python `ctx.set_prop` / `ctx.set_props` (core 0.42.0, `write.prop`, user permission). Writable codes are in [`PROPERTIES.md`](../PROPERTIES.md) "Writing" (56 `safe`; the 221 `tested` ones need `{tested: true}`). Logged and undoable. Dates are `'YYYY-MM-DD'`. Contract targets: `'contract:p123'`, `'contract:s45'`, `'contract:me'` |
| **Per-save mod data** (performance records, career progress) | `api.saveData.get/set` (Python `ctx.save_data()`, core 0.44.0, `save.data`): committed when the game is saved, rolled back when the save is reloaded without saving. Writing straight into `ctx.save_dir()` does not follow that rollback |
| Match results (score), related people/teams of news | `api.on('matchEnded', ev => ...)` (`ev.home/away/homeGoals/awayGoals`), `api.on('newsAdded', ev => ev.refs())` (core 0.37.0, [`NEWS.md`](../NEWS.md)); all league results: `api.leagueResults('myleague')` |
| Game commands (actions): add to shortlist, transfer offers, holiday … | [`ACTIONS.md`](../ACTIONS.md), CLI `actions <regex>`. In a mod: `api.actionsFor(target)` lists usable commands (read.action), `api.action(id, target, {event})` runs one (game.action, user permission), core 0.41.0 |
| List of verified property codes | [`PROPERTIES.md`](../PROPERTIES.md) (only entries with a meaning `ko` were checked against the screen; verify the others yourself) |
| Change a player's potential (PA) | `api.setPlayerPA(uid, pa, { expect, reason })` (capability `write.player.pa`, user permission required, every write is logged and undoable in the app; always check `ok`/`error` in the result) |
| Send a message to the inbox | `api.inbox.send({title, body, from})` (core 0.34.0, `ui.inbox`) |
| The manager and club | `myInfo()` |
| Game date, when the date changes | `gameDate()`, `api.on('dateChanged', ev => ...)` (Python: `ctx.game()['date']`) |
| Tell saves apart, when a save is loaded or saved | `saveInfo()`, `api.on('saveLoaded', ...)`, `api.on('gameSaved', ...)`, Python `ctx.save_dir()` (per-save folder) |
| Periodic work | `api.every(ms, fn)`, `api.after(ms, fn)` (stop automatically when the mod is switched off) |
| The team a fan supports | `fanClub(uid)` |
| A settings screen in the app | `settings` in `mod.json` (JS: `api.settings()` / `api.onSettings(fn)`, Python: `ctx.settings()`. Do not read the settings file directly) |
| A mod window inside the app | `ui/index.html` + Python `ui_` functions |
| PC-side work (internet API, files) | `run(ctx)` in `python/main.py` |
| Game side ↔ PC side communication | JS `api.send` / `api.recv` ↔ Python `ctx.recv` / `ctx.post` |
| Clean up when the mod is switched off | `api.onUnload(fn)`: remove your own `Interceptor`s, `setInterval`s and changed text. The game data tables stay when you switch off and on |
| Apply a change to mod.js right away | App info tab **Reload game side** (no game restart needed; restart the app for Python) |

**When investigating the game (developer tools, not mod code):** `cli.py explore player:<uid>` spreads an object out 8 bytes at a time and shows the class name, text and date of any object a pointer points to (follow with `/+0x130`). `cli.py classes <regex>` searches the game's 10,000+ class names. Register a field you found with one line in `core/fields.json` (with the evidence, or `verified: false` if unsure) and every mod can read it with `getField`. Before registration `raw.read` is needed. `cli.py get player:<uid> player.season.league.` checks registered fields in the running game. For a new field use `cli.py find-field <target>=<screen value> <other target>=<value>` (common field + draft entry); find the game function that changes it with `cli.py watch-write <target> <field>` (save the game first), and look at its arguments and callers with `cli.py watch-call <function|fm+0xaddress>`. Register verified functions in `core/functions.json`. For writing, the **semi-automatic discovery** commands `cand`, `verify` and `promote` collect candidates, verify them on a test save and register them ([`EXTENDING.md`](EXTENDING.md) section D).

**If you need a value or function that is not in the registries**, do not put special-purpose code into the mod; follow the procedure of adding one line to the registry: [`EXTENDING.md`](EXTENDING.md) (find the field → register → verify → open writing; find the function → confirm the arguments → register).

**Not available** (do not assume they exist; when asked, say "the core does not have it yet")
- Writing game values that are not property codes marked `safe`/`tested` or fields marked **write: safe** (for example wages of other contract types, transfer fees, match results)
- Creating new game screens, buttons or menus
- Changing game calculations (match results, transfers, growth …)
- **Events** other than `socialPanel`, `frame`, `dateChanged`, `saveLoaded`, `newsAdded`, `matchEnded`, `gameSaved` (no live in-match events such as goals or cards, no screen changes)
- Reading text on screens other than the social feed (press conferences, the transfer screen …)
- Hooking game functions that are not in FUNCTIONS.md safely (using `Interceptor` directly needs `raw.hook` and has no cleanup or isolation), changing arguments or return values of non-modify functions

---

## 5. Cheat sheet for reading game data

**Order:** `api.prepareData(ev.th)` (build the tables once, 1–2 minutes) → read after `mapsReady` becomes `true`.

```js
api.on('socialPanel', function (ev) {
  try {
    api.prepareData(ev.th);
    if (!mapsReady) return;                       // skip while the tables are being built
    linkIds(ev.text).forEach(function (e) {       // e = { name, type, idx }
      if (e.type === 0x18) {                      // 0x18 = club, 0x01 = person
        var club = lookup(clubs, e.idx, CLUB_VT); // always take it out with lookup (it checks it is the same object)
        if (!club) return;
        var rank = getInt(club, 'TpoN');          // league position; null if absent
        if (rank !== null) api.log(e.name + ' position ' + rank);
      }
    });
  } catch (x) { /* on failure change nothing */ }
});
```

**Known field codes** (only those verified in the social-feed mod work; any other code is unknown here — the full list is in `PROPERTIES.md`)

| Target | Code | Meaning |
|---|---|---|
| Club | `Tomp` | Matches played this season |
| Club | `TpoN` | League position |
| Club | `Tlgs` / `Tlgc` | League goals for / against |
| Club | `Cmxp` | Media predicted position |
| Club | `Tnts` | Net transfer spend (internal game currency) |
| Club | `Tfrm` | Array of recent results (values 0–3, last = most recent; `fanClub()` reverses it so [0] is the most recent) |
| Player/person | `Page` | Age |
| Player/person | `PAap` / `PAcg` | Career appearances / career goals |
| Player/person | `PCRP` | Reputation |
| Player/person | `Pnam` | Name object (`.Pfna` is the common name; `personName()` does it for you) |
| Manager/staff | `Page`, `Nptk`, `Npmm`, `Npde`, `Ncrr` | Age, tactical knowledge, man management, determination, manager reputation |

A value of `null` means the object does not have that property. That is normal, not an error, so skip it. If you do not know what a code means, **do not read it by guesswork**; tell the user.

---

## 6. Common patterns

**Do heavy work on the PC side (AI calls, etc.) and return the result to the game side**

```js
// mod.js
var results = {}, sent = {};
api.recv(function (m) {
  if (m.t === 'res') results[m.k] = m.v;
  if (m.t === 'ready') { for (var k in sent) if (!(k in results)) api.send({ t: 'req', k: k, text: sent[k] }); }   // resend unanswered requests
});
function ask(k, text) { sent[k] = text; api.send({ t: 'req', k: k, text: text }); }
api.send({ t: 'hello' });                          // right after connecting; Python answers with ready
```
```python
# python/main.py
def run(ctx):
    while not ctx.stop.is_set():
        m = ctx.recv(0.5)
        if m is None:
            continue
        if m.get("t") == "hello":
            ctx.post({"t": "ready"})
        elif m.get("t") == "req":
            ctx.post({"t": "res", "k": m["k"], "v": "result: " + m["text"]})   # call an AI API etc. here
```

The key point: messages **can be lost** (they are dropped when the game is not attached or the script is being reloaded). So align state with a `hello` → `ready` handshake, resend requests that have no answer, and make Python tolerate receiving the same request twice. A real example is `mods/ai-social-feed`.

**Letting the game-side JS use a setting value**: the settings file is read by Python (`ctx.settings()`). JS does not read files; have Python send it with `ctx.post({"t": "cfg", ...})`. If you send it every time the value changes, a setting changed in the app takes effect immediately.

**Per-save data that must follow save/load**: use `api.saveData` / `ctx.save_data()` instead of writing files into `ctx.save_dir()`.

---

## 7. Common mistakes and their symptoms

| Symptom | Cause | Fix |
|---|---|---|
| The mod is not in the app list | `mod.json` is missing, has a JSON syntax error, or the folder is in the wrong place | `validate`, check it is in the mods folder (`Documents\M24GA\mods`), press **Refresh** in the app |
| "Cannot be turned on" | `mod.json` error (required item, missing file, core condition) | The red notice on the app home screen or the mod info tab, `validate` |
| It is on but nothing happens in the game | The loader is off / the game is not attached yet / the tables are being built | The big button on the home screen, `loader.log`, check `mapsReady`. **Social posts that are already drawn only change after you leave the screen and come back** |
| The mod window says "Not running yet" | The Python part is not running | Turn the loader on, look for `[mod id] Python error` in `loader.log` |
| `ui_... function not found` in the mod window | `m24.call('name')` and `def ui_name` differ | Make the names match (`validate` catches it) |
| "Python error" as soon as the mod is turned on | No `run(ctx)`, import failure, an exception | The stack in `loader.log` |
| "Turned off automatically" + a reason in the app | The loader detected repeated errors and turned it off: syntax error, an exception while loading, callback exceptions more than 25 times in 5 seconds, or Python exceptions 3 times in 60 seconds | Read the reason and the stack in `loader.log`, fix it and **turn it on again**. Wrap every callback in `try/catch`, and when something cannot run because a setting is missing, wait with `ctx.stop.wait(2.0)` instead of raising |
| No mod loads after the game crashed | **Safe mode** (the game crashed with mods loaded) | Read the notice on the app home screen and turn mods on one by one to find the cause. Check that your code only reads objects confirmed with `lookup` |
| After switching a mod off and on, text on an already open screen is unchanged | Since core 0.3.0 the tables stay, but a mod loaded again changes only text drawn afterwards | Leave the screen and open it again. Only the first time M24GA starts does it build the tables (1–2 minutes) |
| After off/on, an Interceptor or timer runs twice | The core does not know about things the mod attached itself, so they remain when it is unloaded | In `api.onUnload(fn)` call `listener.detach()` and `clearInterval(t)` (`validate` warns) |
| Changing a setting does not reach JS | JS does not read the settings file | Have Python send it with `ctx.post` (section 6) |
| Messages do not arrive | `ctx.post` returned `False` (the game is not attached), or it was lost | The `hello`/`ready` and resend pattern |
| The game crashed | Reading an unconfirmed object, raw memory access | Take objects out only with `lookup`, use `try/catch`, no raw access |
| My per-save records are wrong after loading an older save | Records were written into `ctx.save_dir()` | Use `api.saveData` / `ctx.save_data()` (section 4) |
| "Unsupported game version" | The game was updated and the core addresses no longer match; or it is a build that has not been checked yet | Wait for a core update (not a mod problem), or send the **Copy build diagnostic report** from the app home screen |

---

## 8. Debugging order

1. `python -X utf8 tools\m24.py validate <mod folder>`: most structural errors are caught here.
2. In the app press **Refresh** → turn the mod on → turn the loader on.
3. Open that mod in the app and look at the **Log tab** (a red count appears on the tab when there are errors; you can filter with "errors only"). The full record is `~\m24ga_data\loader.log`: `game: ...` = game-side JS (`api.log` and errors), `[mod id] ...` = Python (`ctx.log` and errors).
4. Change one thing at a time and check again.
5. **An AI agent should check through the CLI rather than the screen** ([`CLI.md`](CLI.md)): if the user keeps the app running, `python -X utf8 loader\cli.py status --json` (connection, game date), `rescan`/`enable <id>` (load a new mod), `reload <id>` (apply a mod.js change right away), `log <id> --json` and `report <id>` run on the app's loader.
6. (Optional) With `// @ts-check` and `/// <reference ...m24ga.d.ts />` at the top of `mod.js`, VS Code underlines missing functions and wrong arguments right away.

---

## 9. Safety

- A mod runs code in game memory and on the user's PC. **Do not install mods from unknown sources.** Read AI-written code before turning it on too.
- Before a mod is turned on, the app **shows the user its risky capabilities (running code on the PC, direct memory reads/writes, hooking functions) and asks for permission.** This is a notice-and-consent mechanism, not a sandbox: code can hide things, so only allow mods you trust.
- Writes to game values (`api.setProp`, `api.setField`, `api.setPlayerPA`, `api.action`) stay in the save once the game is saved. **Back up the save first**, and use the semi-automatic discovery tools (`verify`) only on a **test save**.
- Do not put API keys in a mod file; keep the key in a separate file and put only its path in the settings (the `mods/ai-social-feed` way).
