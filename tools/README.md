# M24GA 분석 도구

모드를 만들 때 FM24를 조사하는 데 쓰는 스크립트다. 게임 파일은 읽기만 한다.

| 도구 | 하는 일 | 사용법 |
|---|---|---|
| `fmdis.py` | `fm.exe`의 RVA가 속한 함수 전체를 디스어셈블한다 (PE 예외 테이블로 함수 범위를 찾고, call 대상·문자열 참조를 표시) | `python -X utf8 -I fmdis.py <pylib 폴더> <fm.exe> <RVA> [RVA …]` |
| `fmfdump.py` | `.fmf` 아카이브 안의 zstd 프레임을 풀어 폴더에 저장한다 | `python fmfdump.py <pylib 폴더> <파일.fmf> <출력 폴더>` |
| `fmfgrep2.py` | `.fmf` 아카이브의 zstd 프레임을 풀면서 정규식으로 검색한다 | `python fmfgrep2.py <pylib 폴더> <정규식> <파일.fmf> [...]` |
| `rtti.py` | `fm.exe`의 클래스 정보(MSVC RTTI)로 vtable ↔ 클래스 이름 ↔ 상속 표를 만든다 (클래스 1만여 개). 결과는 `~/m24ga_data/rtti/`에 캐시. 패키지 필요 없음. Denuvo 빌드라 섹션 이름이 뒤섞여 있어서 크기로 구역을 고른다 | `python -X utf8 rtti.py build` / `find <정규식>` / `vt <RVA>` / `stats` (CLI `classes`가 이걸 쓴다). `PE(...).func_of(rva)`: 예외 테이블로 그 주소가 든 함수의 시작·끝 (CLI `watch-write`가 쓴다) |
| `props_catalog.py` | 속성 전수 조사 결과(scan_*.json)로 속성 등록부 `core/properties.json`과 `docs/PROPERTIES.md`를 만든다 (M55). 이미 적은 뜻(ko)은 유지 | `python -X utf8 props_catalog.py <scan 폴더>` / `--docs` (문서만) |
| `func_vf.py` | 함수 등록부에 클래스 기반 주소 `vf`와 긴 검색 바이트 `find`를 채우고, 빌드가 바뀌었을 때 다시 찾기를 확인한다 (M57, `loader/funcmap.py`) | `python -X utf8 func_vf.py fill` / `check` |
| `ltc_extract.py` | `data/shared.fmf` 안의 한국어 번역 `.ltc`를 CSV로 추출한다 (게임 문구 찾기용) | `python ltc_extract.py [시작 오프셋] [출력.csv]` |

## 준비

필요한 패키지는 `capstone`, `pefile`(fmdis), `zstandard`(fmf·ltc)다. 시스템에 설치하지 않으려면 한 폴더에 받아 두고 그 경로를 첫 인자(`<pylib 폴더>`)나 `ZSTD_DIR` 환경 변수로 넘긴다.

```
pip install --target C:\temp\fm24pylib capstone pefile zstandard
```

## 주의

- 게임 실행 파일이나 아카이브에서 뽑은 결과물(디스어셈블 덤프, `.ltc` CSV 등)은 게임 저작물이므로 **저장소에 올리지 않는다.**
- 주소(RVA)는 FM24 Epic 2026-10-24 빌드 기준이다 (`builds/` 참고).
