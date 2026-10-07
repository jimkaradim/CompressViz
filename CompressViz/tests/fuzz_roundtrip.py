"""Deterministic stress tests for every CompressViz Python codec.

Run directly with Python; no third-party test runner is required.
"""

from __future__ import annotations

import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from compressviz import adaptive, arithmetic, huffman, lz77, lzw, rle


def main() -> None:
    rng = random.Random(0xC0DEC)
    codecs = [
        ("rle-pairs", lambda d: rle.compress(d, variant="pairs"), rle.decompress),
        ("rle-packbits", lambda d: rle.compress(d, variant="packbits"), rle.decompress),
        ("huffman", huffman.compress, huffman.decompress),
        ("arithmetic", arithmetic.compress, arithmetic.decompress),
        ("adaptive-1", lambda d: adaptive.compress(d, increment=1),
         lambda b: adaptive.decompress(b, increment=1)),
        ("adaptive-32", adaptive.compress, adaptive.decompress),
    ]
    for window in (1, 2, 3, 16, 255, 256, 4096):
        for lookahead in (1, 2, 3, 8, 18, 64):
            for mode in ("lz77", "lzss"):
                codecs.append((
                    f"{mode}-w{window}-l{lookahead}",
                    lambda d, w=window, l=lookahead, m=mode: lz77.compress(
                        d, window_size=w, lookahead_size=l, mode=m),
                    lz77.decompress,
                ))
    for bits in range(9, 17):
        codecs.append((f"lzw-{bits}", lambda d, b=bits: lzw.compress(d, max_bits=b),
                       lzw.decompress))

    cases = [
        b"", b"\x00", b"\xff", bytes(range(256)), bytes(range(255, -1, -1)),
        b"A" * 257, b"AB" * 513, b"ABC" * 1000, bytes(range(256)) * 8,
    ]
    for n in list(range(0, 40)) + [63, 64, 65, 127, 128, 129, 255, 256, 257,
                                    511, 512, 513, 1023, 1024, 2048]:
        cases.append(bytes(rng.randrange(256) for _ in range(n)))
        alphabet = max(1, min(256, 1 + n % 33))
        cases.append(bytes(rng.randrange(alphabet) for _ in range(n)))

    checks = 0
    for name, encode, decode in codecs:
        for index, data in enumerate(cases):
            restored = decode(encode(data))
            if restored != data:
                raise AssertionError(
                    f"{name} failed case {index}, length {len(data)}: "
                    f"{restored[:32]!r} != {data[:32]!r}")
            checks += 1
    print(f"Stress round-trip checks passed: {checks}")


if __name__ == "__main__":
    main()
