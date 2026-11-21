"""M24GA 코어 0.2.0: 모드의 Python 부분(python/main.py)에서 쓰는 규약. 편집기 자동완성과 AI 참고용 타입 정의.

AI에게: 여기 없는 속성이나 함수는 없는 거예요. 지어내지 마세요.

모드 진입 파일(mod.json의 "python")이 만들어야 하는 것:

    def run(ctx: ModContext) -> None: ...          # 필수. 모드를 켤 때 스레드로 불러요. ctx.stop이 켜지면 15초 안에 끝내요
    def status() -> dict | None: ...                # 선택. 앱이 상태를 물을 때 (JSON으로 바꿀 수 있는 dict)
    def ui_<이름>(*args) -> Any: ...                # 선택. 모드창이 m24.call('<이름>', ...args)로 불러요. 인자와 결과는 JSON

같은 폴더의 다른 .py는 그냥 import해요. 모드끼리 모듈 이름이 겹치면(config.py 등) 나중에 켜는 모드가 막혀요.
"""
import threading
from typing import Any, Optional


class ModContext:
    """run(ctx)에 주어지는 값."""

    id: str
    """모드 id (mod.json의 id)"""

    data_dir: str
    """모드 데이터 폴더 (기본 ~/m24ga_data/<id>). 파일을 읽고 쓸 때는 이 안에서만"""

    stop: threading.Event
    """모드를 끄거나 로더를 멈추면 켜져요. 반복문에서 확인하세요 (while not ctx.stop.is_set(), ctx.stop.wait(1.0))"""

    def log(self, msg: str) -> None:
        """~/m24ga_data/loader.log에 '[모드id] msg'로 남겨요 (print는 안 보여요)"""

    def settings(self) -> dict[str, Any]:
        """설정 값: {mod.json settings의 key: 값}. key의 점(.)은 그대로 키에 있어요 (예: ctx.settings()["style.swear"]).
        호출할 때마다 설정 파일에서 읽어서, 사용자가 앱에서 바꾸면 다음 호출부터 반영돼요. 없거나 틀린 값은 default"""

    def game(self) -> dict[str, Any]:
        """(코어 0.5.0) {"date": "2035-04-25" 또는 None, "save": {"id": int, "nonce": int} 또는 None}. 게임에 안 붙어 있거나 세이브가 없으면 None"""

    def game_dir(self) -> Optional[str]:
        """(코어 0.31.0) 붙은 게임의 설치 폴더 (fm.exe 폴더). 한 번도 안 붙었으면 None"""

    def actions_for(self, target: Any, all: bool = False) -> list[dict[str, Any]]:
        """(코어 0.41.0, 기능 read.action) 게임 메뉴가 그 대상에 보여 주는 명령 [{id, cls, hidden, disabled, canRun, events, click, confirm, args}].
        target = 'me'|'myteam'|'myclub'|'p123'|'s45'|dref 번호. 실패하면 RuntimeError"""

    def action(self, action_id: str, target: Any, event: Optional[str] = None, danger: bool = False) -> dict[str, Any]:
        """(코어 0.41.0, 기능 game.action, 세이브를 바꿈) 게임 명령 실행 {ok, error, handled}. 게임이 보여 주는 명령만, 1분에 10번"""

    def save_data(self) -> Any:
        """(코어 0.44.0, 기능 save.data) 세이브별 모드 자료: .get(키, 기본값) .set(키, 값) .delete(키) .keys() .all()"""
        ...
    def set_props(self, target: Any, values: dict[str, Any], reason: str = "", tested: bool = False) -> dict[str, Any]:
        """(코어 0.42.0) 여러 속성을 한 번에. 하나라도 실패하면 되돌려요 -> {ok, results, error, rolledBack}"""
        ...
    def set_prop(self, target: Any, code: str, value: Any, expect: Any = None, reason: str = "", tested: bool = False) -> dict[str, Any]:
        """(코어 0.42.0, 기능 write.prop) 게임 속성 하나를 게임 setter로 바꿔요 -> {ok, before, after, code, key, error}"""
        ...
    def props(self, target: str, regex: Optional[str] = None, empty: bool = False) -> dict[str, Any]:
        """(코어 0.39.0, 기능 read.prop) 게임 속성 코드 값 {코드: 값}. target = 'me'|'myteam'|'myclub'|'myjob'|'p123'|'s45'|'team:<번호>'|'comp:<번호>'|'0x주소'.
        게임에 안 붙어 있거나 대상을 못 찾으면 RuntimeError, read.prop이 없으면 PermissionError"""

    def prop(self, target: str, code: str) -> Any:
        """(코어 0.39.0) 속성 하나 (없으면 None)"""

    def save_dir(self) -> Optional[str]:
        """(코어 0.5.0) 지금 세이브 전용 폴더 <데이터 폴더>/saves/<세이브 id>/ (만들어 줘요). 세이브가 없으면 None"""

    def recv(self, timeout: Optional[float] = 0) -> Optional[Any]:
        """게임 쪽 api.send()로 온 메시지 하나 (JSON 값). timeout 초 안에 없으면 None.
        0이면 기다리지 않고, None이면 올 때까지 기다려요. 수신함은 2만 개까지이고 넘치면 오래된 것부터 버려요"""

    def post(self, obj: Any) -> bool:
        """게임 쪽 api.recv()로 메시지를 보내요 (JSON으로 바꿀 수 있어야 해요).
        게임에 안 붙어 있거나 스크립트가 내려가 있으면 False이고 그 메시지는 버려져요. 메시지는 유실될 수 있어요"""
