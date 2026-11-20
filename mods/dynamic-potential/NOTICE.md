# 출처 표기 (NOTICE)

이 모드는 **GNU General Public License v3.0 이상**(GPL-3.0-or-later)으로 배포해요.

## FM24 Dynamic PA 0.9.5 (GPL-3.0)

1.1.0부터 이 파일들은 M24GA 공용 라이브러리 `pylib/dpa/`에 있어요 (몸값 모드도 같이 써요, `pylib/NOTICE.md`). 아래 파일은 FM24 Dynamic PA v0.9.5의 `app/` 파일이에요. **계산은 그대로**이고, 모듈끼리의 import 경로를 패키지용(`.모듈`)으로 바꾸고 `save_archive.py`가 `zstandard`가 없을 때 Python 기본 모듈을 쓰게 한 줄을 더한 것이 전부예요. 각 파일 첫 줄에 출처가 적혀 있어요.

| 파일 | 하는 일 |
|---|---|
| `model.py`, `rules.py`, `model_v07.py` | 평가 모델 (비교군 순위, 상승·하락, 드문 사건, 전체 예산) |
| `league_strength.py`, `transfer_evaluation.py` | 리그 수준 보정, 이적·여러 리그 기록 합산 |
| `scouting_metrics.py` | 포지션별 상세 기록 보정 |
| `development_balance.py` | 유망주 정체·노화 균형 |
| `save_archive.py`, `save_history.py`, `save_context.py`, `club_context.py`, `fm24_profile.py`, `nations.json` | 세이브 파일(.fm)에서 과거 시즌 읽기 (읽기 전용) |

원본의 레이아웃 정보는 Dynamic PA가 참고한 공개 자료에서 왔어요 (barak14/fm-editor, dgarfias/fm_scouter, chilliesdev/fmseasonhub-re). 자세한 목록은 원본의 `SOURCES.txt`를 보세요.

## M24GA 쪽 새 코드

`mod.js`, `python/main.py`, `python/potential.py`, `ui/index.html`과 공용 라이브러리의 `pylib/m24hist.py`(옛 `python/savehist.py`), `pylib/dpa/_zstd_compat.py`는 M24GA 프로젝트가 새로 쓴 코드예요.

- `potential.py`: 게임 자료를 원래 모델 입력으로 바꾸고, 선수별 한국어 설명과 장기 부상 규칙(M24GA 고유), 반기 점검, 대륙컵 가중, 달력형 리그 보정을 더해요.
- `m24hist.py`(공용, 옛 `savehist.py`): 지난 시즌 백분위를 원본 `HistoryStore.prior_rankings`와 같은 방식으로 계산하고 캐시해요.
