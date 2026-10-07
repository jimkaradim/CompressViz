"""Verify that visual trace events match the compressor's actual token stream."""

from __future__ import annotations

import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from compressviz import lz77, rle
from compressviz.bitio import BitReader
from compressviz.trace import build_trace


def rle_body_from_trace(data: bytes, variant: str) -> bytes:
    events = build_trace("rle", data, {"variant": variant}, max_steps=len(data) + 2)
    out = bytearray()
    for event in events:
        out.append(event["control_byte"])
        if variant == "pairs":
            out.append(data[event["position"]])
        elif "literal_hex" in event:
            out.extend(bytes.fromhex(event["literal_hex"]))
        else:
            out.append(data[event["position"]])
    return bytes(out)


def lz_tokens(blob: bytes):
    mode = blob[0]
    window = int.from_bytes(blob[1:5], "big")
    lookahead = int.from_bytes(blob[5:7], "big")
    n = int.from_bytes(blob[7:11], "big")
    off_bits, len_bits = max(1, window.bit_length()), max(1, lookahead.bit_length())
    reader, produced, tokens = BitReader(blob[11:]), 0, []
    while produced < n:
        if mode == 1:
            if reader.read_bit():
                off, length = reader.read_bits(off_bits), reader.read_bits(len_bits)
                tokens.append((off, length, None))
                produced += length
            else:
                literal = reader.read_bits(8)
                tokens.append((0, 0, literal))
                produced += 1
        else:
            off, length = reader.read_bits(off_bits), reader.read_bits(len_bits)
            literal = reader.read_bits(8)
            tokens.append((off, length, literal))
            produced += length + 1
    return tokens


def main() -> None:
    rng = random.Random(1729)
    cases = [b"", b"A", b"AAAA", b"ABABABAB", b"ABCABCABCABC", bytes(range(64))]
    cases += [bytes(rng.randrange(8) for _ in range(rng.randrange(1, 180))) for _ in range(50)]

    checks = 0
    for data in cases:
        for variant in ("pairs", "packbits"):
            expected = rle.compress(data, variant=variant)[1:]
            assert rle_body_from_trace(data, variant) == expected
            checks += 1
        for mode in ("lz77", "lzss"):
            for window, lookahead in ((16, 8), (256, 18), (4096, 64)):
                blob = lz77.compress(data, window_size=window,
                                     lookahead_size=lookahead, mode=mode)
                actual = lz_tokens(blob)
                events = build_trace(mode, data, {"window_size": window,
                                     "lookahead_size": lookahead}, max_steps=len(data) + 2)
                shown = [(e["offset"], e["length"],
                          e["literal_byte"] if mode == "lzss" else e["next_byte"])
                         for e in events]
                assert shown == actual, (mode, window, lookahead, data)
                checks += 1
    print(f"Trace/token consistency checks passed: {checks}")


if __name__ == "__main__":
    main()
