"""M24GA 배포판 만들기 (Windows 64비트, Python이 없는 PC에서도 바로 쓰는 폴더/zip). GPL-3.0-or-later.

사용:  python -X utf8 tools/build_dist.py --embed <python-3.14.x-embed-amd64.zip> [--version X]  (기본값 = 코어 버전, loader/mods.py CORE_VERSION)
  - --embed: python.org의 "Windows embeddable package (64-bit)" zip. vendor/의 frida가 cp314용이라 3.14.x여야 해요 (--check로 확인).
  - 결과: dist/M24GA-<버전>-win64/ 와 같은 이름의 .zip
저장소에서 **git이 추적하는 파일만** 복사해요 (키·개인 파일이 섞여 들어가지 않게). vendor/는 설치된 것을 그대로 (캐시·bin 제외).
"""
import argparse
import glob
import os
import shutil
import subprocess
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "loader"))

KEEP_DIRS = ("loader", "core", "builds", "mods", "pylib", "docs", "examples", "tools")
KEEP_FILES = ("LICENSE", "README.md", "README.en.md", "requirements.txt", "AGENTS.md")

LAUNCH_APP = """@echo off
rem M24GA 로더 앱 (더블클릭). 창을 닫으면 모드도 멈춰요. 이 폴더 안의 Python을 써요 (따로 설치할 필요 없음).
cd /d "%~dp0"
start "" "python\\pythonw.exe" -X utf8 loader\\app.py
"""
LAUNCH_CLI = """@echo off
rem M24GA CLI (터미널에서 쓰기). 사용: m24cli <명령>   도움말: m24cli --help
cd /d "%~dp0"
"python\\python.exe" -X utf8 loader\\cli.py %*
"""
FIRST_RUN = """M24GA {ver} 배포판 (Windows 64비트)

1. 압축을 푼 폴더 그대로 쓰세요 (경로에 한글이나 공백이 있어도 돼요).
2. M24GA.bat 을 더블클릭 → 앱이 열려요. 홈의 큰 버튼으로 로더를 켜면 FM24가 실행될 때 자동으로 연결돼요.
3. 모드는 앱의 "모드 폴더 열기"(문서\\M24GA\\mods)에 .24mod 파일을 넣고 "새로 고침".
4. 터미널에서는 m24cli.bat <명령> (m24cli.bat --help).

- 지금은 FM24 Epic판 24.4.2에서 확인했어요. 다른 판(예: Steam)에서 "지원하지 않는 게임 버전"이 나오면 앱 홈의
  "빌드 진단 보고서 복사"를 눌러 보고서를 보내 주세요.
- 앱 화면은 Windows의 WebView2 런타임이 있어야 떠요 (Windows 11에는 기본으로 있어요).
- 모드는 게임 메모리와 이 PC에서 코드를 실행해요. 출처를 아는 모드만 넣으세요.
- 라이선스: GPL-3.0-or-later (LICENSE), 포함된 다른 프로그램은 THIRD_PARTY_LICENSES.txt.
"""


def tracked():
    out = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, check=True, capture_output=True).stdout.decode("utf-8")
    return [p for p in out.split("\0") if p]


def copy_tracked(dst):
    n = 0
    for rel in tracked():
        top = rel.split("/")[0]
        if top not in KEEP_DIRS and rel not in KEEP_FILES:
            continue
        d = os.path.join(dst, rel)
        os.makedirs(os.path.dirname(d), exist_ok=True)
        shutil.copy2(os.path.join(ROOT, rel), d)
        n += 1
    return n


def copy_vendor(dst):
    src = os.path.join(ROOT, "vendor")
    skip_top = {"bin", "__pycache__"}
    n = 0
    for name in os.listdir(src):
        if name in skip_top:
            continue
        s, d = os.path.join(src, name), os.path.join(dst, "vendor", name)
        if os.path.isdir(s):
            shutil.copytree(s, d, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        else:
            os.makedirs(os.path.dirname(d), exist_ok=True)
            shutil.copy2(s, d)
        n += 1
    return n


def setup_python(embed_zip, dst):
    py = os.path.join(dst, "python")
    with zipfile.ZipFile(embed_zip) as z:
        z.extractall(py)
    pth = glob.glob(os.path.join(py, "python*._pth"))
    if not pth:
        raise SystemExit("embeddable zip에 ._pth 파일이 없어요")
    stem = os.path.basename(pth[0])[:-5]            # python314
    with open(pth[0], "w", encoding="utf-8") as f:
        f.write("\n".join([stem + ".zip", ".", "..\\loader", "..\\vendor", ""]))
    return stem


MIT_TEXT = """Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
documentation files (the "Software"), to deal in the Software without restriction, including without limitation the
rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit
persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the
Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE
WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR
OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
"""
EXTRA_NOTICES = [
    ("proxy_tools 0.1.0 (MIT License, Jonathan Tushman, https://github.com/jtushman/proxy_tools)",
     "패키지 메타데이터에 MIT License로 적혀 있지만 라이선스 파일이 들어 있지 않아 표준 MIT 문구를 붙여요.\n\n"
     "Copyright (c) Jonathan Tushman\n\n" + MIT_TEXT),
    ("소스 코드 위치",
     "- frida 17.24.3 (wxWindows Library Licence 3.1): https://github.com/frida/frida , https://github.com/frida/frida-python\n"
     "- pywebview 6.2: https://github.com/r0x0r/pywebview\n"
     "- pythonnet 3.2.1 / clr_loader 0.3.1: https://github.com/pythonnet/pythonnet , https://github.com/pythonnet/clr-loader\n"
     "- cffi, pycparser, bottle, typing_extensions: PyPI 각 프로젝트 페이지\n"
     "- Python 3.14.6 (embeddable package, 수정 없이 포함): https://www.python.org/downloads/ , 포함된 다른 라이브러리 목록 https://docs.python.org/3.14/license.html\n"
     "- M24GA 자체 (GPL-3.0-or-later): 이 배포판에 소스가 그대로 들어 있고, 공개 저장소에서도 받을 수 있어요.\n"),
]


def licenses(dst, py_dir):
    parts = []
    found = set(glob.glob(os.path.join(ROOT, "vendor", "*.dist-info", "licenses", "**", "*"), recursive=True))
    found |= set(glob.glob(os.path.join(ROOT, "vendor", "*.dist-info", "LICENSE*")))
    for lic in sorted(p for p in found if os.path.isfile(p)):
        pkg = os.path.relpath(lic, os.path.join(ROOT, "vendor")).split(os.sep)[0]
        with open(lic, encoding="utf-8", errors="replace") as f:
            parts.append("=" * 72 + "\n%s  (%s)\n" % (pkg, os.path.basename(lic)) + "=" * 72 + "\n" + f.read())
    for name, text in EXTRA_NOTICES:   # 패키지에 라이선스 파일이 없거나 소스 위치를 알려야 하는 것
        parts.append("=" * 72 + "\n%s\n" % name + "=" * 72 + "\n" + text)
    pl = os.path.join(py_dir, "LICENSE.txt")
    if os.path.isfile(pl):
        with open(pl, encoding="utf-8", errors="replace") as f:
            parts.append("=" * 72 + "\nPython (python.org embeddable package)\n" + "=" * 72 + "\n" + f.read())
    with open(os.path.join(dst, "THIRD_PARTY_LICENSES.txt"), "w", encoding="utf-8") as f:
        f.write("M24GA 배포판에 함께 들어 있는 프로그램의 라이선스 (M24GA 자체는 GPL-3.0-or-later, LICENSE 파일)\n\n" + "\n\n".join(parts))
    return len(parts)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--embed", required=True, help="python-3.14.x-embed-amd64.zip")
    ap.add_argument("--version", default=None, help="기본값: 코어 버전 (배포판 버전 = 코어 버전)")
    ap.add_argument("--out", default=os.path.join(ROOT, "dist"))
    a = ap.parse_args()
    if not a.version:
        import mods
        a.version = mods.CORE_VERSION
    if not zipfile.is_zipfile(a.embed):
        raise SystemExit("--embed가 zip 파일이 아니에요")
    name = "M24GA-%s-win64" % a.version
    dst = os.path.join(a.out, name)
    if os.path.exists(dst):
        shutil.rmtree(dst)
    os.makedirs(dst)
    nfiles = copy_tracked(dst)
    nvend = copy_vendor(dst)
    stem = setup_python(a.embed, dst)
    nlic = licenses(dst, os.path.join(dst, "python"))
    for fn, text in (("M24GA.bat", LAUNCH_APP), ("m24cli.bat", LAUNCH_CLI)):
        with open(os.path.join(dst, fn), "w", encoding="utf-8", newline="\r\n") as f:
            f.write(text)
    with open(os.path.join(dst, "처음 읽어 주세요.txt"), "w", encoding="utf-8-sig", newline="\r\n") as f:
        f.write(FIRST_RUN.format(ver=a.version))
    zpath = os.path.join(a.out, name + ".zip")
    if os.path.exists(zpath):
        os.remove(zpath)
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for base, _, files in os.walk(dst):
            for fn in files:
                p = os.path.join(base, fn)
                z.write(p, os.path.join(name, os.path.relpath(p, dst)))
    print("폴더 %s (저장소 파일 %d, vendor 항목 %d, 라이선스 %d, %s)" % (dst, nfiles, nvend, nlic, stem))
    print("zip %s (%.1f MB)" % (zpath, os.path.getsize(zpath) / 1e6))


if __name__ == "__main__":
    main()
