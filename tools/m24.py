"""M24GA 모드 개발 도구. GPL-3.0-or-later.

  python -X utf8 tools/m24.py new <id> [--name 이름] [--dir 상위폴더] [--python] [--ui]   동작하는 모드 뼈대를 만든다
  python -X utf8 tools/m24.py validate <모드폴더 또는 .24mod> [--json] [--strict]         문제를 찾는다 (위치, 이유, 고치는 법)
  python -X utf8 tools/m24.py pack <모드폴더> [출력폴더] [--force]                         검사한 뒤 .24mod 하나로 묶는다
  python -X utf8 tools/m24.py caps [--check]                                             기능 등록부(core/capabilities.json)로 문서·스키마를 다시 만든다

validate의 종료 코드: 0 = 통과, 1 = 오류 있음 (--strict면 경고도 오류로 친다). 게임이나 frida 없이 돌아간다.
"""
import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "loader"))
sys.path.insert(0, HERE)
import mods as modlib  # noqa: E402
import pack_mod  # noqa: E402
import caps as caplib  # noqa: E402
import validate as vlib  # noqa: E402

TEMPLATES = os.path.join(HERE, "templates")
SCHEMA = os.path.join(ROOT, "docs", "mod.schema.json")

MOD_JS = """// @ts-check
/// <reference path="{rootf}/docs/types/m24ga.d.ts" />
// {name} - 게임 쪽 부분 (Frida JS).
// 로더가 registerMod('{id}', function (api) {{ ... }}) 안에 넣어 주므로 registerMod를 쓰지 않아요.
// 규칙은 같은 폴더의 AGENTS.md와 {root}\\docs\\AI_GUIDE.md를 보세요. 변수는 항상 var로 선언해요.
// DIR = 이 모드의 데이터 폴더 (로더가 넣어 줘요, 끝에 / 포함).

var seen = 0;

api.log('올라왔어요. 데이터 폴더: ' + DIR);   // loader.log에 "game: [{id}] ..."로 남아요

// 소셜 패널(소셜피드 글 한 칸)이 그려질 때마다. ev = {{ th, type, dst, text }}
api.on('socialPanel', function (ev) {{
  seen++;
}});

// 앱/상태에 보여 줄 값
api.status(function () {{ return {{ seen: seen }}; }});
{msg}"""

MOD_JS_MSG = """
// Python 부분과 메시지 주고받기. 메시지는 유실될 수 있으니 연결 직후 hello를 보내 상태를 맞춰요.
api.recv(function (m) {
  if (m.t === 'pong') api.log('Python이 답했어요: ' + m.text);
});
api.send({ t: 'hello' });
"""

PY_MAIN = '''# -*- coding: utf-8 -*-
"""{name}: PC 쪽 부분. 로더가 모드를 켤 때 run(ctx)를 스레드로 불러요. 규칙은 AGENTS.md를 보세요."""
import time

_started = None
_hello = 0


def run(ctx):
    global _started, _hello
    _started, _hello = time.time(), 0
    ctx.log("시작. 설정: %s" % ctx.settings())
    while not ctx.stop.is_set():        # 모드를 끄면 ctx.stop이 켜져요. 15초 안에 끝내야 해요
        m = ctx.recv(0.5)               # 게임 쪽 api.send()로 온 메시지 (0.5초 기다려도 없으면 None)
        if m is None:
            continue
        if m.get("t") == "hello":
            _hello += 1
            ctx.post({"t": "pong", "text": "안녕"})   # 게임 쪽 api.recv()로 가요 (게임에 안 붙어 있으면 버려져요)
    ctx.log("끝")


def status():
    """선택 사항. 앱이 모드 상태를 물을 때."""
    return {"hello": _hello}


# 모드창(ui/index.html)이 m24.call('이름')으로 부르는 함수는 이름이 ui_로 시작해요
def ui_state():
    return {"hello": _hello, "up": int(time.time() - _started) if _started else 0}
'''

UI_HTML = """<!doctype html>
<html lang="ko">
<head><meta charset="utf-8"><title>{name}</title></head>
<body>
<!-- 모드창: 로더가 테마 CSS(.card .stat .btn ...)와 m24.call / m24.toast를 앞에 넣어 줘요. 글자는 textContent로만 넣어요 -->
<div class="stats">
  <div class="stat"><div class="label">hello 받은 횟수</div><div class="value" id="vHello">0</div></div>
  <div class="stat"><div class="label">켜진 지 (초)</div><div class="value" id="vUp">0</div></div>
</div>
<script>
async function tick() {{
  try {{
    const s = await m24.call('state');   // Python의 ui_state()
    document.getElementById('vHello').textContent = s.hello;
    document.getElementById('vUp').textContent = s.up;
  }} catch (e) {{ /* 모드가 멈춘 동안은 조용히 넘겨요 */ }}
}}
tick(); setInterval(tick, 1000);
</script>
</body>
</html>
"""


def schema_ref(folder):
    try:
        return os.path.relpath(SCHEMA, folder).replace("\\", "/")
    except ValueError:                      # 다른 드라이브면 절대 경로
        return "file:///" + SCHEMA.replace("\\", "/")


def cmd_new(a):
    mid = a.id
    if not modlib.ID_RE.match(mid):
        print("id 형식이 잘못됐어요: %r (소문자·숫자·-·_ 만, 소문자나 숫자로 시작, 최대 64자)" % mid)
        return 2
    folder = os.path.abspath(os.path.join(a.dir or os.getcwd(), mid))
    if os.path.exists(folder) and os.listdir(folder):
        print("이미 있고 비어 있지 않아요: %s (다른 id나 --dir를 쓰세요)" % folder)
        return 2
    py = a.python or a.ui
    name = a.name or mid
    m = {"$schema": schema_ref(folder), "id": mid, "name": name, "version": "0.1.0", "description": "한 줄 설명을 적으세요.",
         "author": "", "license": "GPL-3.0-or-later", "core": ">=" + modlib.CORE_VERSION, "js": "mod.js"}
    if py:
        m["python"] = "python/main.py"
    if a.ui:
        m["ui"] = "ui/index.html"
    m["capabilities"] = ["event.socialPanel"] + (["pc.python"] if py else [])   # 쓰는 기능 (docs/CAPABILITIES.md). 새로 쓰면 여기 더한다
    m["settings"] = [{"key": "feature", "type": "bool", "label": "기능 켜기", "default": True, "group": "기본",
                      "help": "설정 항목 예시예요. 앱의 설정 탭이 이 목록에서 자동으로 만들어져요"}]
    os.makedirs(folder, exist_ok=True)
    files = {"mod.json": json.dumps(m, ensure_ascii=False, indent=2) + "\n",
             "mod.js": MOD_JS.format(name=name, id=mid, root=ROOT, rootf=ROOT.replace("\\", "/"), msg=MOD_JS_MSG if py else "")}
    if py:
        files["python/main.py"] = PY_MAIN.replace("{name}", name)   # 딕셔너리 중괄호가 있어서 format을 쓰지 않는다
    if a.ui:
        files["ui/index.html"] = UI_HTML.format(name=name)
    with open(os.path.join(TEMPLATES, "AGENTS.md"), encoding="utf-8") as f:
        files["AGENTS.md"] = f.read().replace("{{ROOT}}", ROOT)
    for rel, text in files.items():
        p = os.path.join(folder, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
    print("만들었어요: %s" % folder)
    for rel in files:
        print("  " + rel)
    rep = vlib.validate(folder)
    print(vlib.format_text(rep))
    print("\n다음: 이 폴더를 문서\\M24GA\\mods 에 넣고(또는 그 안에서 만들고) 앱에서 새로 고침 → 켜기.")
    print("AI와 함께 고칠 때는 이 폴더에서 시작하세요 (AGENTS.md를 먼저 읽어요).")
    return 0 if not rep.errors else 1


def cmd_validate(a):
    rep = vlib.validate(a.path)
    d = rep.to_dict()
    print(json.dumps(d, ensure_ascii=False, indent=2) if a.json else vlib.format_text(rep))
    bad = d["errors"] or (a.strict and d["warnings"])
    return 1 if bad else 0


def cmd_pack(a):
    rep = vlib.validate(a.path)
    if rep.errors and not a.force:
        print(vlib.format_text(rep))
        print("\n오류가 있어서 묶지 않았어요. 고친 뒤 다시 하거나 --force로 그냥 묶을 수 있어요.")
        return 1
    if rep.issues:
        print(vlib.format_text(rep))
    out, n = pack_mod.pack(a.path, a.out or os.path.join(ROOT, "dist"))
    print("만듦: %s (파일 %d개)" % (out, n))
    return 0


CAPS_MD = os.path.join(ROOT, "docs", "CAPABILITIES.md")


def caps_outputs():
    """{경로: 새 내용} - 등록부에서 만드는 파일들 (docs/CAPABILITIES.md, mod.schema.json의 capabilities 항목)."""
    with open(SCHEMA, encoding="utf-8") as f:
        schema = json.load(f)
    schema["properties"]["capabilities"] = {
        "type": "array", "uniqueItems": True, "items": {"enum": caplib.names()},
        "description": "쓰는 기능 (docs/CAPABILITIES.md). 코드에서 쓰는데 없으면 validate 오류. pc/raw/hook/write 등급은 사용자가 앱에서 허용해야 켜진다. 코어 0.4.0부터."}
    fields_md = os.path.join(ROOT, "docs", "FIELDS.md")   # 필드 등록부 문서 (M20)
    return {CAPS_MD: caplib.markdown(), SCHEMA: json.dumps(schema, ensure_ascii=False, indent=2) + "\n", fields_md: caplib.fields_markdown(),
            os.path.join(ROOT, "docs", "FUNCTIONS.md"): caplib.functions_markdown()}


def cmd_caps(a):
    stale = []
    for path, text in caps_outputs().items():
        try:
            with open(path, encoding="utf-8") as f:
                same = f.read() == text
        except OSError:
            same = False
        if same:
            continue
        stale.append(path)
        if not a.check:
            with open(path, "w", encoding="utf-8", newline="\n") as f:
                f.write(text)
    if a.check:
        print("최신이에요" if not stale else "다시 만들어야 해요: " + ", ".join(stale))
        return 1 if stale else 0
    print("만들었어요: " + (", ".join(stale) if stale else "바뀐 것 없음"))
    return 0


def main(argv):
    p = argparse.ArgumentParser(prog="m24", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    n = sub.add_parser("new", help="모드 뼈대 만들기")
    n.add_argument("id")
    n.add_argument("--name")
    n.add_argument("--dir", help="이 안에 <id> 폴더를 만든다 (기본: 지금 폴더)")
    n.add_argument("--python", action="store_true", help="PC 쪽 Python 부분도 만든다")
    n.add_argument("--ui", action="store_true", help="모드창도 만든다 (Python 포함)")
    n.set_defaults(fn=cmd_new)
    v = sub.add_parser("validate", help="모드 검사")
    v.add_argument("path")
    v.add_argument("--json", action="store_true")
    v.add_argument("--strict", action="store_true", help="경고도 오류로 친다")
    v.set_defaults(fn=cmd_validate)
    k = sub.add_parser("pack", help="검사하고 .24mod로 묶기")
    k.add_argument("path")
    k.add_argument("out", nargs="?")
    k.add_argument("--force", action="store_true")
    k.set_defaults(fn=cmd_pack)
    c = sub.add_parser("caps", help="기능 등록부로 docs/CAPABILITIES.md와 스키마 다시 만들기")
    c.add_argument("--check", action="store_true", help="최신인지 확인만 (다르면 종료 코드 1)")
    c.set_defaults(fn=cmd_caps)
    a = p.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
