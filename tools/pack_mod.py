"""모드 폴더를 .24mod 파일 하나로 묶는다 (M24GA M03 로그). GPL-3.0-or-later.

사용: python -X utf8 tools/pack_mod.py mods/ai-social-feed [출력 폴더]
결과: <출력 폴더>/<id>-<version>.24mod  (기본 출력 폴더: dist/)
__pycache__, *.pyc, 숨김 파일은 넣지 않는다.
"""
import json
import os
import sys
import zipfile

SKIP_DIRS = {"__pycache__", ".git"}


def pack(src, out_dir):
    with open(os.path.join(src, "mod.json"), encoding="utf-8") as f:
        m = json.load(f)
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, "%s-%s.24mod" % (m["id"], m["version"]))
    n = 0
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for d, dirs, files in os.walk(src):
            dirs[:] = sorted(x for x in dirs if x not in SKIP_DIRS and not x.startswith("."))
            for fn in sorted(files):
                if fn.endswith(".pyc") or fn.startswith(".") or (fn == "AGENTS.md" and d == src):
                    continue   # 개발용 AI 안내(작성자 PC 경로가 들어 있음)는 배포 파일에 넣지 않는다
                p = os.path.join(d, fn)
                z.write(p, os.path.relpath(p, src).replace("\\", "/"))
                n += 1
    return out, n


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path, count = pack(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else os.path.join(root, "dist"))
    print("만듦: %s (파일 %d개)" % (path, count))
