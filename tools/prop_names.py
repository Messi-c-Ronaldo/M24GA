"""속성 코드 이름표 만들기 (M67, 작성: Claude)

게임 파일 두 곳에서 속성 코드 → 화면 이름을 뽑아 ~/m24ga_data/prop_names.tsv(코드, 영어, 게임 언어, 표시 형식, 분류를 탭으로 나눈 줄)를 만든다.
  1. data/game/properties.fmf : 열 정의 `column_table_properties` = 코드(`<integer id="id" value="Pcro">`)와
     이름의 번역 번호(`<translation id="name" translation_id="227798" value="Crossing">`), 분류(`category`),
     표시 형식(`widget_info`의 class: cash_cell = 돈, date_cell = 날짜, person_button = 사람 링크 …)
  2. data/shared.fmf 안의 번역 파일(.ltc): 언어마다 있고, 문장 표 뒤에 (번역 번호, 문장 위치) 표가 붙어 있다.
     번호의 위 8비트는 0x10(보통 문장), 아래 24비트가 번역 번호. 위치의 최상위 비트는 '다른 구역' 표시라 떼고 쓴다.
게임 글이라 저장소에는 넣지 않는다 (각자 자기 게임 파일에서 만든다). CLI `props`·`prop-info`가 이 표가 있으면 이름을 같이 보여 준다.

사용법:
  python -X utf8 tools/prop_names.py [--lang 한국어] [--game <FM24 폴더>] [--pylib <zstandard 폴더>] [--out 파일]
  --lang: 이름을 붙일 언어 (shared.fmf 안의 언어 이름, 기본 한국어). 'English'면 영어만.
  필요한 패키지: zstandard (pip install --target <폴더> zstandard 후 --pylib)
  첫 실행은 shared.fmf(240MB)를 훑어서 2~3분 걸리고, 번역 파일 위치를 ~/m24ga_data/ltc_offsets.json에 적어 두면 다음부터 빨라진다.
"""
import collections
import json
import os
import re
import struct
import sys

MAGIC = b"\x28\xb5\x2f\xfd"
WIN = 2 * 1024 * 1024
HDR = 33   # 번역 파일 머리 크기 (항목 시작 위치)
DEFAULT_GAME = r"C:\Program Files\Epic Games\FootballManager24"


def _zstd(pylib):
    if pylib:
        sys.path.insert(0, pylib)
    import zstandard
    return zstandard


def frames(data, zstd, start=0):
    """압축 프레임 (파일 위치, 풀린 바이트) 제너레이터"""
    mv, pos, n = memoryview(data), start, len(data)
    while True:
        i = data.find(MAGIC, pos)
        if i < 0:
            return
        try:
            d = zstd.ZstdDecompressor().decompressobj()
            out = d.decompress(mv[i:i + WIN])
            pos = i + max(min(WIN, n - i) - len(d.unused_data), 4)
            yield i, out
        except Exception:  # noqa: BLE001
            pos = i + 4


def properties_names(game_dir, zstd):
    """properties.fmf -> {코드: (번역 번호, 영어, 표시 형식, 분류 번역 번호)}"""
    with open(os.path.join(game_dir, "data", "game", "properties.fmf"), "rb") as f:
        data = f.read()
    text = b"".join(out for _, out in frames(data, zstd)).decode("utf-8", "replace")
    names = {}
    for code, body in re.findall(r'<integer id="id" value="([^"]+)"\s*/>(.*?)(?=<integer id="id" value=|\Z)', text, re.S):
        m = re.search(r'<translation id="name" translation_id="(\d+)" type="use" value="([^"]*)"', body)
        if m and code not in names:
            w = re.search(r'<record id="widget_info">.*?<symbol id="class" value="([^"]+)"', body, re.S)
            c = re.search(r'<translation id="category" translation_id="(\d+)"', body)
            names[code] = (int(m.group(1)), re.sub(r"\[COMMENT.*|\[comment.*", "", m.group(2), flags=re.I).strip(),
                           w.group(1) if w else "", int(c.group(1)) if c else 0)
    return names


def ltc_header(out):
    """풀린 첫 프레임이 번역 파일 머리면 언어 이름, 아니면 None"""
    if out[2:6] != b"ctl.":
        return None
    n = int.from_bytes(out[16:20], "little")
    return bytes(out[20:20 + n]).decode("utf-8", "replace")


def find_ltcs(shared, zstd, cache):
    """shared.fmf 안 번역 파일 [(위치, 언어)] — 캐시가 있으면 그걸 쓴다"""
    if os.path.exists(cache):
        try:
            c = json.load(open(cache, encoding="utf-8"))
            if c.get("size") == len(shared):
                return [tuple(x) for x in c["ltcs"]]
        except Exception:  # noqa: BLE001
            pass
    found = [(i, ltc_header(out)) for i, out in frames(shared, zstd) if ltc_header(out)]
    os.makedirs(os.path.dirname(cache), exist_ok=True)
    json.dump({"size": len(shared), "ltcs": found}, open(cache, "w", encoding="utf-8"), ensure_ascii=False)
    return found


def parse_ltc(shared, zstd, start):
    """번역 파일 하나 -> {번역 번호: 첫 문장}. 문장 표(그룹) 뒤의 (번호, 위치) 표를 쓴다"""
    buf = bytearray()
    for i, (_, out) in enumerate(frames(shared, zstd, start)):
        if i > 0 and ltc_header(out):
            break   # 다음 번역 파일 머리가 나왔다 = 이 파일(문장 + 번호 표)은 끝
        buf += out
        if len(buf) > 150 * 1024 * 1024:
            break
    return parse_ltc_buf(buf)


def parse_ltc_buf(buf):
    """풀린 번역 파일 바이트 -> {번역 번호: 첫 문장} (게임 없이 시험할 수 있게 나눔)"""
    end = int.from_bytes(buf[8:12], "little") + 8   # 머리의 u32 = 문장 구역 길이 (문장 구역 끝 = 값 + 8, M67 확인)
    pos, starts, first = HDR, {}, []
    while pos < end:
        flag = buf[pos]
        if flag == 0 or flag > 64:
            break
        starts[pos] = len(first)
        p = pos + 1
        text = None
        for v in range(flag):
            ln = int.from_bytes(buf[p:p + 4], "little")
            if v == 0:
                text = bytes(buf[p + 4:p + 4 + ln]).decode("utf-8", "replace")
            p += 4 + ln
        first.append(text)
        pos = p
    n = struct.unpack_from("<I", buf, pos)[0]
    out = {}
    for i in range(n):
        key, off = struct.unpack_from("<II", buf, pos + 4 + 8 * i)
        g = starts.get((off & 0x7FFFFFFF) + 8)
        if g is not None and (key >> 24) == 0x10:
            out[key & 0xFFFFFF] = first[g]
    return out


def _clean(x):
    return (x or "").replace("\t", " ").replace("\n", " ")


def build(game_dir, lang, pylib, out_path, data_dir):
    zstd = _zstd(pylib)
    names = properties_names(game_dir, zstd)
    print("properties.fmf: 이름이 있는 코드 %d개" % len(names))
    ko = {}
    if lang and lang.lower() != "english":
        with open(os.path.join(game_dir, "data", "shared.fmf"), "rb") as f:
            shared = f.read()
        ltcs = find_ltcs(shared, zstd, os.path.join(data_dir, "ltc_offsets.json"))
        best = {}
        for off, l in ltcs:
            if l == lang:
                best.setdefault(l, []).append(off)
        if lang not in best:
            raise SystemExit("shared.fmf에 '%s' 번역이 없어요 (있는 언어: %s)" % (lang, ", ".join(sorted({l for _, l in ltcs}))))
        for off in best[lang]:   # 같은 언어가 둘(짧은 것·본 문장)이라 번호가 더 많이 풀리는 쪽을 쓴다
            t = parse_ltc(shared, zstd, off)
            if sum(1 for v in names.values() if v[0] in t) > sum(1 for v in names.values() if v[0] in ko):
                ko = t
        print("%s 번역: 코드 %d개 중 %d개에 이름 붙음" % (lang, len(names), sum(1 for v in names.values() if v[0] in ko)))
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8", newline="\n") as f:
        for code in sorted(names):
            tid, en, wcls, cat = names[code]
            f.write("\t".join([code, _clean(en), _clean(ko.get(tid)), wcls, _clean(ko.get(cat))]) + "\n")
    print("->", out_path)
    return len(names)


def main(argv):
    def opt(k, d=None):
        return argv[argv.index(k) + 1] if k in argv else d
    data_dir = os.path.join(os.path.expanduser("~"), "m24ga_data")
    build(opt("--game", os.environ.get("FM24_DIR", DEFAULT_GAME)), opt("--lang", "한국어"), opt("--pylib", os.environ.get("ZSTD_DIR")),
          opt("--out", os.path.join(data_dir, "prop_names.tsv")), data_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
