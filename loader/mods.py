"""M24GA: 모드 찾기, mod.json 검사, 켜고 끄기 목록, 모드 설정, 모드 Python 부분 실행. GPL-3.0-or-later.

모드 하나 = `.24mod` 파일(zip) 하나, 또는 mod.json이 든 폴더(개발용). (M24GA M03 로그)
  mods 폴더: 문서\\M24GA\\mods  (+ 개발 중에는 저장소의 mods/도 본다)
  사용자 데이터: ~/m24ga_data/
    enabled.json              {모드 id: true/false}  (없는 모드는 mod.json "default_enabled", 기본 true)
    cache/<id>-<version>/     .24mod 안 Python 부분을 푼 곳 (zip이 바뀌면 다시 푼다)
    <id>/                     모드 데이터 폴더 (mod.json "data_dir"로 바꿀 수 있다)
"""
import ctypes
import hashlib
import importlib.util
import json
import os
import queue
import re
import shutil
import sys
import threading
import time
import traceback
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import caps  # noqa: E402  (기능 등록부, M10)

CORE_VERSION = "0.33.0"
MOD_EXT = ".24mod"
FROZEN = getattr(sys, "frozen", False)
ROOT = os.path.dirname(os.path.abspath(sys.executable)) if FROZEN else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEV_MODS = os.path.join(ROOT, "mods")
PYLIB = os.path.join(ROOT, "pylib")   # 코어 0.18.0: 모드들이 같이 쓰는 Python 라이브러리 (dpa = Dynamic PA 0.9.5, m24hist = 세이브 과거 시즌)
DATA = os.path.join(os.path.expanduser("~"), "m24ga_data")
ENABLED_PATH = os.path.join(DATA, "enabled.json")
AUTO_PATH = os.path.join(DATA, "autodisabled.json")   # 오류가 반복돼서 자동으로 끈 모드 {id: {time, reason, source}}
CACHE_DIR = os.path.join(DATA, "cache")
ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
SETTING_TYPES = ("bool", "int", "number", "text", "password", "select")


def documents_dir():
    """문서 폴더 (OneDrive 등으로 옮겨져 있어도 실제 위치)."""
    buf = ctypes.create_unicode_buffer(260)
    try:
        if ctypes.windll.shell32.SHGetFolderPathW(None, 5, None, 0, buf) == 0 and buf.value:   # CSIDL_PERSONAL
            return buf.value
    except (AttributeError, OSError):
        pass
    return os.path.join(os.path.expanduser("~"), "Documents")


USER_MODS = os.path.join(documents_dir(), "M24GA", "mods")


def mod_dirs():
    """모드를 찾는 폴더 목록. exe로 배포하면 사용자 mods 폴더만 본다."""
    return [USER_MODS] if FROZEN else [USER_MODS, DEV_MODS]


def _ver(s):
    p = [int(x) for x in re.findall(r"\d+", s)[:3]]
    return tuple(p + [0] * (3 - len(p)))


def core_ok(req):
    """mod.json "core" 조건 (">=0.1.0", "0.1.0", 비우면 통과)."""
    req = (req or "").strip()
    if not req:
        return True
    m = re.match(r"^(>=|==|=)?\s*([\d.]+)$", req)
    if not m:
        return False
    return _ver(CORE_VERSION) >= _ver(m.group(2)) if m.group(1) == ">=" else _ver(CORE_VERSION) == _ver(m.group(2))


class Mod:
    """찾은 모드 하나. kind = 'file'(.24mod) / 'dir'(개발 폴더)."""

    def __init__(self, path, kind, manifest):
        self.path, self.kind, self.manifest = path, kind, manifest
        self.id = manifest["id"]
        self.problems = []          # 켤 수 없는 이유 (비어 있으면 켤 수 있다)
        self.warnings = []          # 켤 수는 있지만 알려 줄 것
        self.conflicts = []         # 같은 id인 다른 모드 파일의 경로

    name = property(lambda self: self.manifest.get("name") or self.id)
    version = property(lambda self: self.manifest.get("version", "0"))

    def _names(self):
        if self.kind == "dir":
            out = []
            for d, _, fs in os.walk(self.path):
                out += [os.path.relpath(os.path.join(d, f), self.path).replace("\\", "/") for f in fs]
            return out
        with zipfile.ZipFile(self.path) as z:
            return [n for n in z.namelist() if not n.endswith("/")]

    def has(self, rel):
        return rel in self._names()

    def read_bytes(self, rel):
        if self.kind == "dir":
            with open(os.path.join(self.path, rel), "rb") as f:
                return f.read()
        with zipfile.ZipFile(self.path) as z:
            return z.read(rel)

    def read_text(self, rel):
        return self.read_bytes(rel).decode("utf-8-sig")

    @property
    def data_dir(self):
        return os.path.expanduser(self.manifest.get("data_dir") or os.path.join(DATA, self.id))

    def build_entries(self):
        """모드 안 builds/*.json: [{"build": 빌드 이름, "sig": {...}, "vt": {...}}]"""
        out = []
        for n in self._names():
            if n.startswith("builds/") and n.endswith(".json"):
                d = json.loads(self.read_text(n))
                out += d if isinstance(d, list) else [d]
        return out

    def python_root(self):
        """Python 진입 파일이 있는 폴더 (.24mod면 캐시에 풀고 그 폴더)."""
        entry = self.manifest.get("python")
        if not entry:
            return None
        sub = os.path.dirname(entry)
        if self.kind == "dir":
            return os.path.join(self.path, sub)
        with open(self.path, "rb") as f:
            digest = hashlib.sha256(f.read()).hexdigest()
        dst = os.path.join(CACHE_DIR, "%s-%s" % (self.id, self.version))
        stamp = os.path.join(dst, ".m24ga_hash")
        try:
            with open(stamp, encoding="utf-8") as f:
                same = f.read().strip() == digest
        except OSError:
            same = False
        if not same:
            shutil.rmtree(dst, ignore_errors=True)
            os.makedirs(dst)
            with zipfile.ZipFile(self.path) as z:
                for n in z.namelist():
                    if not sub or n.startswith(sub + "/"):
                        z.extract(n, dst)
            with open(stamp, "w", encoding="utf-8") as f:
                f.write(digest)
        return os.path.join(dst, sub)

    def js_text(self):
        """게임 쪽 JS 글 (없거나 못 읽으면 ''). 기능 찾기에 쓴다."""
        if not hasattr(self, "_js"):
            try:
                self._js = self.read_text(self.manifest.get("js", "mod.js"))
            except (OSError, KeyError, UnicodeDecodeError):
                self._js = ""
        return self._js

    @property
    def caps(self):
        """이 모드의 기능 = mod.json 선언 ∪ 코드에서 찾은 것 (M10)."""
        if not hasattr(self, "_caps"):
            self._caps = caps.effective(self.manifest, self.js_text())
        return self._caps

    def needs_permission(self):
        """사용자가 아직 허용하지 않은 위험 기능 (pc, raw, hook, write). 비어 있으면 켤 수 있다."""
        g = set(granted(self.id))
        return [x for x in caps.elevated(self.caps) if x not in g]

    def info(self):
        """GUI용 요약."""
        m = self.manifest
        return {"id": self.id, "name": self.name, "version": self.version, "description": m.get("description", ""),
                "author": m.get("author", ""), "license": m.get("license", ""), "core": m.get("core", ""),
                "path": self.path, "kind": self.kind, "enabled": is_enabled(self), "auto_disabled": auto_disabled().get(self.id), "problems": list(self.problems),
                "warnings": list(self.warnings), "removable": removable(self), "conflicts": list(self.conflicts),
                "caps": caps.describe(self.caps, granted(self.id)), "needs_perm": self.needs_permission(), "caps_declared": "capabilities" in m, "has_settings": bool(m.get("settings")), "ui": m.get("ui")}


def _check(mod):
    m = mod.manifest
    for k in ("name", "version"):
        if not m.get(k):
            mod.problems.append("mod.json에 %s가 없음" % k)
    if not core_ok(m.get("core")):
        mod.problems.append("코어 %s가 필요함 (지금 %s)" % (m.get("core"), CORE_VERSION))
    names = mod._names()
    js = m.get("js", "mod.js")
    if js not in names:
        mod.problems.append("%s가 없음" % js)
    if m.get("python") and m["python"] not in names:
        mod.problems.append("Python 진입 파일 %s가 없음" % m["python"])
    for s in m.get("settings") or []:
        if not s.get("key") or s.get("type") not in SETTING_TYPES:
            mod.problems.append("설정 항목 형식 오류: %s" % json.dumps(s, ensure_ascii=False))
    for x in caps.unknown(m):
        c = caps.closest(x)
        mod.problems.append("모르는 기능 '%s'%s (mod.json capabilities)" % (x, (", 혹시 '%s'?" % c) if c else ""))
    for r in m.get("requires") or []:
        if importlib.util.find_spec(r.split(">")[0].split("=")[0].strip()) is None:
            mod.warnings.append("필요한 패키지 %s가 없음" % r)


def _load_one(path):
    if os.path.isdir(path):
        mf = os.path.join(path, "mod.json")
        if not os.path.isfile(mf):
            return None
        with open(mf, encoding="utf-8-sig") as f:
            return Mod(path, "dir", json.load(f))
    if path.lower().endswith(MOD_EXT):
        with zipfile.ZipFile(path) as z:
            return Mod(path, "file", json.loads(z.read("mod.json").decode("utf-8-sig")))
    return None


def scan():
    """mods 폴더들을 훑는다. 반환: (모드 목록, 오류 [(경로, 이유)]).
    같은 id가 둘 이상이면 모두 problems에 '중복'을 넣어 켜지 않는다."""
    os.makedirs(USER_MODS, exist_ok=True)
    found, errors = [], []
    for d in mod_dirs():
        if not os.path.isdir(d):
            continue
        for n in sorted(os.listdir(d)):
            p = os.path.join(d, n)
            try:
                mod = _load_one(p)
            except (OSError, ValueError, KeyError, zipfile.BadZipFile) as e:
                errors.append((p, "읽기 실패: %s" % e))
                continue
            if mod is None:
                continue
            if not isinstance(mod.manifest.get("id"), str) or not ID_RE.match(mod.id):
                errors.append((p, "id 형식 오류: %r (소문자·숫자·-·_)" % mod.manifest.get("id")))
                continue
            _check(mod)
            found.append(mod)
    by_id = {}
    for mod in found:
        by_id.setdefault(mod.id, []).append(mod)
    for mid, ms in by_id.items():
        if len(ms) > 1:
            for mod in ms:
                mod.problems.append("같은 id의 모드가 여러 개: " + ", ".join(x.path for x in ms))
                mod.conflicts = [x.path for x in ms if x is not mod]
    init_permissions(found)
    return found, errors


# ---- 데이터 폴더 이전 (M08) ----
MIGRATED = ".m24ga_migrated"


def ensure_data(mod):
    """모드 데이터 폴더를 만든다. mod.json "migrate_from"(옛 데이터 폴더)이 있고 새 폴더가 비어 있으면 **복사**해 온다
    (옛 폴더는 그대로 둔다 = 되돌리려면 mod.json만 되돌리면 된다). 복사했으면 설명 글, 아니면 None.
    새 폴더에 이미 내용이 있거나 이전한 표시(MIGRATED)가 있으면 아무것도 안 한다."""
    dst = mod.data_dir
    src = mod.manifest.get("migrate_from")
    if not isinstance(src, str) or not src:
        os.makedirs(dst, exist_ok=True)
        return None
    src = os.path.abspath(os.path.expanduser(src))
    if os.path.normcase(src) == os.path.normcase(os.path.abspath(dst)) or not os.path.isdir(src):
        os.makedirs(dst, exist_ok=True)
        return None
    if os.path.exists(os.path.join(dst, MIGRATED)) or (os.path.isdir(dst) and os.listdir(dst)):
        os.makedirs(dst, exist_ok=True)
        return None
    tmp = dst + ".migrating"
    shutil.rmtree(tmp, ignore_errors=True)
    shutil.copytree(src, tmp, ignore=shutil.ignore_patterns("*.tmp", "stop.flag", "__pycache__"))
    n = sum(len(fs) for _, _, fs in os.walk(tmp))
    with open(os.path.join(tmp, MIGRATED), "w", encoding="utf-8") as f:
        f.write("%s\n%s\n" % (src, time.strftime("%Y-%m-%d %H:%M:%S")))
    if os.path.isdir(dst):
        os.rmdir(dst)                 # 비어 있는 폴더만 여기까지 온다
    os.replace(tmp, dst)
    return "데이터 폴더를 복사해 왔어요: %s -> %s (파일 %d개. 옛 폴더는 그대로 두었어요)" % (src, dst, n)


# ---- 설치와 삭제 (M08): 앱의 설치/삭제 버튼이 쓴다 ----
TRASH = os.path.join(DATA, "trash")      # 지우거나 덮어쓴 .24mod는 여기로 옮긴다 (되돌릴 수 있게)


def _to_trash(path):
    os.makedirs(TRASH, exist_ok=True)
    dst = os.path.join(TRASH, time.strftime("%Y%m%d-%H%M%S-") + os.path.basename(path))
    shutil.move(path, dst)
    return dst


def install(src, found=None):
    """.24mod 파일 하나를 사용자 mods 폴더에 설치한다. 반환 {ok, id, name, version, replaced(바꾼 옛 버전), error, report}.
    - 검사(validate)에서 오류가 있으면 설치하지 않는다.
    - 같은 id가 이미 사용자 mods 폴더에 .24mod로 있으면 새 것으로 바꾼다 (옛 파일은 휴지통 폴더로).
    - 같은 id가 다른 곳(개발 폴더 등)에 있으면 설치하지 않는다 (둘 다 못 켜게 되므로)."""
    import validate as vlib      # 순환 import 피하려고 여기서
    src = os.path.abspath(src)
    if not os.path.isfile(src) or not src.lower().endswith(MOD_EXT):
        return {"ok": False, "error": "%s 파일만 설치할 수 있어요" % MOD_EXT}
    rep = vlib.validate(src)
    if not rep.to_dict()["ok"]:
        return {"ok": False, "error": "모드 검사에서 오류가 나서 설치하지 않았어요", "report": vlib.format_text(rep)}
    mod = _load_one(src)
    os.makedirs(USER_MODS, exist_ok=True)
    found = scan()[0] if found is None else found
    dst = os.path.join(USER_MODS, mod.id + MOD_EXT)
    replaced = None
    for o in found:
        if o.id != mod.id or os.path.normcase(o.path) == os.path.normcase(dst):
            continue
        return {"ok": False, "error": "같은 id(%s)의 모드가 다른 곳에 이미 있어요: %s. 그쪽을 지우거나 옮긴 뒤 설치해 주세요" % (mod.id, o.path)}
    if os.path.exists(dst):
        old = _load_one(dst) if zipfile.is_zipfile(dst) else None
        replaced = old.version if old else "?"
        if os.path.normcase(src) == os.path.normcase(dst):
            return {"ok": False, "error": "이미 설치된 파일이에요"}
        _to_trash(dst)
    tmp = dst + ".part"
    shutil.copyfile(src, tmp)
    os.replace(tmp, dst)
    return {"ok": True, "id": mod.id, "name": mod.name, "version": mod.version, "replaced": replaced, "path": dst}


def removable(mod):
    """앱에서 지울 수 있는 모드인가 (사용자 mods 폴더 안의 .24mod만. 개발 폴더는 직접 지우게 한다)."""
    return mod.kind == "file" and os.path.normcase(os.path.dirname(os.path.abspath(mod.path))) == os.path.normcase(os.path.abspath(USER_MODS))


def uninstall(mod):
    """설치한 .24mod를 휴지통 폴더로 옮긴다 (데이터 폴더와 설정은 그대로). 반환 {ok, trash, error}."""
    if not removable(mod):
        return {"ok": False, "error": "개발 폴더 모드나 mods 폴더 밖의 모드는 앱에서 지우지 않아요. 직접 지워 주세요: %s" % mod.path}
    try:
        return {"ok": True, "trash": _to_trash(mod.path)}
    except OSError as e:
        return {"ok": False, "error": "지우지 못했어요: %s" % e}


# ---- 켜고 끄기 ----
_elock = threading.Lock()


def _read_json(path, default):
    try:
        with open(path, encoding="utf-8-sig") as f:
            v = json.load(f)
        return v if isinstance(v, type(default)) else default
    except (OSError, ValueError):
        return default


def _write_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def is_enabled(mod):
    v = _read_json(ENABLED_PATH, {}).get(mod.id)
    return bool(mod.manifest.get("default_enabled", True)) if v is None else bool(v)


def set_enabled(mod_id, on):
    with _elock:
        d = _read_json(ENABLED_PATH, {})
        d[mod_id] = bool(on)
        _write_json(ENABLED_PATH, d)


def auto_disabled():
    """오류가 반복돼서 로더가 자동으로 끈 모드: {id: {"time", "reason", "source"(js/python)}}. 사용자가 다시 켜기 전까지 유지된다."""
    return _read_json(AUTO_PATH, {})


def auto_disable(mod_id, reason, source):
    """자동으로 끈 기록을 남긴다. 이미 있으면 False (같은 이유를 여러 번 알리지 않게)."""
    with _elock:
        d = _read_json(AUTO_PATH, {})
        if mod_id in d:
            return False
        d[mod_id] = {"time": time.strftime("%Y-%m-%d %H:%M:%S"), "reason": str(reason)[:400], "source": source}
        _write_json(AUTO_PATH, d)
        return True


def clear_auto_disabled(mod_id):
    with _elock:
        d = _read_json(AUTO_PATH, {})
        if d.pop(mod_id, None) is None:
            return False
        _write_json(AUTO_PATH, d)
        return True


def active(mods_list):
    """켜져 있고 문제가 없고 자동으로 꺼지지 않았고 필요한 권한을 받은 모드."""
    off = auto_disabled()
    return [m for m in mods_list if is_enabled(m) and not m.problems and m.id not in off and not m.needs_permission()]


# ---- 권한 (M10): 자동 허용이 아닌 기능(pc, raw, hook, write)은 사용자가 앱에서 허용해야 모드가 켜진다 ----
# ~/m24ga_data/permissions.json  {모드 id: {"granted": [기능 이름], "time": 시각, "how": "user" | "upgrade"}}
def _perm_path():
    return os.path.join(DATA, "permissions.json")


def granted(mod_id):
    v = _read_json(_perm_path(), {}).get(mod_id) or {}
    return list(v.get("granted") or [])


def grant(mod_id, cap_names, how="user"):
    """기능들을 허용한다 (이미 허용한 것에 더한다)."""
    with _elock:
        d = _read_json(_perm_path(), {})
        cur = set((d.get(mod_id) or {}).get("granted") or [])
        d[mod_id] = {"granted": sorted(cur | set(cap_names)), "time": time.strftime("%Y-%m-%d %H:%M:%S"), "how": how}
        _write_json(_perm_path(), d)


def revoke(mod_id):
    with _elock:
        d = _read_json(_perm_path(), {})
        if d.pop(mod_id, None) is not None:
            _write_json(_perm_path(), d)


def init_permissions(mods_list):
    """권한 파일이 처음 생길 때(코어 0.4.0으로 올린 첫 실행) 한 번만: 그때 켜져 있던 모드의 지금 기능을 허용한 것으로 기록한다.
    (업데이트했다고 쓰던 모드가 갑자기 꺼지지 않게. 이후 새 위험 기능이 늘면 다시 묻는다.) 반환: 기록한 모드 id 목록."""
    if os.path.exists(_perm_path()):
        return []
    done = []
    with _elock:
        if os.path.exists(_perm_path()):
            return []
        d = {}
        for m in mods_list:
            if is_enabled(m) and not m.problems:
                el = caps.elevated(m.caps)
                if el:
                    d[m.id] = {"granted": sorted(el), "time": time.strftime("%Y-%m-%d %H:%M:%S"), "how": "upgrade"}
                    done.append(m.id)
        _write_json(_perm_path(), d)
    return done


# ---- 모드 설정 ----
# mod.json "settings": [{"key": "api.model", "type": "text|password|bool|int|number|select", "label": ..., "default": ...,
#                        "min": .., "max": .., "options": [..], "help": ..}]
# 값은 모드 데이터 폴더의 "settings_file"(기본 settings.json)에 key의 점(.)을 따라 중첩해서 저장한다.
def settings_path(mod):
    return os.path.join(mod.data_dir, mod.manifest.get("settings_file") or "settings.json")


def _dget(d, key):
    for part in key.split("."):
        if not isinstance(d, dict) or part not in d:
            return None, False
        d = d[part]
    return d, True


def _dset(d, key, value):
    parts = key.split(".")
    for part in parts[:-1]:
        if not isinstance(d.get(part), dict):
            d[part] = {}
        d = d[part]
    d[parts[-1]] = value


def opt_values(spec):
    """select 항목의 허용 값. options는 문자열 또는 {"value", "label"}."""
    return [o["value"] if isinstance(o, dict) else o for o in spec.get("options", [])]


def _coerce(spec, v):
    """설정 값 검사. 틀리면 ValueError."""
    t = spec["type"]
    if t == "bool":
        if isinstance(v, bool):
            return v
        raise ValueError("true/false여야 함")
    if t in ("int", "number"):
        if isinstance(v, bool):
            raise ValueError("숫자여야 함")
        v = int(v) if t == "int" else float(v)
        if ("min" in spec and v < spec["min"]) or ("max" in spec and v > spec["max"]):
            lo, hi = spec.get("min"), spec.get("max")
            raise ValueError("범위 %s~%s" % (lo, hi) if lo is not None and hi is not None else ("%s 이상" % lo if lo is not None else "%s 이하" % hi))
        return v
    if t == "select":
        if v not in opt_values(spec):
            raise ValueError("허용 값: %s" % opt_values(spec))
        return v
    if not isinstance(v, str):
        raise ValueError("문자열이어야 함")
    return v


def load_settings(mod):
    """{key: 값}. 파일에 없거나 틀린 값은 기본값."""
    cur = _read_json(settings_path(mod), {})
    out = {}
    for s in mod.manifest.get("settings") or []:
        v, ok = _dget(cur, s["key"])
        try:
            out[s["key"]] = _coerce(s, v) if ok else s.get("default")
        except (ValueError, TypeError):
            out[s["key"]] = s.get("default")
    return out


def settings_view(mod):
    """GUI용: {"specs": [...], "values": {key: 값}, "set": {password key: 저장돼 있는지}}.
    password 값은 화면으로 보내지 않는다."""
    vals = load_settings(mod)
    specs = [dict(s) for s in mod.manifest.get("settings") or []]
    is_set = {}
    for s in specs:
        s["options"] = [o if isinstance(o, dict) else {"value": o, "label": str(o)} for o in s.get("options", [])]
        if s["type"] == "password":
            is_set[s["key"]] = bool(vals.get(s["key"]))
            vals[s["key"]] = ""
    return {"specs": specs, "values": vals, "set": is_set}


def save_settings(mod, changes):
    """changes: {key: 값}. 검사에 걸린 항목은 저장하지 않고 {key: 이유}로 돌려준다. 파일의 다른 항목은 그대로 둔다."""
    specs = {s["key"]: s for s in mod.manifest.get("settings") or []}
    cur = _read_json(settings_path(mod), {})
    errs = {}
    for k, v in changes.items():
        if k not in specs:
            errs[k] = "모르는 설정"
            continue
        try:
            _dset(cur, k, _coerce(specs[k], v))
        except (ValueError, TypeError) as e:
            errs[k] = str(e)
    _write_json(settings_path(mod), cur)
    return errs


# ---- 모드 Python 부분 ----
# mod.json "python": "python/main.py". 진입 파일은 run(ctx)를 둔다 (ctx.stop이 켜질 때까지 돌다가 끝낸다).
# status()가 있으면 GUI가 부른다. 같은 폴더의 다른 모듈은 평범하게 import한다 (모드끼리 이름이 겹치면 늦게 켠 쪽을 막는다).
# 게임 날짜·세이브 (M12): 호스트가 코어 알림을 받아 채운다. 게임에 안 붙어 있거나 세이브가 없으면 None
GAME = {"date": None, "save": None}
GAME_DIR = {"dir": None}   # (코어 0.31.0) 마지막으로 붙은 fm.exe의 폴더. 게임이 꺼져도 남겨 둔다


class ModContext:
    def __init__(self, mod, log, post=None):
        self.mod, self.id, self.data_dir = mod, mod.id, mod.data_dir
        self.stop = threading.Event()
        self._log, self._post = log, post
        self._inbox = queue.Queue(maxsize=20000)

    def recv(self, timeout=0):
        """게임 쪽 JS의 api.send(obj)로 온 메시지 하나(dict/list 등). timeout 초 안에 없으면 None (0이면 기다리지 않음, None이면 올 때까지)."""
        try:
            return self._inbox.get_nowait() if timeout is not None and timeout <= 0 else self._inbox.get(timeout=timeout)
        except queue.Empty:
            return None

    def post(self, obj):
        """게임 쪽 JS의 api.recv(fn)로 메시지를 보낸다. obj는 JSON으로 바꿀 수 있어야 한다. 게임에 안 붙어 있으면 False (그 메시지는 버려짐)."""
        return bool(self._post and self._post(self.id, obj))

    def log(self, msg):
        self._log("[%s] %s" % (self.id, msg))

    def settings(self):
        return load_settings(self.mod)

    def game(self):
        """(코어 0.5.0) 지금 게임 상태 {"date": "2035-04-25" 또는 None, "save": {"id", "nonce"} 또는 None}.
        게임에 안 붙어 있거나 세이브를 안 불러왔으면 None. 0.5초마다 갱신된다."""
        return {"date": GAME.get("date"), "save": dict(GAME["save"]) if GAME.get("save") else None}

    def game_dir(self):
        r"""(코어 0.31.0) 붙어 있는 게임의 설치 폴더 (fm.exe가 있는 폴더, 예: C:\Program Files\Epic Games\FootballManager24).
        게임에 한 번도 안 붙었으면 None. 원본 게임 자료(data\*.fmf)를 읽을 때 써요 (DynamicME)."""
        return GAME_DIR.get("dir")

    def save_dir(self):
        """(코어 0.5.0) 지금 세이브 전용 데이터 폴더 <데이터 폴더>/saves/<세이브 id>/ (만들어서 돌려준다). 세이브가 없으면 None.
        세이브마다 따로 기록해야 하는 것(선수별 기록, 진행 상황)은 여기에 둔다."""
        s = GAME.get("save")
        if not s or not s.get("id"):
            return None
        p = os.path.join(self.data_dir, "saves", str(s["id"]))
        os.makedirs(p, exist_ok=True)
        return p


class PyRunner:
    """모드 하나의 Python 부분을 스레드로 실행한다."""

    RESTART_MAX = 3          # RESTART_WINDOW초 안에 이만큼 오류로 끝나면 자동으로 끈다
    RESTART_WINDOW = 60
    RESTART_WAIT = 2.0       # 오류로 끝난 뒤 다시 시작하기 전에 기다리는 시간

    def __init__(self, mod, log, post=None, on_fatal=None):
        self.mod, self.log, self.post, self.on_fatal = mod, log, post, on_fatal
        self.ctx, self.module, self.thread = None, None, None
        self.error = None

    def _import(self):
        root = os.path.abspath(self.mod.python_root())
        for n in os.listdir(root):                      # 모듈 이름 겹침 검사
            name = n[:-3] if n.endswith(".py") else (n if os.path.isdir(os.path.join(root, n)) else None)
            if not name or name == "__pycache__":
                continue
            ex = sys.modules.get(name)
            f = getattr(ex, "__file__", None)
            if f and not os.path.abspath(f).startswith(root + os.sep):
                raise RuntimeError("Python 모듈 이름 '%s'이 이미 다른 곳에서 쓰이고 있음 (%s)" % (name, f))
        if os.path.isdir(PYLIB) and PYLIB not in sys.path:   # 공용 라이브러리는 모드 폴더보다 뒤 (모드 자기 모듈이 먼저)
            sys.path.append(PYLIB)
        if root not in sys.path:
            sys.path.insert(0, root)
        entry = os.path.join(root, os.path.basename(self.mod.manifest["python"]))
        mname = "m24ga_mod_" + self.mod.id.replace("-", "_")
        try:
            mtime = os.path.getmtime(entry)
        except OSError:
            mtime = None
        ex = sys.modules.get(mname)
        if ex is not None and getattr(ex, "__m24_mtime__", None) == mtime:
            return ex
        # 진입 파일이 바뀌었으면 다시 읽는다 (C04: 고친 main.py가 앱을 다시 켜기 전까지 반영되지 않던 문제).
        # 진입 파일이 import한 모드의 다른 모듈은 그대로라서, 그것까지 바꿨으면 앱을 다시 켜야 한다
        spec = importlib.util.spec_from_file_location(mname, entry)
        module = importlib.util.module_from_spec(spec)
        sys.modules[mname] = module
        try:
            spec.loader.exec_module(module)
        except Exception:
            if ex is not None:
                sys.modules[mname] = ex   # 새 코드가 깨졌으면 예전 것을 남긴다 (오류는 위로 알린다)
            else:
                sys.modules.pop(mname, None)
            raise
        module.__m24_mtime__ = mtime
        return module

    def start(self):
        if self.running() or not self.mod.manifest.get("python"):
            return
        self.error = None
        try:
            note = ensure_data(self.mod)
            if note:
                self.log("[%s] %s" % (self.mod.id, note))
            self.module = self._import()
        except Exception as e:  # noqa: BLE001
            self.error = "Python 부분을 불러오지 못함: %r" % e
            self.log("[%s] %s\n%s" % (self.mod.id, self.error, traceback.format_exc()))
            return
        self.ctx = ModContext(self.mod, self.log, self.post)

        def body():
            fails = []
            while not self.ctx.stop.is_set():
                try:
                    self.module.run(self.ctx)
                    return                   # run이 스스로 끝났다 (멈추라고 했거나 할 일을 다 함)
                except Exception as e:  # noqa: BLE001
                    now = time.time()
                    fails = [t for t in fails if now - t < self.RESTART_WINDOW] + [now]
                    self.error = repr(e)[:300]
                    self.log("[%s] Python 오류(%d회째): %r\n%s" % (self.mod.id, len(fails), e, traceback.format_exc()))
                    if len(fails) >= self.RESTART_MAX:
                        reason = "Python 부분이 %d초 안에 %d번 오류로 멈춤: %s" % (self.RESTART_WINDOW, len(fails), self.error)
                        self.log("[%s] 반복 오류라서 자동으로 끕니다" % self.mod.id)
                        if self.on_fatal:
                            self.on_fatal(self.mod.id, reason)
                        return
                    if self.ctx.stop.wait(self.RESTART_WAIT):
                        return
                    self.log("[%s] 다시 시작합니다" % self.mod.id)
        self.thread = threading.Thread(target=body, name="mod-" + self.mod.id, daemon=True)
        self.thread.start()

    def stop(self, timeout=15):
        if self.ctx:
            self.ctx.stop.set()
        if self.thread:
            self.thread.join(timeout)
        self.thread = None

    def running(self):
        return bool(self.thread and self.thread.is_alive())

    def deliver(self, obj):
        """호스트가 게임 쪽 메시지를 이 모드 수신함에 넣는다 (가득 차면 가장 오래된 것을 버림)."""
        ctx = self.ctx
        if not ctx:
            return
        while True:
            try:
                ctx._inbox.put_nowait(obj)
                return
            except queue.Full:
                try:
                    ctx._inbox.get_nowait()
                except queue.Empty:
                    pass

    def call_ui(self, name, args):
        """모드창이 부르는 함수: 모듈의 ui_<name>만 부를 수 있다."""
        if not re.match(r"^[a-z][a-z0-9_]{0,40}$", name or ""):
            raise ValueError("함수 이름 형식 오류")
        fn = getattr(self.module, "ui_" + name, None) if self.module else None
        if not callable(fn):
            raise ValueError("모드에 ui_%s 함수가 없음 (모드가 실행 중이 아닐 수 있다)" % name)
        return fn(*(args or []))

    def status(self):
        fn = getattr(self.module, "status", None)
        if not fn:
            return None
        try:
            return fn()
        except Exception as e:  # noqa: BLE001
            return {"error": repr(e)}


if __name__ == "__main__":   # python -X utf8 loader/mods.py  -> 찾은 모드 목록
    ms, errs = scan()
    print("mods 폴더:", mod_dirs())
    for m in ms:
        print(json.dumps(m.info(), ensure_ascii=False))
    for p, e in errs:
        print("오류:", p, e)
