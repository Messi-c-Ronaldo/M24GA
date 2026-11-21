# AGENTS.md: DynamicPA (dynamic-potential)를 고치는 AI에게

이 폴더는 **M24GA**(FM24 모드 로더)의 모드 하나예요. 선수의 한 시즌 활약에 따라 잠재력(PA)이 오르내려요. 모델은 FM24 Dynamic PA 0.9.5(GPL-3.0)를 그대로 옮긴 것이고, 모드 쪽 새 코드는 그 입력과 출력을 다뤄요. 코드를 고치기 전에 아래를 지키고, 모르는 것은 **지어내지 말고** 문서를 읽거나 사용자에게 물어보세요.

## 먼저 읽을 것
1. `C:\Program Files\Epic Games\M24GA\docs\AI_GUIDE.md`: 규칙, 할 수 있는 것/없는 것. **반드시 먼저.**
2. `C:\Program Files\Epic Games\M24GA\docs\MODDING.md`, `CAPABILITIES.md`, `types\m24ga.d.ts`(게임 쪽 JS), `types\m24ga.pyi`(Python). **여기에 없는 함수는 없는 거예요.**
3. 이 모드의 개발 기록: `C:\Program Files\Epic Games\logs\포텐모드\` (README → P01~P10). 왜 이렇게 만들었는지, 게임에서 확인한 값, 겪은 사고가 있어요.

## 파일 구성
| 파일 | 하는 일 |
|---|---|
| `mod.json` | 기능 선언(`read.player` `read.date` `read.data` `read.me` `write.player.pa` `pc.python`), 설정 8개 |
| `mod.js` | **게임 안**: ① `collect` 선수 전체를 1,000명씩 0.3초 간격으로 훑어 자료를 Python에 보냄 ② `apply` 초당 9명씩 `api.setPlayerPA` ③ 부상 훑기(1,000명/초, `playerInjury`) ④ `check` 지금 PA 확인 |
| `python/main.py` | **PC 쪽 흐름**: 평가일 감지(5초마다), 요청 → 세이브 읽기 → `collect` → 계산 → 저장 → (auto면) 적용. 모드창 함수 `ui_state/preview/rows/apply/stop/check` |
| `python/potential.py` | 새 코드: 게임 자료 → 모델 입력, 한국어 설명, 장기 부상 규칙, 반기 점검 배율, 대륙컵 가중, 달력형 리그 |
| `M24GA/pylib/m24hist.py` (공용, 1.1.0부터) | 새 코드: 세이브 `.fm`에서 지난 시즌 읽기, 달력형 리그(직전 시즌 보관) 찾기, 캐시(`savehist.pkl`). `main.py`가 `import m24hist as savehist`로 써요 |
| `M24GA/pylib/dpa/` (공용, 1.1.0부터) | **Dynamic PA 0.9.5 원본**(GPL-3.0). 몸값 모드도 같이 써요. 계산은 그대로, import 경로만 바꿨어요. **고치지 마세요** (고치면 원본과 결과가 달라져 시험이 깨져요). `_zstd_compat.py`만 새 코드 |
| `ui/index.html` | 모드창: 평가 소식, 미리보기 표, 적용 버튼, 필터·검색 |

세이브별 자료는 `~\m24ga_data\dynamic-potential\saves\<세이브 id>\`: `preview.json`(마지막 평가) `history.json`(해마다 백분위·부진 여부, 다음 해 3시즌 가중) `state.json`(한 평가일) `injuries.json` `savehist.pkl`.
- **1.2.0부터** `preview`·`history`·`state`·`injuries`는 세이브별 모드 데이터(`ctx.save_data()`, 코어 0.44.0)에 둔다: 게임 저장 때 확정(`~\m24ga_data\savedata\<세이브 id>\dynamic-potential\<키>.json`), 저장 없이 다시 불러오면 되돌아감. 위 폴더의 예전 파일은 처음 읽을 때 한 번 가져온다. `savehist.pkl`(세이브 파일에서 다시 만드는 캐시)은 그대로 위 폴더. 이 기록들은 수 MB라 PC 쪽 전용(게임 쪽 JS에서는 안 보임).

## 꼭 지킬 규칙 (이 모드에서 특히)
- 변수는 항상 `var`. mod.js는 `require`/`import`/`document`/`fetch`를 못 써요. 파일·세이브 작업은 Python 쪽에서.
- **게임 PA 쓰기는 `api.setPlayerPA`로만**, 항상 `expect`(지금 값)를 줘요. 쓰기는 앱이 기록하고 되돌릴 수 있어요. 메모리를 직접 쓰지 마세요.
- **게임 스레드를 오래 붙잡지 마세요.** 선수 12만 명을 훑는 일은 1,000명씩 `api.every`로 나눠요 (P03·P05의 사고: 큰 덩어리가 게임을 3초 멈췄어요). 메모리 훑기는 1MB 조각 + 시간 예산.
- 평가일에 같은 입력이면 **같은 결과**여야 해요 (sha256 결정적 난수). `random`·시간을 계산에 넣지 마세요.
- 새 규칙은 **설정에서 끌 수 있게** 하고, 끄면 원래 모델과 같은 결과가 나와야 해요. `tests/test_dynamic_potential.py`가 원본 Dynamic PA(`~\Downloads\FM24_Dynamic_PA_v0.9.5`)와 결과가 같은지 봐요.
- 모드창은 글자를 `textContent`로만 넣어요. `ui_` 함수 이름과 `m24.call('이름')`을 맞춰요. 평가처럼 오래 걸리는 일은 `ui_` 함수 안에서 하지 말고 요청만 걸어요 (`_pending`).
- 로그 줄에 "실패"·"오류"가 있으면 로그 탭이 오류로 표시해요.
- **Python 코드를 고친 뒤에는 앱을 다시 켜야 반영돼요** (모듈이 `sys.modules`에 남아요). 모드를 껐다 켜는 것으로는 안 돼요.

## 작업 순서
1. 코드를 고치고
2. `python -X utf8 C:\Program Files\Epic Games\M24GA\tools\m24.py validate .` (오류 0, 경고는 `zstandard` 하나가 정상)
3. `python -X utf8 -m unittest tests.test_dynamic_potential` (저장소 루트에서)
4. 앱을 다시 켜고 CLI로 확인해요: `python -X utf8 loader\cli.py call dynamic-potential state --json`, `... preview`, `... rows changed "" 20`, `... apply all "[uid]"`(소수), 앱 정보 탭 또는 `cli.py undo dynamic-potential`로 되돌리기. 게임 쪽 변화는 사용자에게 "게임에서 이것만 해 주세요"라고 부탁해요.
5. 안 되면 `~\m24ga_data\loader.log` 마지막 줄 (게임 쪽 `game:`, Python `[PY]`).
6. 끝나면 `python -X utf8 C:\Program Files\Epic Games\M24GA\tools\m24.py pack .`로 `.24mod`를 만들고, `logs\포텐모드\`에 새 로그 파일(`PNN_...md`)을 하나 더해요.

## 있는 것 / 없는 것
- 있는 것: PA 쓰기(`write.player.pa`), 선수 읽기(시즌 기록 대회별, 포지션, 성격, 소속, 부상), 날짜·세이브.
- 없는 것(있다고 가정하지 마세요): 앱 바깥 알림(모드가 알림을 띄우는 API 없음), 소셜피드에 글 올리기(모드 사이 통로 없음), CA·능력치 쓰기, 과거 시즌을 게임 메모리에서 읽기(경력 화면을 열 때만 올라와서 세이브 파일에서 읽어요).
