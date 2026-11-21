"""M24GA 모드 검증기. GPL-3.0-or-later.

모드 폴더 또는 .24mod 파일을 읽어서 문제를 찾는다. 사람과 AI가 같이 읽도록 문제마다
  level(error/warning/info), where(어느 파일의 어느 항목), message(무엇이 문제인지), fix(어떻게 고치는지)
를 낸다. 게임이나 frida 없이 돌아간다 (mods.py만 쓴다).

사용: python -X utf8 tools/m24.py validate 모드폴더 [--json]
"""
import ast
import difflib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import caps  # noqa: E402
import mods as modlib  # noqa: E402

KNOWN_KEYS = ("$schema", "id", "name", "version", "description", "author", "license", "core", "js", "python", "ui",
              "default_enabled", "data_dir", "migrate_from", "capabilities", "settings_file", "settings", "requires", "events")
KNOWN_EVENTS = ("socialPanel", "frame", "dateChanged", "saveLoaded")
SETTING_KEYS = ("key", "type", "label", "default", "group", "help", "min", "max", "step", "percent", "multiline", "placeholder", "options")
TYPE_ALIASES = {"string": "text", "str": "text", "textarea": "text", "boolean": "bool", "checkbox": "bool", "toggle": "bool", "switch": "bool",
                "integer": "int", "float": "number", "double": "number", "slider": "number", "range": "number",
                "dropdown": "select", "choice": "select", "enum": "select", "secret": "password", "pass": "password"}
GENERIC_PY_NAMES = ("config", "utils", "common", "helpers", "constants", "settings", "bridge", "generator", "main_helpers")
HEX = re.compile(r"^[0-9a-f]+$")


class Report:
    def __init__(self, path):
        self.path, self.issues, self.id = path, [], None

    def add(self, level, where, message, fix=""):
        self.issues.append({"level": level, "where": where, "message": message, "fix": fix})

    error = lambda self, w, m, f="": self.add("error", w, m, f)      # noqa: E731
    warn = lambda self, w, m, f="": self.add("warning", w, m, f)     # noqa: E731
    info = lambda self, w, m, f="": self.add("info", w, m, f)        # noqa: E731

    @property
    def errors(self):
        return [i for i in self.issues if i["level"] == "error"]

    def to_dict(self):
        return {"path": self.path, "id": self.id, "ok": not self.errors, "errors": len(self.errors),
                "warnings": len([i for i in self.issues if i["level"] == "warning"]), "issues": self.issues}


def _closest(word, options):
    m = difflib.get_close_matches(word, options, n=1, cutoff=0.6)
    return m[0] if m else None


def _load_manifest(path, rep):
    """(Mod, manifest) 또는 (None, None)."""
    try:
        if os.path.isdir(path):
            mf = os.path.join(path, "mod.json")
            if not os.path.isfile(mf):
                rep.error("mod.json", "폴더에 mod.json이 없어요", "모드 폴더 맨 위에 mod.json을 만드세요 (python tools/m24.py new <id>로 뼈대를 만들 수 있어요)")
                return None, None
            with open(mf, encoding="utf-8-sig") as f:
                raw, kind = f.read(), "dir"
        elif path.lower().endswith(modlib.MOD_EXT) and os.path.isfile(path):
            with zipfile.ZipFile(path) as z:
                if "mod.json" not in z.namelist():
                    rep.error("mod.json", ".24mod 파일 맨 위에 mod.json이 없어요", "폴더 안의 파일들을 폴더째가 아니라 바로 zip의 맨 위에 넣어야 해요 (tools/m24.py pack을 쓰세요)")
                    return None, None
                raw, kind = z.read("mod.json").decode("utf-8-sig"), "file"
        else:
            rep.error(path, "모드 폴더나 %s 파일이 아니에요" % modlib.MOD_EXT, "mod.json이 든 폴더 경로를 주세요")
            return None, None
    except (OSError, zipfile.BadZipFile, UnicodeDecodeError) as e:
        rep.error(path, "읽지 못했어요: %s" % e)
        return None, None
    try:
        manifest = json.loads(raw)
    except ValueError as e:
        rep.error("mod.json", "JSON 문법 오류: %s" % e, "쉼표, 따옴표, 괄호를 확인하세요. 주석(// ...)과 마지막 항목 뒤의 쉼표는 JSON에서 쓸 수 없어요")
        return None, None
    if not isinstance(manifest, dict):
        rep.error("mod.json", "맨 위가 { } 객체여야 해요")
        return None, None
    mid = manifest.get("id")
    if not isinstance(mid, str):
        mid = "_invalid_"
    return modlib.Mod(path, kind, dict(manifest, id=mid)), manifest


def _check_manifest(mod, m, rep, names):
    w = "mod.json"
    for k in m:
        if k not in KNOWN_KEYS:
            c = _closest(k, KNOWN_KEYS)
            rep.warn("%s %s" % (w, k), "모르는 항목이에요 (로더가 무시해요)", ("혹시 '%s'를 말하려던 건가요?" % c) if c else "오타인지 확인하세요. 쓸 수 있는 항목: " + ", ".join(KNOWN_KEYS[1:]))
    for k in ("id", "name", "version"):
        if not isinstance(m.get(k), str) or not m.get(k).strip():
            rep.error("%s %s" % (w, k), "필수 항목이 없거나 글자가 아니에요", '예: "%s": "%s"' % (k, {"id": "my-mod", "name": "내 모드", "version": "1.0.0"}[k]))
    mid = m.get("id")
    if isinstance(mid, str) and mid:
        rep.id = mid
        if not modlib.ID_RE.match(mid):
            rep.error(w + " id", "id 형식이 잘못됐어요: %r" % mid, "소문자·숫자·-·_ 만, 숫자나 소문자로 시작, 최대 64자 (예: my-mod)")
    v = m.get("version")
    if isinstance(v, str) and not re.match(r"^\d+\.\d+(\.\d+)?([-+].+)?$", v):
        rep.warn(w + " version", "버전 형식이 '1.0.0' 같은 숫자 형식이 아니에요: %r" % v, '"1.0.0"처럼 적으세요')
    for k in ("description", "author", "license", "data_dir", "migrate_from"):
        if k in m and not isinstance(m[k], str):
            rep.error("%s %s" % (w, k), "글자여야 해요")
    if not m.get("description"):
        rep.info(w + " description", "설명이 없어요", "앱 정보 탭에 보이는 한 줄 설명을 넣으면 좋아요")
    # core
    core = m.get("core")
    if core is not None:
        if not isinstance(core, str) or not re.match(r"^\s*(>=|==|=)?\s*\d+(\.\d+){0,2}\s*$", core):
            rep.error(w + " core", "형식이 잘못됐어요: %r" % (core,), '">=0.2.0", "==0.2.0", "0.2.0" 중 하나')
        elif not modlib.core_ok(core):
            rep.error(w + " core", "이 모드는 코어 %s가 필요한데 지금 코어는 %s예요" % (core, modlib.CORE_VERSION), "코어를 올리거나, 새 기능을 안 쓰면 core 조건을 낮추세요")
    else:
        rep.info(w + " core", "core 조건이 없어요", '"core": ">=%s"처럼 적어 두면 안 맞는 코어에서 켜지지 않아요' % modlib.CORE_VERSION)
    # 파일
    for key, default in (("js", "mod.js"), ("python", None), ("ui", None)):
        val = m.get(key, default)
        if val is None:
            continue
        if not isinstance(val, str) or not val:
            rep.error("%s %s" % (w, key), "파일 경로(글자)여야 해요")
        elif val not in names:
            c = _closest(val, names)
            rep.error("%s %s" % (w, key), "%r 파일이 없어요" % val, ("혹시 '%s'인가요?" % c) if c else "mod.json의 경로와 실제 파일 위치/이름(대소문자)을 맞추세요")
    if isinstance(m.get("python"), str) and not m["python"].endswith(".py"):
        rep.error(w + " python", "Python 진입 파일은 .py여야 해요")
    if "default_enabled" in m and not isinstance(m["default_enabled"], bool):
        rep.error(w + " default_enabled", "true/false여야 해요")
    sf = m.get("settings_file")
    if sf is not None and (not isinstance(sf, str) or "/" in sf or "\\" in sf or not sf.endswith(".json")):
        rep.error(w + " settings_file", "폴더 없는 .json 파일 이름이어야 해요", '예: "settings.json"')
    if "requires" in m and not (isinstance(m["requires"], list) and all(isinstance(x, str) for x in m["requires"])):
        rep.error(w + " requires", "글자 목록이어야 해요", '예: ["requests"]')
    ev = m.get("events")
    if ev is not None:
        if not isinstance(ev, list):
            rep.error(w + " events", "목록이어야 해요")
        else:
            for e in ev:
                if e not in KNOWN_EVENTS:
                    rep.error(w + " events", "모르는 이벤트 %r" % (e,), "지금 있는 이벤트: " + ", ".join(KNOWN_EVENTS))
    _check_settings(m.get("settings"), rep)


def _check_settings(settings, rep):
    if settings is None:
        return
    if not isinstance(settings, list):
        rep.error("mod.json settings", "목록([ ])이어야 해요")
        return
    seen = {}
    for i, s in enumerate(settings):
        key = s.get("key") if isinstance(s, dict) else None
        w = "mod.json settings[%d]%s" % (i, " (%s)" % key if isinstance(key, str) else "")
        if not isinstance(s, dict):
            rep.error(w, "{ } 객체여야 해요")
            continue
        for k in s:
            if k not in SETTING_KEYS:
                c = _closest(k, SETTING_KEYS)
                rep.warn("%s %s" % (w, k), "모르는 항목이에요 (무시돼요)", ("혹시 '%s'인가요?" % c) if c else "쓸 수 있는 항목: " + ", ".join(SETTING_KEYS))
        if not isinstance(key, str) or not key or any(not p for p in key.split(".")):
            rep.error(w + " key", "key가 없거나 형식이 잘못됐어요", '글자, 점(.)으로 중첩 가능. 예: "style.swear"')
            continue
        for other in seen:
            if other == key:
                rep.error(w + " key", "key가 중복이에요", "항목마다 다른 key를 쓰세요")
            elif other.startswith(key + ".") or key.startswith(other + "."):
                rep.error(w + " key", "'%s'와 '%s'가 서로 겹쳐요 (하나는 값이고 하나는 그 안의 묶음이 될 수 없어요)" % (key, other), "한쪽 key 이름을 바꾸세요")
        seen[key] = s
        t = s.get("type")
        if t not in modlib.SETTING_TYPES:
            alias = TYPE_ALIASES.get(str(t).lower())
            rep.error(w + " type", "type %r은 쓸 수 없어요" % (t,), ("'%s'를 쓰세요. " % alias if alias else "") + "허용: " + ", ".join(modlib.SETTING_TYPES))
            continue
        if not s.get("label"):
            rep.warn(w + " label", "label이 없어서 key가 이름으로 보여요", "사람이 읽을 이름을 넣으세요")
        if "default" not in s:
            rep.warn(w + " default", "default가 없어요", "기본값을 넣으세요")
        else:
            d = s["default"]
            ok = {"bool": isinstance(d, bool), "int": isinstance(d, int) and not isinstance(d, bool),
                  "number": isinstance(d, (int, float)) and not isinstance(d, bool),
                  "text": isinstance(d, str), "password": isinstance(d, str), "select": True}[t]
            if not ok:
                rep.error(w + " default", "default %r가 type '%s'와 안 맞아요" % (d, t), "type에 맞는 값으로 고치세요 (bool=true/false, int/number=숫자, text/password=글자)")
            if ok and t in ("int", "number") and (("min" in s and d < s["min"]) or ("max" in s and d > s["max"])):
                rep.error(w + " default", "default %r가 min~max 범위 밖이에요" % (d,))
        if t in ("int", "number"):
            for b in ("min", "max"):
                if b in s and (not isinstance(s[b], (int, float)) or isinstance(s[b], bool)):
                    rep.error("%s %s" % (w, b), "숫자여야 해요")
            if isinstance(s.get("min"), (int, float)) and isinstance(s.get("max"), (int, float)) and s["min"] > s["max"]:
                rep.error(w, "min이 max보다 커요")
            if s.get("percent") and not (t == "number" and "min" in s and "max" in s):
                rep.warn(w + " percent", "percent는 min과 max가 있는 number 항목에서만 효과가 있어요")
        if t == "select":
            opts = s.get("options")
            if not isinstance(opts, list) or not opts:
                rep.error(w + " options", "select는 options 목록이 필요해요", '예: ["a","b"] 또는 [{"value":"a","label":"에이"}]')
            else:
                vals = []
                for o in opts:
                    if isinstance(o, dict) and "value" in o and isinstance(o.get("label", ""), str):
                        vals.append(o["value"])
                    elif isinstance(o, str):
                        vals.append(o)
                    else:
                        rep.error(w + " options", "옵션 %r 형식이 잘못됐어요" % (o,), '글자 또는 {"value": .., "label": ..}')
                if "default" in s and vals and s["default"] not in vals:
                    rep.error(w + " default", "default %r가 options 안에 없어요 (%s)" % (s["default"], ", ".join(map(str, vals))))
        if t == "password":
            rep.info(w, "password 값은 설정 파일에 그대로 저장돼요 (화면에는 안 보여요)", "API 키는 별도 파일에 두고 설정에는 경로만 두는 방식을 권장해요")


def _core_min(core):
    mt = re.match(r"^\s*(>=|==|=)?\s*([\d.]+)\s*$", core or "")
    return modlib._ver(mt.group(2)) if mt else (0, 0, 0)


def _check_js(mod, m, rep, names):
    rel = m.get("js", "mod.js") if isinstance(m.get("js", "mod.js"), str) else "mod.js"
    if rel not in names:
        return ""
    try:
        src = mod.read_text(rel)
    except Exception as e:  # noqa: BLE001
        rep.error(rel, "읽지 못했어요: %s" % e)
        return ""
    lines = src.splitlines()

    def at(pat):
        for n, ln in enumerate(lines, 1):
            code = ln.split("//")[0]
            if re.search(pat, code):
                return n
        return None

    rules = [
        (r"\bregisterMod\s*\(", "error", "mod.js 안에서 registerMod()를 부르면 안 돼요 (로더가 이미 감싸 줘요)", "registerMod 줄을 지우고 안의 내용만 mod.js에 두세요. 코어 API는 api.on / api.status / api.send ... 로 써요"),
        (r"(?:^|[^.\w])require\s*\(", "error", "Frida 스크립트에는 require()가 없어요", "필요한 기능은 코어 함수나 Python 쪽(ctx.recv/post)으로 옮기세요"),
        (r"^\s*import\s+[\w{*]|\bexport\s+(?:default|const|function|\{)", "error", "import/export는 쓸 수 없어요 (모든 모드가 한 스크립트로 묶여요)", "한 파일에 모두 쓰세요"),
        (r"\b(?:document|window|localStorage|XMLHttpRequest|fetch)\b", "error", "게임 쪽 JS에는 브라우저 API(document, window, fetch ...)가 없어요", "화면은 모드창(ui/index.html), 네트워크는 Python 쪽에서 하세요"),
        (r"\bconsole\.(?:log|warn|error)\s*\(", "warning", "console.log는 로그 파일로 안 가요", "api.log('...')를 쓰면 loader.log에 남아요"),
        (r"\bInterceptor\.(?:attach|replace)\s*\(", "warning", "게임 함수를 직접 후킹해요. 같은 함수를 코어도 후킹하고 있으면 서로 꼬일 수 있어요 (원시 접근, 앞으로 권한 선언이 필요해져요)", "가능하면 api.on('socialPanel'/'frame') 같은 코어 이벤트를 쓰세요"),
        (r"\b(?:NativeFunction|NativeCallback)\s*\(|\.write(?:U8|U16|U32|S32|Pointer|Utf8String|ByteArray|Double)\s*\(", "warning", "게임 메모리에 직접 접근해요. 잘못된 주소는 게임을 튕기게 하고 쓰기는 세이브를 망가뜨릴 수 있어요 (원시 접근)", "코어 읽기 함수(getVal 등)를 쓰고, 쓰기는 코어가 지원할 때까지 하지 마세요. 꼭 필요하면 try/catch로 감싸고 먼저 객체를 확인하세요"),
    ]
    for pat, lvl, msg, fix in rules:
        n = at(pat)
        if n:
            rep.add(lvl, "%s:%d" % (rel, n), msg, fix)
    for n, ln in enumerate(lines, 1):
        for em in re.finditer(r"""api\.on\(\s*['"]([^'"]+)['"]""", ln):
            if em.group(1) not in KNOWN_EVENTS:
                rep.error("%s:%d" % (rel, n), "모르는 이벤트 %r" % em.group(1), "지금 있는 이벤트: " + ", ".join(KNOWN_EVENTS))
    # 필드 등록부 (M20): 없는 필드 이름, 읽기만 되는 필드 쓰기
    try:
        freg = caps.fields()["fields"]
    except (OSError, ValueError):
        freg = None
    for n, how, name in (caps.field_uses(src) if freg is not None else []):
        f = freg.get(name)
        if not f:
            c = _closest(name, list(freg))
            rep.error("%s:%d" % (rel, n), "모르는 필드 %r" % name,
                      ("혹시 '%s'인가요? " % c if c else "") + "있는 필드는 docs/FIELDS.md (게임에서는 fieldNames('player.'))")
        elif how == "set" and f.get("write") != "safe":
            rep.error("%s:%d" % (rel, n), "필드 %r는 읽기만 돼요 (write: %s)" % (name, f.get("write", "no")),
                      "쓰기가 확인된 필드(docs/FIELDS.md의 '쓰기: safe')만 api.setField로 쓸 수 있어요")
    # 함수 등록부 (M22): 없는 함수, 코어 전용 함수, 보기만 되는 함수를 바꾸기
    try:
        fnreg = caps.functions()["functions"]
    except (OSError, ValueError):
        fnreg = None
    for n, name in (caps.hook_uses(src) if fnreg is not None else []):
        f = fnreg.get(name)
        if not f:
            c = _closest(name, list(fnreg))
            rep.error("%s:%d" % (rel, n), "모르는 함수 %r" % name,
                      ("혹시 '%s'인가요? " % c if c else "") + "있는 함수는 docs/FUNCTIONS.md (CLI functions)")
        elif f.get("owner") == "core" and f.get("call"):
            rep.error("%s:%d" % (rel, n), "%r는 코어가 직접 부르는 함수라 끼어들 수 없어요" % name, "모드에서는 쓰지 않아요")
        elif f.get("owner") == "core":
            rep.error("%s:%d" % (rel, n), "%r는 코어가 이미 걸어 둔 함수예요" % name, "api.on('%s', fn)을 쓰세요" % f.get("event", "?"))
        elif f.get("hook") != "modify" and re.search(r"\bev\.set(?:Arg|Ret)\s*\(", src):
            rep.warn("%s:%d" % (rel, n), "%r는 보기만 되는 함수(hook: observe)인데 ev.setArg/ev.setRet을 써요 (실행하면 오류)" % name,
                     "functions.json에서 modify로 확인된 함수만 바꿀 수 있어요")
    if at(r"\bapi\.(?:send|recv)\s*\("):
        if _core_min(m.get("core")) < (0, 2, 0):
            rep.warn("mod.json core", "api.send/api.recv는 코어 0.2.0부터 있어요", '"core": ">=0.2.0"로 올리세요')
        if not m.get("python"):
            rep.warn(rel, "api.send로 보내도 받을 Python 부분이 없어요 (mod.json에 python 항목 없음)", "python/main.py를 만들고 mod.json에 \"python\"을 적으세요")
    if at(r"\bapi\.(?:settings|onSettings)\s*\(") and _core_min(m.get("core")) < (0, 12, 0):
        rep.warn("mod.json core", "api.settings/api.onSettings는 코어 0.12.0부터 있어요", '"core": ">=0.12.0"로 올리세요')
    if at(r"\bapi\.(?:onUnload|alive)\s*\(") and _core_min(m.get("core")) < (0, 3, 0):
        rep.warn("mod.json core", "api.onUnload/api.alive는 코어 0.3.0부터 있어요", '"core": ">=0.3.0"로 올리세요')
    if at(r"\b(?:Interceptor\.attach|setInterval)\s*\(") and not at(r"\bapi\.onUnload\s*\("):
        rep.warn(rel, "Interceptor.attach나 setInterval을 직접 쓰는데 api.onUnload가 없어요. 모드를 끄거나 다시 올려도 그것들이 계속 남아요",
                 "api.onUnload(function () { listener.detach(); clearInterval(t); })처럼 치우세요 (api.on('frame', ...)을 쓰면 코어가 알아서 떼요)")
    # 문법 검사 (node가 있을 때). 모드는 function(api){ ... } 안에 들어가므로 같은 모양으로 감싼다. 줄 번호는 그대로 맞는다.
    node = shutil.which("node")
    if not node:
        rep.info(rel, "node가 없어서 JS 문법 검사를 건너뛰었어요", "Node.js를 설치하면 문법 오류도 미리 잡아 줘요")
        return src
    with tempfile.TemporaryDirectory() as td:
        fp = os.path.join(td, "mod_check.js")
        with open(fp, "w", encoding="utf-8") as f:
            f.write("(function (api) {" + src + "\n});\n")
        r = subprocess.run([node, "--check", fp], capture_output=True, text=True, timeout=30)
        if r.returncode != 0:
            err = [x for x in r.stderr.splitlines() if x.strip()]
            msg = next((x for x in err if "Error" in x), err[0] if err else "문법 오류")
            ln = re.search(r"mod_check\.js:(\d+)", r.stderr)
            rep.error("%s%s" % (rel, ":" + ln.group(1) if ln else ""), "JS 문법 오류: %s" % msg.strip(), "해당 줄의 괄호, 따옴표, 쉼표를 확인하세요")
    return src


def _py_files(mod, m, names):
    """진입 파일이 있는 폴더의 .py 파일 {상대경로: 코드}."""
    entry = m.get("python")
    if not isinstance(entry, str) or entry not in names:
        return {}, ""
    sub = os.path.dirname(entry).replace("\\", "/")
    out = {}
    for n in names:
        if n.endswith(".py") and (not sub or n.startswith(sub + "/")):
            try:
                out[n] = mod.read_text(n)
            except Exception:  # noqa: BLE001
                pass
    return out, sub


def _check_python(mod, m, rep, names):
    files, sub = _py_files(mod, m, names)
    entry = m.get("python")
    ui_funcs = set()
    if not files:
        return ui_funcs
    local = set()
    for n in names:
        if sub and not n.startswith(sub + "/"):
            continue
        rest = n[len(sub) + 1:] if sub else n
        top = rest.split("/")[0]
        local.add(top[:-3] if top.endswith(".py") else top)
    requires = {re.split(r"[<>=!~\[ ]", r)[0].lower() for r in (m.get("requires") or []) if isinstance(r, str)}
    for n, code in sorted(files.items()):
        try:
            tree = ast.parse(code, filename=n)
        except SyntaxError as e:
            rep.error("%s:%s" % (n, e.lineno), "Python 문법 오류: %s" % e.msg, "해당 줄을 확인하세요")
            continue
        if n == entry:
            run = next((x for x in tree.body if isinstance(x, ast.FunctionDef) and x.name == "run"), None)
            if run is None:
                rep.error(n, "run(ctx) 함수가 없어요", "def run(ctx): ... 를 만들고 ctx.stop이 켜질 때까지 일하세요")
            else:
                if not run.args.args:
                    rep.error("%s:%d" % (n, run.lineno), "run은 ctx 인자를 받아야 해요", "def run(ctx):")
                elif "%s.stop" % run.args.args[0].arg not in code:
                    rep.warn("%s:%d" % (n, run.lineno), "ctx.stop을 확인하지 않아요. 모드를 끌 때 멈추지 않고 15초 뒤 강제로 기다리게 돼요", "while not ctx.stop.wait(1.0): ... 처럼 반복하세요 (또는 ctx.recv(timeout) 루프에서 ctx.stop.is_set() 확인)")
        for node in ast.walk(tree):
            names_in = []
            if isinstance(node, ast.Import):
                names_in = [a.name.split(".")[0] for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                names_in = [node.module.split(".")[0]]
            for nm in names_in:
                if nm in sys.stdlib_module_names or nm in local:
                    continue
                if nm in _pylib_names():   # 코어 0.18.0 공용 라이브러리 (M24GA/pylib, 로더가 sys.path에 넣음)
                    continue
                if nm.lower() not in requires and nm not in ("frida",):
                    rep.warn("%s:%d" % (n, node.lineno), "'%s'는 기본 Python 패키지가 아니에요. 배포용 exe에는 없을 수 있어요" % nm, '순수 Python이면 python/ 안에 같이 넣고, 아니면 mod.json "requires": ["%s"]에 적으세요' % nm)
        if n == entry:
            for x in tree.body:
                if isinstance(x, ast.FunctionDef) and x.name.startswith("ui_"):
                    ui_funcs.add(x.name[3:])
    for nm in local:
        if nm in GENERIC_PY_NAMES:
            rep.warn(entry, "Python 모듈 이름 '%s'이 흔해서 다른 모드와 겹칠 수 있어요 (겹치면 나중에 켜는 모드가 막혀요)" % nm, "이름에 모드 이름을 넣거나(예: mymod_config.py) 패키지 폴더 안에 넣으세요")
    for n in sorted(files):
        if n != entry and files[n].count("\n") == 0 and not files[n].strip():
            rep.info(n, "빈 파일이에요")
    return ui_funcs


def _check_ui(mod, m, rep, names, ui_funcs):
    rel = m.get("ui")
    if not isinstance(rel, str) or rel not in names:
        return
    try:
        html = mod.read_text(rel)
    except Exception as e:  # noqa: BLE001
        rep.error(rel, "읽지 못했어요: %s" % e)
        return
    if not m.get("python"):
        rep.error("mod.json ui", "모드창은 Python 부분의 ui_ 함수로만 통신해요. python 항목이 없어요", "python/main.py를 만들고 mod.json에 \"python\"을 적으세요")
    lines = html.splitlines()
    for n, ln in enumerate(lines, 1):
        for pat, msg in ((r"\.innerHTML\s*=|\.outerHTML\s*=|insertAdjacentHTML|document\.write\s*\(", "HTML로 넣으면 글 속 태그가 실행돼요 (모드가 만든 글자나 AI 글을 넣을 때 위험해요)"),
                         (r"\beval\s*\(|new\s+Function\s*\(", "eval은 쓸 수 없어요")):
            if re.search(pat, ln):
                rep.warn("%s:%d" % (rel, n), msg, "textContent로 넣으세요")
        for cm in re.finditer(r"""m24\.call\(\s*['"]([^'"]+)['"]""", ln):
            nm = cm.group(1)
            if nm not in ui_funcs:
                c = _closest(nm, sorted(ui_funcs))
                rep.error("%s:%d" % (rel, n), "m24.call('%s')에 맞는 ui_%s() 함수가 Python 진입 파일에 없어요" % (nm, nm),
                          ("혹시 '%s'인가요? " % c if c else "") + "%s 에 def ui_%s(...): 를 만드세요" % (m.get("python", "python/main.py"), nm))
    if re.search(r"https?://(?!cdn\.jsdelivr\.net/gh/orioncactus)", html):
        rep.info(rel, "외부 주소를 쓰고 있어요. 인터넷이 없으면 모드창이 비어 보일 수 있어요", "필요한 것은 파일 안에 넣는 편이 안전해요")
    if not re.search(r"m24\.call\(", html) and ui_funcs:
        rep.info(rel, "Python에 ui_ 함수가 있는데 모드창이 m24.call로 부르지 않아요")


def _check_builds(mod, m, rep, names):
    for n in names:
        if not (n.startswith("builds/") and n.endswith(".json")):
            continue
        try:
            d = json.loads(mod.read_text(n))
        except ValueError as e:
            rep.error(n, "JSON 문법 오류: %s" % e)
            continue
        for i, e in enumerate(d if isinstance(d, list) else [d]):
            w = "%s[%d]" % (n, i)
            if not isinstance(e, dict) or not isinstance(e.get("build"), str):
                rep.error(w, "build(게임 빌드 이름) 글자가 필요해요", "코어 builds/*.json의 name과 같은 글자")
                continue
            for part, ln in (("sig", 32), ("vt", None)):
                for off, val in (e.get(part) or {}).items():
                    if not re.match(r"^0x[0-9a-f]+$", str(off)):
                        rep.error("%s %s" % (w, part), "오프셋 %r 형식이 잘못됐어요" % off, "예: 0x61ae80")
                    if not isinstance(val, str) or not HEX.match(val) or (ln and len(val) != ln):
                        rep.error("%s %s %s" % (w, part, off), "값은 소문자 16진수%s여야 해요" % (" %d자(16바이트)" % ln if ln else ""))


def _check_caps(mod, m, rep, names):
    """기능 등록부 (M10): 선언한 기능과 코드에서 쓰는 기능이 맞는지."""
    w = "mod.json capabilities"
    rel = m.get("js", "mod.js") if isinstance(m.get("js", "mod.js"), str) else "mod.js"
    try:
        src = mod.read_text(rel) if rel in names else ""
    except Exception:  # noqa: BLE001  (읽기 오류는 _check_js가 알린다)
        src = ""
    found = caps.detect(src, m)
    if m.get("python"):   # (코어 0.39.0) Python 쪽 ctx.props/ctx.prop = read.prop, (0.41.0) ctx.actions_for = read.action, ctx.action = game.action
        pyw = [("read.prop", r"\bctx\.props?\s*\("), ("read.action", r"\bctx\.actions_for\s*\("), ("game.action", r"\bctx\.action\s*\(")]
        for n in names:
            if not n.endswith(".py"):
                continue
            try:
                txt = mod.read_text(n)
            except Exception:  # noqa: BLE001
                continue
            for cap, rx in pyw:
                if cap not in found and re.search(rx, txt):
                    found[cap] = 0
    v = m.get("capabilities")
    if v is not None and (not isinstance(v, list) or not all(isinstance(x, str) for x in v)):
        rep.error(w, "글자 목록이어야 해요", '예: "capabilities": ["event.socialPanel", "read.data"]')
        return
    want = sorted(found, key=lambda x: (caps.RISK_ORDER.index(caps.risk_of(x)), x))
    if v is None:
        if want:
            rep.warn(w, "쓰는 기능을 선언하지 않았어요. 코드에서 찾은 기능: %s" % ", ".join(want),
                     'mod.json에 "capabilities": %s 를 넣으세요 (목록과 뜻: docs/CAPABILITIES.md)' % json.dumps(want))
    else:
        for x in caps.unknown(m):
            c = caps.closest(x)
            rep.error(w, "모르는 기능 이름이에요: %r" % x, ("혹시 '%s'인가요? " % c if c else "") + "쓸 수 있는 이름: docs/CAPABILITIES.md")
        for x in want:
            if x not in v:
                where = "mod.json python" if found[x] == 0 else "%s:%d" % (rel, found[x])
                rep.error(where, "기능 '%s'(%s)를 쓰는데 mod.json capabilities에 없어요" % (x, caps.registry()["by_name"][x]["title"]),
                          'mod.json "capabilities"에 "%s"를 더하세요' % x)
        for x in v:
            if x in caps.registry()["by_name"] and x not in found and x != "pc.python":
                rep.info(w, "'%s'를 선언했지만 코드에서 찾지 못했어요" % x, "안 쓰면 빼세요 (쓰는데 못 찾은 것이라면 그대로 두어도 돼요)")
        if "pc.python" in v and not m.get("python"):
            rep.warn(w, "pc.python을 선언했는데 mod.json에 python이 없어요", "Python 부분이 없으면 pc.python을 빼세요")
        if _core_min(m.get("core")) < (0, 4, 0):
            rep.warn("mod.json core", "capabilities는 코어 0.4.0부터 읽어요", '"core": ">=0.4.0"로 올리세요')
    el = caps.elevated(sorted(set(want) | set(x for x in (v or []) if caps.risk_of(x))))
    if el:
        reg = caps.registry()
        rep.info(w, "사용자가 앱에서 허용해야 켜지는 기능: %s" % ", ".join("%s(%s)" % (x, reg["risks"][caps.risk_of(x)]["label"]) for x in el),
                 "코어 함수(read.*, ui.*)로 되는 일이면 그쪽을 쓰세요. 허용을 덜 받을수록 사용자가 쉽게 켜요")


def _pylib_names():
    """M24GA/pylib에 있는 모듈·패키지 이름 (코어 0.18.0)"""
    d = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "pylib")
    try:
        return {n[:-3] if n.endswith(".py") else n for n in os.listdir(d) if (n.endswith(".py") or os.path.isdir(os.path.join(d, n))) and n != "__pycache__"}
    except OSError:
        return set()


def validate(path):
    rep = Report(path)
    mod, m = _load_manifest(path, rep)
    if mod is None:
        return rep
    try:
        names = mod._names()
    except Exception as e:  # noqa: BLE001
        rep.error(path, "파일 목록을 읽지 못했어요: %s" % e)
        return rep
    names = [n.replace("\\", "/") for n in names]
    _check_manifest(mod, m, rep, names)
    _check_js(mod, m, rep, names)
    ui_funcs = _check_python(mod, m, rep, names)
    _check_ui(mod, m, rep, names, ui_funcs)
    _check_builds(mod, m, rep, names)
    _check_caps(mod, m, rep, names)
    return rep


def format_text(rep):
    tag = {"error": "[오류]", "warning": "[경고]", "info": "[참고]"}
    out = ["검사: %s%s" % (rep.path, " (id: %s)" % rep.id if rep.id else "")]
    order = {"error": 0, "warning": 1, "info": 2}
    for i in sorted(rep.issues, key=lambda x: order[x["level"]]):
        out.append("%s %s: %s" % (tag[i["level"]], i["where"], i["message"]))
        if i["fix"]:
            out.append("       고치려면: %s" % i["fix"])
    d = rep.to_dict()
    out.append("결과: %s (오류 %d, 경고 %d)" % ("통과" if d["ok"] else "고쳐야 해요", d["errors"], d["warnings"]))
    return "\n".join(out)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    r = validate(sys.argv[1])
    print(json.dumps(r.to_dict(), ensure_ascii=False, indent=2) if "--json" in sys.argv else format_text(r))
    sys.exit(0 if not r.errors else 1)
