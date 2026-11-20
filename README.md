# M24GA

FM24(Epic 빌드)에 모드를 붙이는 오픈소스 로더예요. 모드는 `.24mod` 파일 하나이고, 앱에서 켜고 끄고 설정해요.

> **베타 안내 (0.1.0-beta)**
> - 지금은 **FM24 Epic판 24.4.2(2025-04-16 빌드)** 에서만 확인했어요. 빌드가 안 맞으면 로더가 아무것도 올리지 않고 멈춰요(게임은 안전해요).
> - **Steam판은 아직 확인하지 못했어요.** 같은 코드일 가능성은 높지만 확인 전이에요. Steam판에서 "지원하지 않는 게임 버전"이 나오면 앱 홈의 **빌드 진단 보고서 복사** 버튼(또는 `m24cli build-report`)으로 보고서를 복사해 이슈에 붙여 주세요. 파일 크기, SHA-256, 서명 칸 비교만 들어가고 개인 경로는 지워져요.
> - Python이 있어야 해요(아래 쓰기 참고). 설치 없이 쓰는 배포판은 준비 중이에요.
> - 문서와 화면은 지금 한국어뿐이에요.

- 게임 안에는 [Frida](https://frida.re)로 코어 + 켜진 모드의 스크립트를 하나로 묶어 올려요.
- 모드마다 PC 쪽 Python 부분, 앱 안 모드창, 자동으로 만들어지는 설정 화면을 가질 수 있어요.
- 게임 빌드가 안 맞으면 아무것도 올리지 않아요 (코어는 로더 전체, 모드 전용 주소는 그 모드만).

## 쓰기

1. `pip install --target vendor -r requirements.txt` (이 폴더에 `vendor/`가 생겨요)
2. `start_m24ga.bat` 더블클릭 (또는 `pythonw -X utf8 loader\app.py`)
3. 앱 홈의 큰 버튼으로 로더를 켜면, 게임이 실행될 때 자동으로 연결돼요.
4. 모드는 앱의 **모드 폴더 열기**(`문서\M24GA\mods`)에 `.24mod` 파일을 넣고 **새로 고침**.

터미널에서는 `python -X utf8 loader/host.py` (`--list`, `--check`, `--now`, `--once`).

### CLI (GUI 없이 전체 기능)

`m24cli.bat <명령>` 또는 `python -X utf8 loader/cli.py <명령>`. AI 에이전트가 GUI를 조작하지 않고 직접 제어할 수 있어요.

```
m24cli status                    로더 상태 (게임 연결, 빌드, 모드 요약)
m24cli mods                      모드 목록과 상태
m24cli mod <id>                  모드 상세 정보
m24cli start [--now] [--wait 60] 로더 시작 (--wait: 게임 연결까지 기다리기)
m24cli stop                      로더 끄기
m24cli run [--now] [--once]      포그라운드 실행 (Ctrl+C로 종료)
m24cli enable <id>               모드 켜기
m24cli disable <id>              모드 끄기
m24cli install <파일.24mod>      모드 설치
m24cli uninstall <id>            모드 삭제
m24cli reload <id>               모드 핫 리로드
m24cli grant <id>                위험 기능 권한 허용
m24cli settings <id>             설정 보기
m24cli set <id> <key> <값>       설정 바꾸기
m24cli log <id>                  모드 로그
m24cli report <id>               AI에게 줄 보고서
m24cli validate <경로>           모드 검사
m24cli watch [--until hooked]    상태 모니터링 (JSON 스트림)
```

모든 명령에 `--json`을 붙이면 JSON으로 출력해요 (AI 파싱용). 도움말: `m24cli --help`.
앱(또는 `m24cli run`)이 켜져 있으면 CLI 명령은 그 로더로 전달돼서 실행돼요 (게임 연결·모드 로그가 그쪽에 있어요). 자세한 것은 [docs/CLI.md](docs/CLI.md).

## 모드 만들기

AI(Claude Code, Cursor, ChatGPT 등)와 같이 만든다면 [docs/AI_GUIDE.md](docs/AI_GUIDE.md)의 시작 프롬프트를 쓰세요. 뼈대 만들기와 검사는 도구가 해요.

```
python -X utf8 tools/m24.py new my-mod --python --ui    # 동작하는 뼈대 (AGENTS.md 포함)
python -X utf8 tools/m24.py validate my-mod             # 위치, 이유, 고치는 법을 알려 줘요
python -X utf8 tools/m24.py pack my-mod                 # 검사하고 .24mod로 묶기
```

참고서는 [docs/MODDING.md](docs/MODDING.md), 예제는 [examples/hello](examples/hello)(설정·메시지·모드창)와 [examples/field-hook](examples/field-hook)(설정 읽기·게임 값 읽기·함수 끼어들기)예요. 읽고 쓸 수 있는 게임 값은 [docs/FIELDS.md](docs/FIELDS.md), 끼어들 수 있는 함수는 [docs/FUNCTIONS.md](docs/FUNCTIONS.md), 이 목록을 넓히는 법은 [docs/EXTENDING.md](docs/EXTENDING.md)예요. 이 저장소를 AI로 고친다면 [AGENTS.md](AGENTS.md)를 읽게 하세요. 시험은 `python -X utf8 -m unittest discover -s tests`.

## 포함된 모드

- `mods/ai-social-feed`: **DynamicAiFeed**. 소셜피드 팬 댓글을 게임 데이터와 기사 본문을 읽은 AI 댓글로 바꿔요 (API 키 필요).
- `mods/dynamic-potential`: **DynamicPA** (포텐 유동 변화). 선수의 한 시즌 활약에 따라 잠재력(PA)이 오르내려요. 평가일(기본 7/1)에 평가하고 미리보기·적용·되돌리기. FM24 Dynamic PA 0.9.5(GPL-3.0) 모델을 옮겼어요 ([mods/dynamic-potential/README.md](mods/dynamic-potential/README.md), 출처 [NOTICE.md](mods/dynamic-potential/NOTICE.md)). 게임 값을 쓰므로 사용자 허용이 필요해요.
- `mods/player-value`: **EnhancedFee** (몸값 보정). 사람 구단 선수도 AI 구단처럼 몸값을 매기고, 활약에 따라 몸값 배율을 줘요 ([mods/player-value/README.md](mods/player-value/README.md)).
- `mods/dynamic-me`: **DynamicME** (매치엔진 조정). 엔진 팩을 재시작 없이 적용하고 (전술 스타일·xG 포함), 빠른 조정 58개·세부 값 950칸으로 엔진 값을 직접 바꿔요 ([mods/dynamic-me/README.md](mods/dynamic-me/README.md)).
- 모드·로더 개발: McR.

## 주의

모드는 게임 메모리와 이 PC에서 코드를 실행해요. 출처를 아는 모드만 넣으세요. 게임이 업데이트되면 주소가 바뀌어 로더 업데이트가 필요할 수 있어요 (안 맞으면 아무것도 올리지 않아요).

## 라이선스

GPL-3.0-or-later ([LICENSE](LICENSE)).
