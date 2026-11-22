# -*- coding: utf-8 -*-
"""M24GA 로더 앱 (GUI). GPL-3.0-or-later.

화면: ui/index.html (pywebview + Edge WebView2). 왼쪽에 깔린 모드 목록, 오른쪽에 선택한 모드의 정보/설정/모드창.
창을 닫으면 스크립트를 내리고 모드 Python 부분을 멈춘다.
실행: python -X utf8 loader/app.py        (--on: 켜자마자 로더 시작)
모드창은 모드가 ui/에 넣은 HTML이다. sandbox iframe 안에서 돌고, postMessage → Api.mod_call → 모드 Python의 ui_<이름>() 순서로만 모드와 통신한다.
"""
import json
import os
import sys
import threading

HERE = os.path.dirname(os.path.abspath(sys.executable)) if getattr(sys, "frozen", False) else os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


def _fatal(err_text):
    """앱이 시작하다 죽을 때 (0.44.1): pythonw(M24GA.bat)는 콘솔이 없어 오류가 안 보이므로 파일로 남기고 알림 창을 띄운다."""
    path = os.path.join(os.path.expanduser("~"), "m24ga_data", "app_error.txt")
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(err_text)
    except OSError:
        path = "(저장 못 함)"
    low = err_text.lower()
    if "webview2" in low or "edgechromium" in low or "winforms" in low:
        hint = ("앱 화면에 필요한 Microsoft Edge WebView2 런타임이 없거나 고장 난 것 같아요.\n"
                "https://developer.microsoft.com/microsoft-edge/webview2/ 에서 'Evergreen Bootstrapper'를 설치한 뒤 다시 실행해 주세요.")
    elif "clr" in low or "pythonnet" in low or ".net" in low:
        hint = ".NET Framework 4.8이 필요해요. Microsoft에서 '.NET Framework 4.8 Runtime'을 설치한 뒤 다시 실행해 주세요."
    elif "no module named" in low or "dll load failed" in low or "_frida" in low:
        hint = ("프로그램 파일이 빠졌거나 막혔어요. zip을 우클릭 → 속성 → '차단 해제'를 체크한 뒤 새 폴더에 다시 압축을 풀어 주세요.\n"
                "zip 안에서 바로 실행하지 말고, 백신이 파일(frida 등)을 지우지 않았는지도 확인해 주세요.")
    else:
        hint = "아래 오류 파일을 개발자에게 보내 주세요 (GitHub Issues)."
    msg = "M24GA 앱을 시작하지 못했어요.\n\n%s\n\n오류 기록: %s\n\n%s" % (hint, path, err_text.strip().splitlines()[-1][:300] if err_text.strip() else "")
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(None, msg, "M24GA", 0x10)
    except Exception:  # noqa: BLE001
        pass
    sys.stderr.write(msg + "\n\n" + err_text)


try:
    import host  # noqa: E402  (frida 경로 설정도 여기서 한다)
    import mods as modlib  # noqa: E402
    import webview  # noqa: E402
except Exception:  # noqa: BLE001
    import traceback
    _fatal(traceback.format_exc())
    sys.exit(1)

APP_VERSION = modlib.CORE_VERSION
UI_DIR = os.path.join(HERE, "ui")

# 모드창 iframe 첫머리에 넣는 도우미: 테마 CSS, 글꼴, m24.call / m24.toast
HELPER_JS = """<script>
window.m24 = (function () {
  var n = 0, waits = {};
  window.addEventListener('message', function (e) {
    var d = e.data; if (!d || !d.m24 || !waits[d.id]) return;
    var w = waits[d.id]; delete waits[d.id];
    if (d.ok) w.res(d.result); else w.rej(new Error(d.error));
  });
  function post(msg) { parent.postMessage(Object.assign({ m24: 1 }, msg), '*'); }
  return {
    call: function (name) {
      var args = Array.prototype.slice.call(arguments, 1), id = ++n;
      return new Promise(function (res, rej) { waits[id] = { res: res, rej: rej }; post({ id: id, name: name, args: args }); });
    },
    toast: function (msg) { post({ toast: String(msg) }); }
  };
})();
</script>"""


def _read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def _ui_state(st):
    """호스트 상태 -> 화면 상태 (kind, 제목, 설명)."""
    if not st["running"]:
        if st["phase"] == "error":
            return "error", "문제가 생겼어요", st["detail"] or "자세한 내용은 loader.log를 확인해 주세요"
        return "off", "M24GA 꺼짐", "버튼을 누르면 켜져요"
    ph, h = st["phase"], st.get("hook") or {}
    if ph == "waiting":
        return "wait", "게임을 기다리고 있어요", "FM24를 켜면 자동으로 연결돼요"
    if ph == "attaching":
        return "wait", "게임을 찾았어요", st["detail"]
    if ph == "checking":
        return "wait", "게임 버전 확인 중", "잠시만요"
    if ph == "unsupported":
        return "error", "지원하지 않는 게임 버전", "게임이 업데이트됐거나 다른 판(Steam 등)일 수 있어요. 아래 '빌드 진단 보고서 복사'를 눌러 개발자에게 보내 주세요"
    if ph == "hooked":
        if not h:
            return "wait", "연결 중", "잠시만요"
        if h.get("mapsStarted") and not h.get("mapsReady"):
            return "build", "게임 데이터 준비 중", "1분 정도 걸려요. 그동안은 원래 화면이 보여요"
        return "on", "게임에 연결됐어요", "켜진 모드 %d개가 동작 중이에요" % len(h.get("mods") or [])
    return "wait", "준비 중", st.get("detail") or ""


# 창은 Api의 속성으로 두면 안 된다: pywebview가 js_api의 공개 속성을 훑다가 창 내부(WebView2)를 UI 스레드 밖에서 건드려 멈춘다
_WIN = [None]


class Api:
    # ---- 상태 ----
    def get_state(self):
        st = host.status()
        kind, title, desc = _ui_state(st)
        h = st.get("hook") or {}
        return {
            "kind": kind, "title": title, "desc": desc, "running": st["running"], "build": st.get("build"),
            "game": bool(st.get("pid")) and st["phase"] in ("attaching", "checking", "hooked", "unsupported"),
            "maps": "ready" if h.get("mapsReady") else ("building" if h.get("mapsStarted") else ("wait" if h else None)),
            "mods": st["mods"], "errors": st.get("errors", []), "version": APP_VERSION, "safe": host.safe_info(),
            "game_date": (st.get("game") or {}).get("date"), "save_id": ((st.get("game") or {}).get("save") or {}).get("id"),
        }

    def leave_safe_mode(self):
        """안전 모드를 끝내고 켜 둔 모드를 모두 올린다."""
        return {"ok": host.leave_safe_mode()}

    def toggle(self, on):
        if on:
            host.start()
        else:
            host.stop()
        return {"ok": True}

    def rescan(self):
        host.rescan()
        return True

    # ---- 모드 ----
    def set_mod_enabled(self, mod_id, on):
        if not host.find_mod(mod_id):
            return {"ok": False, "error": "모르는 모드"}
        host.set_enabled(mod_id, bool(on))
        return {"ok": True}

    def pick_and_install(self):
        """파일 선택 창을 열어 .24mod를 고르게 하고 설치한다. 취소하면 {cancelled: True}."""
        if _WIN[0] is None:
            return {"ok": False, "error": "창이 없어요"}
        kind = webview.FileDialog.OPEN if hasattr(webview, "FileDialog") else webview.OPEN_DIALOG
        sel = _WIN[0].create_file_dialog(kind, allow_multiple=True, file_types=("M24GA 모드 (*.24mod)",))
        if not sel:
            return {"cancelled": True}
        results = [dict(host.install_mod(p), file=os.path.basename(p)) for p in sel]
        return {"results": results}

    def reload_mod(self, mod_id):
        """모드의 게임 쪽 JS를 지금 파일로 다시 올린다 (코어와 데이터 표는 그대로)."""
        if not host.find_mod(mod_id):
            return {"ok": False, "error": "모르는 모드"}
        if not host.running():
            return {"ok": False, "error": "M24GA가 꺼져 있어요"}
        done = host.reload_mod(mod_id)
        return {"ok": True, "done": bool(done)}

    def grant_permissions(self, mod_id):
        """필요한 위험 기능을 허용하고 모드를 켠다."""
        return {"ok": host.grant_permissions(mod_id)}

    def get_mod_writes(self, mod_id):
        """이 모드의 게임 값 쓰기 기록: {save: 지금 세이브 id, here: 지금 세이브의 기록(최근 30개), here_count, active_count(되돌릴 수 있는 것), total}."""
        save = (host.modlib.GAME.get("save") or {})
        allr = host.write_log(mod_id)
        here = [r for r in allr if (r.get("save") or {}).get("id") == save.get("id")] if save else []
        return {"save": save.get("id"), "here": here[:30], "here_count": len(here),
                "active_count": sum(1 for r in here if not r["undone"]), "total": len(allr)}

    def undo_mod_writes(self, mod_id):
        return host.undo_writes(mod_id)

    def uninstall_mod(self, mod_id):
        return host.uninstall_mod(mod_id)

    def get_mod(self, mod_id):
        m = host.find_mod(mod_id)
        if not m:
            return None
        d = m.info()
        d["settings"] = modlib.settings_view(m)
        d["data_dir"] = m.data_dir
        return d

    def save_mod_settings(self, mod_id, changes):
        m = host.find_mod(mod_id)
        if not m:
            return {"ok": False, "errors": {"": "모르는 모드"}}
        errs = host.save_settings(m, changes)
        return {"ok": not errs, "errors": errs}

    def get_mod_ui(self, mod_id):
        """모드창 HTML (테마 CSS + 도우미를 앞에 넣는다). 없으면 None."""
        m = host.find_mod(mod_id)
        page = m and m.manifest.get("ui")
        if not page:
            return None
        try:
            html = m.read_text(page)
        except (OSError, KeyError):
            return None
        head = ('<meta charset="utf-8"><link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.min.css">'
                '<style>' + _read(os.path.join(UI_DIR, "theme.css")) + '\nbody{overflow:auto;padding:0 2px}</style>' + HELPER_JS)
        return head + html

    def mod_call(self, mod_id, name, args):
        return host.mod_call(mod_id, name, args or [])

    # ---- 로그 탭 ----
    def get_mod_log(self, mod_id, since):
        """since보다 새 로그 항목 {entries, last, errors}."""
        return host.get_mod_log(mod_id, int(since or 0))

    def clear_mod_log(self, mod_id):
        host.clear_mod_log(mod_id)
        return True

    def get_build_report(self):
        """모르는 게임 빌드(Steam판 등)일 때 개발자에게 줄 진단 보고서 글 (M48)."""
        return host.build_report() or ""

    def get_mod_report(self, mod_id):
        """AI에게 붙여 넣을 보고서 글."""
        return host.mod_report(mod_id)

    def get_mod_log_text(self, mod_id):
        """로그 전체를 글로 (복사용)."""
        return "\n".join(host.format_log_entry(e) for e in host.get_mod_log(mod_id, 0)["entries"])

    # ---- 폴더 ----
    def open_mods_folder(self):
        os.makedirs(modlib.USER_MODS, exist_ok=True)
        os.startfile(modlib.USER_MODS)  # noqa: S606
        return True

    def open_mod_data(self, mod_id):
        m = host.find_mod(mod_id)
        if m:
            os.makedirs(m.data_dir, exist_ok=True)
            os.startfile(m.data_dir)  # noqa: S606
        return bool(m)

    def open_log(self):
        os.makedirs(modlib.DATA, exist_ok=True)
        os.startfile(modlib.DATA)  # noqa: S606
        return True


def main():
    import cli      # 다른 터미널의 CLI가 이 앱의 로더를 조종하는 통로 (M18)
    import control
    control.serve(cli.run_captured)
    host.rescan()
    host.check_last_crash()      # 직전 게임이 튕겼으면 로더를 켜기 전부터 안전 모드를 알린다
    api = Api()
    win = webview.create_window(
        "M24GA", url=os.path.join(UI_DIR, "index.html"), js_api=api,
        width=1040, height=700, min_size=(820, 560), background_color="#101013")

    _WIN[0] = win

    def on_closed():
        threading.Thread(target=host.stop, daemon=True).start()

    win.events.closed += on_closed
    if "--on" in sys.argv:   # 켜자마자 로더 시작 (Claude가 화면 클릭 없이 재시작할 때)
        win.events.loaded += lambda: api.toggle(True)
    _webview2_fallback()
    webview.start()
    host.stop()
    control.stop()


def _webview2_fallback():
    """pywebview는 레지스트리(EdgeUpdate\\Clients 'pv')로만 WebView2를 찾는다. 런타임은 깔려 있는데 그 값이 없거나 깨진 PC
    (레지스트리 정리 도구, Edge 제거 도구, 회사 정책 등)에서는 '없다'고 나온다 -> 디스크의 런타임 폴더를 직접 알려 준다 (0.44.3)."""
    import glob
    import winreg
    key = r"Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"
    for root, sub in ((winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\\" + key),
                      (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\\" + key), (winreg.HKEY_CURRENT_USER, r"SOFTWARE\\" + key)):
        try:
            with winreg.OpenKey(root, sub) as k:
                pv = str(winreg.QueryValueEx(k, "pv")[0])
            if int(pv.split(".")[0]) >= 86:
                return   # 레지스트리가 정상 -> pywebview 기본 동작
        except (OSError, ValueError):
            pass
    bases = [os.path.join(os.environ.get(v) or "", "Microsoft", "EdgeWebView", "Application")
             for v in ("ProgramFiles(x86)", "ProgramFiles", "LOCALAPPDATA")]
    found = [os.path.dirname(p) for b in bases if b for p in glob.glob(os.path.join(b, "*", "msedgewebview2.exe"))]

    def ver(p):
        try:
            return tuple(int(x) for x in os.path.basename(p).split("."))
        except ValueError:
            return (0,)
    if found:
        webview.settings["WEBVIEW2_RUNTIME_PATH"] = max(found, key=ver)


if __name__ == "__main__":
    try:
        main()
    except Exception:  # noqa: BLE001  (pywebview가 WebView2를 못 찾을 때 등 — 0.44.1)
        import traceback
        _fatal(traceback.format_exc())
        sys.exit(1)
