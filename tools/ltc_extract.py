# -*- coding: utf-8 -*-
"""
작성자: DeepSeek (Cline)

FM24 `data/shared.fmf` 안의 한국어 번역 `.ltc`를 파싱해 CSV로 추출한다.

- 입력 : FM24 설치 폴더의 data\\shared.fmf (환경 변수 FM24_FMF로 바꿀 수 있음)
- 출력 : ko_ltc.csv (UTF-8 BOM). 사용법: python ltc_extract.py [시작 오프셋] [출력 csv]
- 출력 CSV는 게임 저작물이므로 저장소에 올리지 않는다.
- 게임 원본 파일은 읽기만 하고 수정하지 않는다.
"""
import sys, os, csv

# zstandard 패키지가 필요하다: pip install zstandard (또는 pip install --target <폴더> zstandard 후 ZSTD_DIR 환경 변수로 그 폴더 지정)
ZSTD_DIR = os.environ.get("ZSTD_DIR")
if ZSTD_DIR and ZSTD_DIR not in sys.path:
    sys.path.insert(0, ZSTD_DIR)
import zstandard as zstd  # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# 기본값은 Epic 기본 설치 경로. 다르면 환경 변수 FM24_FMF로 지정한다. 출력은 두 번째 인자 (기본: 현재 폴더의 ko_ltc.csv)
FMF_PATH = os.environ.get("FM24_FMF", r"C:\Program Files\Epic Games\FootballManager24\data\shared.fmf")
CSV_PATH = "ko_ltc.csv"

MAGIC = b"\x28\xb5\x2f\xfd"   # zstd 프레임 매직
LTC_START = 89248947          # 한국어 .ltc 시작 프레임의 .fmf 오프셋 (기본값)
HDR_SIZE = 33                 # .ltc 헤더 크기 (항목 시작 오프셋)
MAX_BUFFER = 48 * 1024 * 1024  # 재조립 버퍼 상한 (소셜피드 .ltc가 클 수 있음)
WIN = 2 * 1024 * 1024         # 프레임 해제 윈도우

MAX_FLAG = 64                 # flag = 뒤따르는 변형 개수 (1..64 까지 허용)


def iter_frames(data, mv, start):
    """프레임 (오프셋, 해제바이트) 제너레이터. fmfgrep2.py 방식."""
    pos = start
    n = len(data)
    while True:
        i = data.find(MAGIC, pos)
        if i < 0:
            return
        try:
            d = zstd.ZstdDecompressor().decompressobj()
            out = d.decompress(mv[i:i + WIN])
            used = min(WIN, n - i) - len(d.unused_data)
            pos = i + max(used, 4)
            yield i, out
        except Exception:
            pos = i + 4
            continue


def main(start=LTC_START, csv_path=CSV_PATH):
    with open(FMF_PATH, "rb") as f:
        data = f.read()
    mv = memoryview(data)

    buf = bytearray()
    frame_offsets = []
    for off, out in iter_frames(data, mv, start):
        buf += out
        frame_offsets.append(off)
        if len(buf) >= MAX_BUFFER:
            break

    assert buf[0:6] == b"\x03\x01" + b"ctl.", "헤더 시그니처 불일치"

    hdr_ver = buf[0:2]
    hdr_tag = bytes(buf[2:6])
    hdr_u16 = int.from_bytes(buf[6:8], "little")
    hdr_u32_a = int.from_bytes(buf[8:12], "little")
    hdr_zero1 = int.from_bytes(buf[12:16], "little")
    lang_len = int.from_bytes(buf[16:20], "little")
    lang = bytes(buf[20:20 + lang_len]).decode("utf-8")
    hdr_zero2 = int.from_bytes(buf[20 + lang_len:24 + lang_len], "little")

    pos = HDR_SIZE
    rows = []
    group_idx = 0
    flat_idx = 0
    flag_hist = {}
    breakpoints = []

    AUTH_TOKENS = ("[%male#author", "[%female#author", "[%person#author")

    def rd_u32(p):
        return int.from_bytes(buf[p:p + 4], "little")

    while pos < len(buf):
        flag = buf[pos]
        if flag == 0 or flag > MAX_FLAG:
            breakpoints.append((pos, flag, bytes(buf[pos:pos + 16]).hex()))
            break
        flag_hist[flag] = flag_hist.get(flag, 0) + 1
        p = pos + 1
        ok = True
        for v in range(flag):
            if p + 4 > len(buf):
                breakpoints.append((pos, -1, "buffer exhausted"))
                ok = False
                break
            L = rd_u32(p)
            p += 4
            if p + L > len(buf):
                breakpoints.append((pos, -2, "text out of range"))
                ok = False
                break
            text = bytes(buf[p:p + L]).decode("utf-8", "replace")
            p += L
            has_author = 1 if any(t in text for t in AUTH_TOKENS) else 0
            rows.append((group_idx, v, flag, text, has_author, flat_idx))
            flat_idx += 1
        if not ok:
            break
        pos = p
        group_idx += 1

    total_groups = group_idx
    total_flat = flat_idx
    item_data_end = pos
    item_data_len = item_data_end - HDR_SIZE

    os.makedirs(os.path.dirname(csv_path), exist_ok=True)
    with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["index", "variant", "flag", "text",
                    "has_author_token", "index_group", "index_flat"])
        for r in rows:
            index_group, variant, flag, text, has_author, index_flat = r
            w.writerow([index_group, variant, flag, text, has_author,
                        index_group, index_flat])

    print("=== 진단 ===")
    print("헤더 시그니처:", bytes(hdr_ver).hex(), hdr_tag)
    print("헤더 u16(6:8) =", hdr_u16)
    print("헤더 u32_a(8:12) =", hdr_u32_a)
    print("헤더 zero1(12:16) =", hdr_zero1)
    print("언어명 len =", lang_len, "언어명 =", lang)
    print("헤더 zero2 =", hdr_zero2)
    print("항목 시작 오프셋(스트림 내) =", HDR_SIZE)
    print("총 묶음(groups) =", total_groups)
    print("총 문장(flat) =", total_flat)
    print("플래그 분포 =", flag_hist)
    print("항목 데이터 끝 오프셋 =", item_data_end)
    print("항목 데이터 길이 =", item_data_len)
    print("항목데이터끝 - 헤더u32_a =", item_data_end - hdr_u32_a)
    print("breakpoints =", breakpoints)
    print("프레임 수 =", len(frame_offsets))
    print("항목끝 앞 24바이트:", bytes(buf[item_data_end - 24:item_data_end]).hex())
    print("항목끝 뒤 16바이트:", bytes(buf[item_data_end:item_data_end + 16]).hex())

    print("=== 검증 문장 ===")
    checks = [
        "오늘 대단했지",
        "팬클럽이었냐",
        "출전 덕에",
    ]
    for c in checks:
        hits = [(r[0], r[1], r[5]) for r in rows if c in r[3]]
        shown = hits[:5]
        extra = f" (총 {len(hits)}건)" if len(hits) > 5 else ""
        print(f"  '{c}' -> {shown}{extra}")


if __name__ == "__main__":
    start = int(sys.argv[1]) if len(sys.argv) > 1 else LTC_START
    csv_path = sys.argv[2] if len(sys.argv) > 2 else CSV_PATH
    print(f"[ltc_extract] start={start} output={csv_path}")
    main(start, csv_path)
