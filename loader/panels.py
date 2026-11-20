"""M24GA: 게임 안 패널 칸 파일 (M43/M44). GPL-3.0-or-later.

FM24는 켤 때 사용자 폴더(문서\\Sports Interactive\\Football Manager 2024)의 panels\\ 아래 파일 목록을 읽고,
이미 있는 파일의 내용은 대화상자를 띄울 때마다 다시 읽는다 (M43 실기). 그래서 로더가 게임을 켜기 전에
고정 이름의 "패널 칸" 파일(panels\\m24ga\\slot01.xml ~ slotNN.xml)을 만들어 두고, 코어가 띄우기 직전에
모드의 양식으로 만든 XML을 그 칸에 써서 연다 (게임 파일 읽기 함수에 끼어들 필요가 없다).

- 새로 만든 칸은 게임을 다시 켜야 게임이 알아본다 -> ensure_slots()가 알려 준다.
- 기본 스킨 파일을 복사하지 않는다. 칸의 처음 내용은 우리가 쓴 작은 대화상자다.
- 지우기: remove_slots() (모드 로더를 지울 때). 사용자의 다른 패널 폴더는 건드리지 않는다.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mods as modlib  # noqa: E402

SLOTS = 8                      # core/modhost.js의 M24_PANEL_SLOTS와 같아야 한다 (bundle이 넣어 준다)
GAME_PREFIX = "m24ga/"         # 게임 안 경로 (게임이 "panels/"를 붙인다, 확장자 없음)
PLACEHOLDER = (
    '<panel width="420">\n'
    '\t<string id="title" value="M24GA"/>\n'
    '\t<attachment_group class="vertical_arrange_autosize" vertical_gap="10"/>\n'
    '\t<layout class="centre_in_parent_attachment"/>\n'
    '\t<widget class="text" auto_size="vertical" multiline="true" text="M24GA panel slot"/>\n'
    '\t<container>\n'
    '\t\t<attachment_group class="button_arrangement_right"/>\n'
    '\t\t<widget class="primary_icon_tick_button" id="ok" text="OK"/>\n'
    '\t</container>\n'
    '</panel>\n'
)


def fm_user_dir():
    """FM24 사용자 폴더 (문서\\Sports Interactive\\Football Manager 2024). 문서 폴더가 OneDrive로 옮겨져 있어도 실제 위치."""
    return os.path.join(modlib.documents_dir(), "Sports Interactive", "Football Manager 2024")


def slot_dir():
    return os.path.join(fm_user_dir(), "panels", "m24ga")


def slot_name(i):
    return "slot%02d" % i


def slot_file(i):
    return os.path.join(slot_dir(), slot_name(i) + ".xml")


def game_path(i):
    return GAME_PREFIX + slot_name(i)


def missing_slots():
    return [i for i in range(1, SLOTS + 1) if not os.path.isfile(slot_file(i))]


def ensure_slots():
    """칸 파일이 없으면 만든다. 반환 {ok, dir, created: [이름], error}.
    created가 있으면 게임을 (다시) 켜야 그 칸을 쓸 수 있다. FM 사용자 폴더가 없으면 아무것도 만들지 않는다
    (FM24를 한 번도 안 켠 PC: 게임이 폴더를 만든 뒤 다음 로더 시작 때 만든다)."""
    base = fm_user_dir()
    out = {"ok": False, "dir": slot_dir(), "created": [], "error": None}
    if not os.path.isdir(base):
        out["error"] = "FM24 사용자 폴더가 없어요: %s" % base
        return out
    try:
        os.makedirs(slot_dir(), exist_ok=True)
        for i in missing_slots():
            with open(slot_file(i), "w", encoding="utf-8", newline="\n") as f:
                f.write(PLACEHOLDER)
            out["created"].append(slot_name(i))
        out["ok"] = not missing_slots()
    except OSError as e:
        out["error"] = str(e)
    return out


def slot_dir_if_ready():
    """칸 파일이 다 있으면 그 폴더, 아니면 None (코어에 넘길 값)."""
    return slot_dir() if os.path.isdir(slot_dir()) and not missing_slots() else None


def remove_slots():
    """우리 칸 파일만 지운다 (폴더가 비면 폴더도). 반환 지운 개수."""
    n = 0
    for i in range(1, SLOTS + 1):
        try:
            os.remove(slot_file(i))
            n += 1
        except OSError:
            pass
    try:
        os.rmdir(slot_dir())
    except OSError:
        pass
    return n


if __name__ == "__main__":   # python loader/panels.py [ensure|remove|status]
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    if cmd == "ensure":
        print(ensure_slots())
    elif cmd == "remove":
        print("지움:", remove_slots())
    else:
        print({"dir": slot_dir(), "missing": [slot_name(i) for i in missing_slots()], "ready": bool(slot_dir_if_ready())})
