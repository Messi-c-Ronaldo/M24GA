"""조종 통로 시험 (M18): 로더 쪽이 연 통로로 CLI 명령이 전달되는지, 토큰이 틀리면 거부되는지. 게임 없이 돈다."""
import json
import os
import shutil
import sys
import tempfile
import unittest
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "loader"))
import mods as modlib  # noqa: E402

try:
    import cli  # noqa: E402
    import control  # noqa: E402
except ImportError:      # pragma: no cover  (frida 없음)
    control = None


@unittest.skipIf(control is None, "frida 없음")
class Control(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.mkdtemp()
        self.saved = modlib.DATA
        modlib.DATA = self.td
        self.calls = []

        def dispatch(argv):
            self.calls.append(argv)
            return (3 if argv[:1] == ["fail"] else 0), "받음: " + " ".join(argv) + "\n"
        control.serve(dispatch)
        with open(control.path(), encoding="utf-8") as f:
            self.info = json.load(f)
        self.info_other = dict(self.info, pid=-1)   # 다른 프로세스가 연 통로인 것처럼 (같은 프로세스면 call이 None)
        with open(control.path(), "w", encoding="utf-8") as f:
            json.dump(self.info_other, f)

    def tearDown(self):
        with open(control.path(), "w", encoding="utf-8") as f:
            json.dump(dict(self.info_other, pid=os.getpid()), f)   # stop()이 내 파일로 알고 지우게
        control.stop()
        modlib.DATA = self.saved
        shutil.rmtree(self.td, ignore_errors=True)

    def test_call_runs_in_server(self):
        self.assertEqual(control.call(["status", "--json"]), (0, "받음: status --json\n"))
        self.assertEqual(control.call(["fail"])[0], 3)
        self.assertEqual(self.calls, [["status", "--json"], ["fail"]])

    def test_wrong_token_is_refused(self):
        req = urllib.request.Request("http://127.0.0.1:%d/" % self.info["port"], data=b'{"argv": ["status"]}',
                                     headers={"X-M24GA-Token": "wrong"})
        with self.assertRaises(urllib.error.HTTPError) as cm:
            urllib.request.urlopen(req, timeout=5)
        self.assertEqual(cm.exception.code, 403)
        cm.exception.close()
        self.assertEqual(self.calls, [])

    def test_no_server_returns_none(self):
        os.remove(control.path())
        self.assertIsNone(control.call(["status"]))

    def test_cli_forwards_and_captures(self):
        # 통로가 있으면 cli.main이 그쪽 결과를 쓰고 종료 코드를 돌려준다
        import contextlib
        import io
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = cli.main(["mods", "--json"])
        self.assertEqual(code, 0)
        self.assertEqual(buf.getvalue(), "받음: mods --json\n")
        # 로컬 전용 명령은 보내지 않는다
        with contextlib.redirect_stdout(io.StringIO()):
            cli.main(["version", "--json"])
        self.assertEqual(self.calls, [["mods", "--json"]])
        # 통로 쪽: run_captured는 출력을 모아 돌려준다
        code, text = cli.run_captured(["version", "--json"])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(text)["core"], modlib.CORE_VERSION)

    def test_act_command_formatting(self):
        # M28: act continue / act click 인자 파싱과 출력 확인 (모의 rpc)
        orig = cli.host.rpc
        seen = []

        def fake_rpc(name, *a):
            seen.append((name, a))
            if a and a[0].get("cmd") == "continue":
                return {"ok": True, "action": "continue", "label": "소셜 피드", "addr": "0xc504f440"}
            return {"ok": True, "action": "click", "cls": "CHECK_BOX", "id": "anLB", "addr": "0xe5c21560",
                    "text": ["분석"], "checked": True, "handled": True}

        cli.host.rpc = fake_rpc
        try:
            code, text = cli.run_captured(["act", "continue"])
            self.assertEqual(code, 0)
            self.assertIn("계속 진행 실행함 (소셜 피드)", text)
            self.assertEqual(seen[-1], ("uiact", ({"cmd": "continue"},)))

            code, text = cli.run_captured(["act", "click", "분석", "--index", "1"])
            self.assertEqual(code, 0)
            self.assertIn('클릭함: CHECK_BOX anLB 0xe5c21560 "분석" -> ☑', text)
            self.assertEqual(seen[-1], ("uiact", ({"cmd": "click", "target": "분석", "index": 1, "partial": False, "confirm": False},)))

            code, text = cli.run_captured(["act", "click", "계약", "--partial", "--yes"])   # M29: --index 없으면 보내지 않음
            self.assertEqual(seen[-1], ("uiact", ({"cmd": "click", "target": "계약", "partial": True, "confirm": True},)))

            code, text = cli.run_captured(["act", "click"])
            self.assertEqual(code, 1)
            self.assertIn("사용: cli.py act click", text)
        finally:
            cli.host.rpc = orig

    def test_continue_wait(self):
        # M30: 계속을 누르고 진행 중 -> 멈춤(바뀐 상태가 1초 그대로)까지 기다린다. 실기 순서(10:30 진행하기 -> 진행 중 -> 12:30 다음 읽기)를 흉내
        base = {"date": "2035-07-02", "clock": "월 10:30", "button": "진행하기", "buttonId": "GCNT", "processing": False,
                "modal": False, "needReply": False, "title": "수신함", "raw": 0x7f326b7}
        seq = [dict(base, processing=True, button="진행 중", raw=0x7f32ab7)] * 2 + [dict(base, clock="월 12:30", button="다음 읽기", raw=0x7f336b7)] * 8
        states = [base] + seq   # 첫 번째 = 누르기 전

        def fake(argv, remote):
            if argv[0] == "act":
                return 0, {"ok": True, "action": "continue", "label": "진행하기"}
            return 0, (states.pop(0) if len(states) > 1 else states[0])
        clock = [0.0]

        def fake_sleep(s):
            clock[0] += s
        import contextlib
        import io
        orig = (cli._jcall, cli.time.sleep, cli.time.time, cli._json_mode)
        cli._jcall, cli.time.sleep, cli.time.time, cli._json_mode = fake, fake_sleep, lambda: clock[0], False
        try:
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                code = cli._continue_wait(["--wait", "5"], remote=True)
            text = buf.getvalue()
        finally:
            cli._jcall, cli.time.sleep, cli.time.time, cli._json_mode = orig
        self.assertEqual(code, 0)
        self.assertIn("후: 2035-07-02 월 12:30  버튼:다음 읽기", text)
        self.assertNotIn("시간 초과", text)

    def test_mail_and_reply(self):
        # M31: ui mail 출력, act reply 옵션 전달(기본 ybut), 이적 메일 거부 메시지
        mail = {"mail": {"title": "Vinci, AC 밀란과의 계약에 합의", "from": "요나스 볼트", "fromJob": "(풋볼 디렉터)", "body": "이적을 마무리할 수 있습니다.",
                         "texts": ["135억 원"], "buttons": [{"addr": "0x1", "id": "ybut", "text": "확인", "kind": "yes"}, {"addr": "0x2", "id": "xbut", "text": "취소", "kind": "no"}],
                         "needReply": True, "risky": True},
                "list": [{"time": "12:11", "from": "요나스 볼트", "title": "Vinci, AC 밀란과의 계약에 합의"}]}
        seen = []

        def fake(name, *a):
            seen.append((name, a))
            if name == "uimail":
                return mail
            return {"error": "'Vinci, AC 밀란과의 계약에 합의'은 이적·계약 관련 메일이라 답하지 않았어요. 정말 답하려면 --yes", "needConfirm": True}
        orig = cli.host.rpc
        cli.host.rpc = fake
        try:
            code, text = cli.run_captured(["ui", "mail"])
            self.assertEqual(code, 0)
            self.assertIn("■ Vinci, AC 밀란과의 계약에 합의", text)
            self.assertIn("확인 [ybut], 취소 [xbut]", text)
            self.assertIn("이적·계약 관련", text)
            code, text = cli.run_captured(["act", "reply"])
            self.assertEqual(code, 1)
            self.assertEqual(seen[-1], ("uiact", ({"cmd": "reply", "target": "ybut", "confirm": False},)))
            cli.run_captured(["act", "reply", "xbut", "--yes"])
            self.assertEqual(seen[-1], ("uiact", ({"cmd": "reply", "target": "xbut", "confirm": True},)))
        finally:
            cli.host.rpc = orig

    def test_play_rules(self):
        # M32: play --days 1 = 답할 메일(기본 규칙) -> 계속 -> 목표 날짜에서 멈춤. 처음 보는 화면이면 멈춤
        st = {"date": "2035-07-09", "button": "답변 요망", "buttonId": "MDSB", "needReply": True, "modal": False}
        calls = []

        def fake(argv, remote):
            calls.append(argv)
            if argv[:2] == ["ui", "state"]:
                return 0, dict(st)
            if argv[:2] == ["ui", "tree"]:
                return 0, {"nodes": []}
            if argv[:2] == ["ui", "mail"]:
                return 0, {"mail": {"title": "첼시, 히츠스페르거에 대해 제의"}}
            if argv[:2] == ["act", "reply"]:
                st.update(button="진행하기", buttonId="GCNT", needReply=False)
                return 0, {"ok": True}
            if argv[:2] == ["act", "continue"]:
                st.update(date="2035-07-10")
                return 0, {"ok": True, "after": dict(st), "secs": 1.0}
            return 0, {"ok": True}
        import contextlib
        import io
        orig = (cli._jcall, cli.time.sleep, cli._json_mode)
        cli._jcall, cli.time.sleep, cli._json_mode = fake, (lambda s: None), False
        try:
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                code = cli._play(["--days", "1", "--manual"], remote=True)
        finally:
            cli._jcall, cli.time.sleep, cli._json_mode = orig
        self.assertEqual(code, 0, buf.getvalue())
        self.assertIn(["act", "reply", "no", "--yes", "--all"], calls)      # 제의 메일 -> no (여러 줄이면 하나씩)
        self.assertIn("목표 날짜 도착", buf.getvalue())

    def test_play_holiday(self):
        # M38: play 기본 = 휴가로 목표 날짜까지 (act holiday --until). 휴가 중(kind -6, busy)이 끝나면 목표 확인
        st = {"date": "2035-08-19", "busy": False, "kind": -19, "modal": False}
        calls, clock = [], [1000.0]

        def fake(argv, remote):
            calls.append(argv)
            if argv[:2] == ["ui", "state"]:
                if st.get("kind") == -6:   # 휴가 중: 상태를 읽을 때마다 하루씩
                    d = cli.datetime.date.fromisoformat(st["date"]) + cli.datetime.timedelta(days=1)
                    st.update(date=d.isoformat())
                    if st["date"] >= "2035-08-22":
                        st.update(busy=False, kind=-19)
                return 0, dict(st)
            if argv[:2] == ["act", "holiday"]:
                st.update(busy=True, kind=-6)
                return 0, {"ok": True}
            return 0, {"ok": True}

        def fake_sleep(sec):
            clock[0] += sec
        import contextlib
        import io
        orig = (cli._jcall, cli.time.sleep, cli.time.time, cli._json_mode)
        cli._jcall, cli.time.sleep, cli.time.time, cli._json_mode = fake, fake_sleep, lambda: clock[0], False
        try:
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                code = cli._play(["--days", "3"], remote=True)
        finally:
            cli._jcall, cli.time.sleep, cli.time.time, cli._json_mode = orig
        self.assertEqual(code, 0, buf.getvalue())
        self.assertIn(["act", "holiday", "--until", "2035-08-22"], calls)
        self.assertFalse(any(c[:2] == ["act", "continue"] for c in calls))   # 버튼·계속 없이
        self.assertIn("목표 날짜 도착", buf.getvalue())

    def test_act_refuses_and_logs(self):
        # M29: 후보가 여러 개면 코어가 누르지 않고 후보를 돌려준다 -> CLI가 후보를 보여 주고 실패. 모든 조작은 act_log.jsonl에
        orig = cli.host.rpc
        cli.host.rpc = lambda name, *a: {"error": "'선수단' 버튼이 2개예요. --index로 하나를 고르세요 (누르지 않았어요)",
                                         "matches": [{"index": 0, "addr": "0x1", "id": "TeSq", "text": "선수단", "cls": "SIDEBAR_LABEL"},
                                                     {"index": 1, "addr": "0x2", "id": None, "text": "선수단", "cls": "BUTTON"}]}
        try:
            code, text = cli.run_captured(["act", "click", "선수단"])
            self.assertEqual(code, 1)
            self.assertIn("#1 선수단  [BUTTON 0x2]", text)
        finally:
            cli.host.rpc = orig
        with open(os.path.join(self.td, "act_log.jsonl"), encoding="utf-8") as f:
            rows = [json.loads(x) for x in f]
        self.assertEqual(rows[-1]["target"], "선수단")
        self.assertFalse(rows[-1]["ok"])


if __name__ == "__main__":
    unittest.main()
