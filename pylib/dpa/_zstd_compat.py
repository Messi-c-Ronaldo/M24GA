"""zstandard 대신 Python 3.14 기본 compression.zstd로 save_archive가 쓰는 부분만 흉내 낸다 (M24GA 새 코드).

save_archive는 ZstdDecompressor(max_window_size=...).stream_reader(파일).read(n) 과 ZstdError만 쓴다.
"""
from compression import zstd as _z

ZstdError = _z.ZstdError


class ZstdDecompressor:
    def __init__(self, max_window_size=128 * 1024 ** 2):
        log = max(10, (int(max_window_size) - 1).bit_length())
        self._options = {_z.DecompressionParameter.window_log_max: log}

    def stream_reader(self, source):
        return _z.ZstdFile(source, "rb", options=self._options)
