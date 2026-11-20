# pylib: M24GA 공용 Python 라이브러리 (코어 0.18.0~)

모드의 Python 부분이 같이 쓰는 라이브러리예요. 로더가 이 폴더를 `sys.path` 끝에 넣어서, 모드는 그냥 `import dpa`, `import m24hist`로 써요.
같은 프로세스에서 모드들이 돌기 때문에, 같은 이름의 패키지를 모드마다 따로 넣으면 로더가 불러오기를 거절해요. 그래서 여러 모드가 쓰는 것은 여기에 둬요.

| 이름 | 하는 일 | 출처 |
|---|---|---|
| `dpa/` | FM24 Dynamic PA 0.9.5의 `app/` 계산 모델과 세이브 파일(.fm) 읽기 (읽기 전용) | **FM24 Dynamic PA v0.9.5 (GPL-3.0)**. 계산은 그대로, 모듈끼리의 import를 패키지용(`.모듈`)으로 바꾸고 `save_archive.py`가 `zstandard`가 없을 때 Python 기본 모듈을 쓰게 한 줄을 더한 것이 전부예요. 각 파일 첫 줄에 출처. `_zstd_compat.py`만 M24GA 새 코드 |
| `m24awards.py` | 세이브 파일에서 해마다 주는 상의 역대 수상자(1~3위)와 대회 우승(대회 기록 × 선수 시즌 기록), 구단·대표팀 시즌 베스트 일레븐을 읽어요 (코어 0.19.0~0.20.0) | M24GA 새 코드 (형식은 몸값모드 V12에서 게임 화면과 맞춰 확인) |
| `m24career.py` | 세이브 파일에서 사람(선수·스태프)별 경력 사건 기록(이적·임대·컵 결승·리그 결과·주간/월간/시즌 상·데뷔·첫 골 등)을 읽어요 (코어 0.22.0, 목록 번호 = 게임 필드 player.recordList) | M24GA 새 코드 (형식은 몸값모드 V17에서 실제 경력과 맞춰 확인) |
| `m24hist.py` | 세이브 파일에서 지난 2시즌 리그 기록을 읽어 Dynamic PA와 같은 방식으로 비교군 백분위를 매기고 캐시해요 (`load`, `prior`, `merge`, `find_save`) | M24GA 새 코드 (포텐 모드의 `savehist.py`를 옮김) |

원본의 레이아웃 정보는 Dynamic PA가 참고한 공개 자료에서 왔어요 (barak14/fm-editor, dgarfias/fm_scouter, chilliesdev/fmseasonhub-re). 자세한 목록은 원본의 `SOURCES.txt`를 보세요.

**`dpa/` 파일은 고치지 마세요.** 포텐 모드 시험(`tests/test_dynamic_potential.py`)이 원본 Dynamic PA와 결과가 같은지 봐요.

`dpa/` 원본 제작자: **도와줄께** (FM24 Dynamic PA, 원본 글 https://www.fmkorea.com/10506342571 , 최신 https://www.fmkorea.com/10555327213). 원작자의 허락을 받아 옮겼어요.

라이선스: GPL-3.0-or-later (M24GA 저장소 `LICENSE`).
