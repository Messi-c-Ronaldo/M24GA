"""M24GA 안전장치 기록: 게임이 비정상 종료했는지 알아내고(안전 모드), 그 기록을 보관한다. GPL-3.0-or-later.

- 게임 프로세스를 열어 두었다가(psutil 없이 Windows API) 끝난 뒤 **종료 코드**를 읽는다. 0xC로 시작하는 코드(NTSTATUS 오류, 예: 0xC0000005 접근 위반)는
  게임이 튕긴 것이고, 0(정상 종료)이나 1(작업 관리자로 종료) 같은 값은 튕긴 게 아니다. 프로세스가 끝난 걸 못 봤으면 코드는 None.
- 스크립트를 올릴 때마다 지금 올라간 모드 목록을 session.json에 적어 둔다. 게임이 튕긴 직후 **모드가 하나라도 올라가 있었으면** 다음 시작 때 안전 모드를 건다.
- 자동으로 끈 모드의 기록은 mods.py(`auto_disabled`)에 있다.

파일 (~/m24ga_data):  session.json (마지막 게임 세션), crashes.json (튕긴 기록, 최근 30개)
"""
import ctypes
import os
import sys
import time
from ctypes import wintypes

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mods as modlib  # noqa: E402

SESSION_PATH = os.path.join(modlib.DATA, "session.json")
CRASH_LOG = os.path.join(modlib.DATA, "crashes.json")
STILL_ACTIVE = 259
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000


def is_crash(code):
    """종료 코드가 게임이 튕긴 것(NTSTATUS 오류 0xC0000000대)인가."""
    return code is not None and (code & 0xF0000000) == 0xC0000000


def code_text(code):
    return "없음" if code is None else "0x%08X" % (code & 0xFFFFFFFF)


class ProcWatch:
    """게임 프로세스를 열어 두고, 끝난 뒤 종료 코드를 읽는다."""

    def __init__(self, pid):
        self.h = None
        try:
            k = ctypes.windll.kernel32
            k.OpenProcess.restype = wintypes.HANDLE
            self.h = k.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid) or None
        except (AttributeError, OSError):
            self.h = None

    def exit_code(self):
        """아직 살아 있거나 알 수 없으면 None."""
        if not self.h:
            return None
        code = wintypes.DWORD()
        if not ctypes.windll.kernel32.GetExitCodeProcess(self.h, ctypes.byref(code)) or code.value == STILL_ACTIVE:
            return None
        return code.value

    def wait_code(self, timeout=5.0):
        """프로세스가 끝나기를 timeout초까지 기다렸다가 종료 코드를 돌려준다 (못 알아내면 None)."""
        end = time.time() + timeout
        while True:
            c = self.exit_code()
            if c is not None or time.time() >= end or not self.h:
                return c
            time.sleep(0.1)

    def close(self):
        if self.h:
            try:
                ctypes.windll.kernel32.CloseHandle(self.h)
            except (AttributeError, OSError):
                pass
            self.h = None


# ---- 세션 기록 ----
def _read():
    return modlib._read_json(SESSION_PATH, {})


def session_set_mods(pid, mods, safe):
    """스크립트를 올릴 때마다: 이 게임 세션에 지금 올라간 모드. 새 게임(pid가 다름)이면 새 세션 기록을 시작한다."""
    s = _read()
    if s.get("pid") != pid or s.get("ended"):
        s = {"pid": pid, "started": time.strftime("%Y-%m-%d %H:%M:%S"), "ended": None, "ack": False, "ever_mods": []}
    s["mods"], s["safe"] = list(mods), bool(safe)
    s["ever_mods"] = sorted(set(s.get("ever_mods", [])) | set(mods))   # 세션 중 한 번이라도 올라간 모드
    modlib._write_json(SESSION_PATH, s)


def session_end(code, reason):
    """게임 세션이 끝났을 때. code=None이면 종료 코드를 모른다 (로더를 먼저 껐을 때 등)."""
    s = _read()
    if not s or s.get("ended"):
        return None
    crash = is_crash(code)
    s["ended"] = {"time": time.strftime("%Y-%m-%d %H:%M:%S"), "code": code, "crash": crash, "reason": reason}
    modlib._write_json(SESSION_PATH, s)
    if crash:
        log = modlib._read_json(CRASH_LOG, [])
        log.append({"time": s["ended"]["time"], "code": code_text(code), "mods": s.get("ever_mods", []), "safe": s.get("safe")})
        modlib._write_json(CRASH_LOG, log[-30:])
    return s


def pending_crash():
    """아직 안전 모드로 알리지 않은, 모드가 올라가 있던 상태에서 튕긴 마지막 세션. 없으면 None."""
    s = _read()
    e = s.get("ended") if s else None
    if e and e.get("crash") and not s.get("ack") and s.get("ever_mods"):
        return {"code": e["code"], "time": e["time"], "mods": s["ever_mods"], "started": s.get("started")}
    return None


def acknowledge_crash():
    s = _read()
    if s:
        s["ack"] = True
        modlib._write_json(SESSION_PATH, s)
