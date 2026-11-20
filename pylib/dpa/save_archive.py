# 출처: FM24 Dynamic PA v0.9.5 app/save_archive.py (GPL-3.0-or-later). M24GA 포텐 모드에 넣으면서 import 경로만 패키지용(.모듈)으로 바꿨어요, zstandard가 없으면 Python 3.14 기본 compression.zstd를 써요(_zstd_compat.py). 계산은 그대로예요.
"""Read-only FM24 archive inspection. No game process or save-write API.

Container facts: FM SaveLens 24 docs/FORMAT.md; independent implementation.
All offsets exposed by this module are archive offsets, not player offsets.
"""
from dataclasses import dataclass
from pathlib import Path
import io
import os
import stat
import struct

try:
    import zstandard as zstd
except ImportError:          # M24GA: 앱의 Python(3.14)에는 zstandard가 없을 수 있다
    from . import _zstd_compat as zstd

MAX_INDEX_STORED = 16 * 1024**2
MAX_INDEX_PLAIN = 32 * 1024**2
MAX_MEMBER_PLAIN = 4 * 1024**3
MAX_SAVE_BYTES = 8 * 1024**3
CHUNK = 1024**2


class SaveError(Exception):
    pass


class Cancelled(Exception):
    pass


def check_cancel(cancel):
    if cancel is not None and cancel.is_set():
        raise Cancelled("사용자가 진단을 중지했습니다.")


def fingerprint(st):
    return (st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns)


class IndexCursor:
    def __init__(self, data):
        self.data, self.pos = data, 0

    def take(self, n):
        if n < 0 or self.pos + n > len(self.data):
            raise SaveError("세이브 색인 끝이 잘렸습니다.")
        result = self.data[self.pos:self.pos+n]
        self.pos += n
        return result

    def number(self, width=4):
        return int.from_bytes(self.take(width), "little")

    def text(self):
        n = self.number()
        if n > 16384:
            raise SaveError("세이브 색인의 문자열 길이가 비정상입니다.")
        try:
            return self.take(n).decode("utf-8", errors="strict")
        except UnicodeDecodeError as exc:
            raise SaveError("세이브 색인의 문자를 해석할 수 없습니다.") from exc


@dataclass(frozen=True)
class Member:
    name: str
    offset: int
    stored: int
    plain: int
    index_at: int = 0


class LimitedReader:
    def __init__(self, source, length):
        self.source, self.remaining = source, length

    def read(self, size=-1):
        if size < 0:
            size = self.remaining
        data = self.source.read(min(size, self.remaining))
        self.remaining -= len(data)
        return data


def unpack_index(data):
    c = IndexCursor(data)
    archive_name = c.text()
    members = []

    def group(prefix):
        count = c.number()
        if count > 100000 or len(members) + count > 100000:
            raise SaveError("세이브 구성 파일 수가 지원 범위를 초과합니다.")
        for _ in range(count):
            parts = []
            for _ in range(20):
                part = c.text()
                parts.append(part)
                if part.startswith("."):
                    break
            else:
                raise SaveError("세이브 구성 파일 이름이 비정상입니다.")
            index_at=c.pos
            offset, stored, plain = (c.number(8) for _ in range(3))
            c.take(16)
            members.append(Member(prefix + "".join(parts), offset, stored, plain,index_at))

    group("")
    groups = c.number()
    if groups > 10000:
        raise SaveError("세이브 색인 폴더 수가 비정상입니다.")
    for _ in range(groups):
        group(c.text() + "/")
    names = [m.name for m in members]
    if len(names) != len(set(names)):
        raise SaveError("세이브 색인에 중복된 구성 파일 이름이 있습니다.")
    if "game_db.dat" not in names:
        raise SaveError("선수 데이터베이스 game_db.dat를 찾지 못했습니다.")
    return archive_name, members, len(data) - c.pos


class SaveArchive:
    def __init__(self, path, cancel=None):
        self.path = Path(path)
        self.cancel = cancel
        self.file = self.path.open("rb")
        try:
            st = os.fstat(self.file.fileno())
            if not stat.S_ISREG(st.st_mode):
                raise SaveError("일반 세이브 파일을 선택해 주세요.")
            self.initial_stat = fingerprint(st)
            self.size = st.st_size
            if not 39 <= self.size <= MAX_SAVE_BYTES:
                raise SaveError("세이브 파일이 너무 작거나 8 GiB를 초과합니다.")
            self.header = self.read_at(0, 26)
            if self.header[:7] != bytes.fromhex("0201666d662e08"):
                raise SaveError("지원하는 FM24 세이브 헤더가 아닙니다.")
            method = self.header[25]
            if method not in (0, 3):
                raise SaveError(f"지원하지 않는 압축 방식입니다: {method}")
            self.compressed = method == 3
            self.index_offset = int.from_bytes(self.header[9:17], "little") + 9
            if self.index_offset < 26 or self.index_offset + 13 > self.size:
                raise SaveError("세이브 색인 위치가 파일 범위를 벗어납니다.")
            marker = self.read_at(self.index_offset, 13)
            if marker != bytes.fromhex("0201666d662e08000028b52ffd"):
                raise SaveError("지원하는 FM24 색인 헤더를 찾지 못했습니다.")
            n = self.size - self.index_offset - 9
            if n > MAX_INDEX_STORED:
                raise SaveError("압축된 색인이 16 MiB를 초과합니다.")
            packed = self.read_at(self.index_offset + 9, n)
            try:
                with zstd.ZstdDecompressor(max_window_size=128*1024**2).stream_reader(io.BytesIO(packed)) as r:
                    self.index_bytes = r.read(MAX_INDEX_PLAIN + 1)
            except zstd.ZstdError as exc:
                raise SaveError("세이브 색인의 압축을 풀지 못했습니다.") from exc
            if len(self.index_bytes) > MAX_INDEX_PLAIN:
                raise SaveError("해제된 색인이 32 MiB를 초과합니다.")
            self.archive_name, self.members, self.index_trailing_bytes = unpack_index(self.index_bytes)
            for m in self.members:
                if m.offset + 26 < 26 or m.offset + 26 + m.stored > self.index_offset:
                    raise SaveError(f"구성 파일의 저장 범위가 비정상입니다: {m.name}")
                if m.plain > MAX_MEMBER_PLAIN:
                    raise SaveError(f"구성 파일이 4 GiB를 초과합니다: {m.name}")
                if not self.compressed and m.stored != m.plain:
                    raise SaveError("비압축 구성 파일의 크기가 일치하지 않습니다.")
            spans = sorted((m.offset + 26, m.offset + 26 + m.stored) for m in self.members if m.stored)
            if any(a[1] > b[0] for a, b in zip(spans, spans[1:])):
                raise SaveError("구성 파일의 저장 범위가 서로 겹칩니다.")
            self.assert_unchanged()
        except BaseException:
            self.file.close()
            raise

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.file.close()

    def read_at(self, offset, size):
        check_cancel(self.cancel)
        if offset < 0 or size < 0 or offset + size > self.size:
            raise SaveError("파일을 읽을 위치가 범위를 벗어납니다.")
        self.file.seek(offset)
        data = self.file.read(size)
        if len(data) != size:
            raise SaveError("세이브를 읽는 중 파일이 잘리거나 변경됐습니다.")
        return data

    def assert_unchanged(self):
        check_cancel(self.cancel)
        if fingerprint(os.fstat(self.file.fileno())) != self.initial_stat:
            raise SaveError("진단 중 세이브가 변경됐습니다. 저장이 끝난 뒤 다시 실행해 주세요.")
        try:
            current = fingerprint(self.path.stat())
        except OSError as exc:
            raise SaveError("진단 중 세이브 경로가 없어졌습니다.") from exc
        if current != self.initial_stat:
            raise SaveError("진단 중 같은 경로의 세이브가 교체됐습니다.")

    def chunks(self, member):
        self.assert_unchanged()
        self.file.seek(member.offset + 26)
        limited = LimitedReader(self.file, member.stored)
        reader = None
        total = 0
        try:
            if self.compressed:
                reader = zstd.ZstdDecompressor(max_window_size=128*1024**2).stream_reader(limited)
            source = reader if reader is not None else limited
            while True:
                check_cancel(self.cancel)
                data = source.read(min(CHUNK, member.plain - total + 1))
                if not data:
                    break
                total += len(data)
                if total > member.plain:
                    raise SaveError(f"해제된 크기가 색인보다 큽니다: {member.name}")
                yield data
            if total != member.plain or limited.remaining:
                raise SaveError(f"구성 파일 길이가 색인과 다릅니다: {member.name}")
        except zstd.ZstdError as exc:
            raise SaveError(f"구성 파일 압축을 풀지 못했습니다: {member.name}") from exc
        finally:
            if reader is not None:
                reader.close()
        self.assert_unchanged()

    def small_member(self, name, limit=1024**2):
        member = next(m for m in self.members if m.name == name)
        if member.plain > limit:
            raise SaveError("이 읽기 작업의 크기 제한을 초과합니다.")
        return b"".join(self.chunks(member))
