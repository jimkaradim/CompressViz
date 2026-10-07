"""Δημιουργία απλών βημάτων για την οπτικοποίηση των αλγορίθμων.

Τα πραγματικά bytes και οι μετρήσεις προέρχονται πάντα από τον compressor.
Εδώ κρατάμε μόνο τις πληροφορίες που χρειάζεται να εμφανίσει η εφαρμογή.
"""

from __future__ import annotations

from collections import Counter
import heapq

from . import huffman, lz77


def _char(value: int) -> str:
    if 32 <= value < 127:
        return chr(value)
    return f"0x{value:02X}"


def _bounded(events: list[dict], max_steps: int) -> list[dict]:
    if len(events) <= max_steps:
        return events
    kept = events[: max_steps - 1]
    kept.append({
        "phase": "summary",
        "title": "Περιορισμός οπτικοποίησης",
        "description": (
            f"Εμφανίζονται τα πρώτα {max_steps - 1} από {len(events)} βήματα. "
            "Η συμπίεση και οι μετρικές υπολογίστηκαν για ολόκληρη την είσοδο."
        ),
    })
    return kept


def _rle_trace(data: bytes, max_steps: int, variant: str = "packbits") -> list[dict]:
    events, i = [], 0
    while i < len(data):
        if len(events) >= max_steps - 1:
            events.append({"phase": "summary", "title": "Περιορισμός οπτικοποίησης",
                           "description": f"Η προβολή σταμάτησε στη θέση {i} από {len(data)} bytes."})
            break
        max_run = 255 if variant == "pairs" else 128
        run = 1
        while i + run < len(data) and data[i + run] == data[i] and run < max_run:
            run += 1
        if variant == "pairs" or run >= 2:
            events.append({
                "phase": "encode",
                "title": f"Run στη θέση {i}",
                "description": f"Το σύμβολο {_char(data[i])} επαναλαμβάνεται {run} φορά/ές.",
                "position": i,
                "symbol": _char(data[i]),
                "run_length": run,
                "token": f"({run}, {_char(data[i])})",
                "control_byte": 257 - run if variant == "packbits" else run,
            })
            i += run
        else:
            start = i
            i += 1
            while i < len(data) and i - start < 128:
                if i + 2 < len(data) and data[i] == data[i + 1] == data[i + 2]:
                    break
                i += 1
            literal = data[start:i]
            events.append({
                "phase": "encode",
                "title": f"Literal block στη θέση {start}",
                "description": f"Αντιγράφονται αυτούσια {len(literal)} byte(s).",
                "position": start,
                "literal_length": len(literal),
                "control_byte": len(literal) - 1,
                "literal_hex": literal.hex(" "),
            })
    return events


def _huffman_trace(data: bytes, max_steps: int) -> list[dict]:
    freq = Counter(data)
    events = [{
        "phase": "model",
        "title": "Πίνακας συχνοτήτων",
        "description": f"Βρέθηκαν {len(freq)} διαφορετικά σύμβολα.",
        "frequencies": {_char(k): v for k, v in freq.most_common()},
    }]
    heap = [(weight, serial, [_char(symbol)])
            for serial, (symbol, weight) in enumerate(sorted(freq.items()))]
    heapq.heapify(heap)
    serial = len(heap)
    while len(heap) > 1:
        wa, _, a = heapq.heappop(heap)
        wb, _, b = heapq.heappop(heap)
        merged = a + b
        events.append({
            "phase": "tree",
            "title": "Συγχώνευση κόμβων",
            "description": f"{wa} + {wb} = {wa + wb}",
            "left": ", ".join(a[:8]),
            "right": ", ".join(b[:8]),
            "weight": wa + wb,
        })
        heapq.heappush(heap, (wa + wb, serial, merged))
        serial += 1
    lengths = huffman.code_lengths(data)
    codes = huffman.canonical_codes(lengths)
    events.append({
        "phase": "codes",
        "title": "Canonical κώδικες",
        "description": "Οι τελικοί κώδικες προκύπτουν ντετερμινιστικά από τα μήκη.",
        "codes": {
            _char(symbol): format(code, f"0{length}b")
            for symbol, (code, length) in sorted(codes.items())
        },
    })
    return _bounded(events, max_steps)


def _lz_trace(data: bytes, window_size: int, lookahead_size: int,
              mode: str, max_steps: int) -> list[dict]:
    events, pos = [], 0
    matcher = lz77._Matcher(data, window_size)
    while pos < len(data):
        if len(events) >= max_steps - 1:
            events.append({"phase": "summary", "title": "Περιορισμός οπτικοποίησης",
                           "description": f"Η προβολή σταμάτησε στη θέση {pos} από {len(data)} bytes."})
            break
        start = max(0, pos - window_size)
        is_lzss = mode == "lzss"
        cap = lookahead_size if is_lzss else min(lookahead_size, len(data) - pos - 1)
        best_offset, best_length = matcher.find(pos, cap) if cap >= lz77.MIN_MATCH else (0, 0)
        use_match = best_length >= lz77.MIN_MATCH
        if mode == "lz77":
            next_pos = pos + best_length
            next_symbol = data[next_pos] if next_pos < len(data) else None
            consumed = best_length + (1 if next_symbol is not None else 0)
            token = f"({best_offset if use_match else 0}, {best_length if use_match else 0}, " \
                    f"{_char(next_symbol) if next_symbol is not None else 'EOF'})"
        else:
            consumed = best_length if use_match else 1
            token = (f"match({best_offset}, {best_length})" if use_match
                     else f"literal({_char(data[pos])})")
        events.append({
            "phase": "match",
            "title": f"Token στη θέση {pos}",
            "description": "Βρέθηκε αντιστοίχιση." if use_match else "Εκπέμπεται literal.",
            "search_window": data[start:pos].decode("utf-8", errors="replace")[-80:],
            "lookahead": data[pos:pos + lookahead_size].decode("utf-8", errors="replace"),
            "offset": best_offset if use_match else 0,
            "length": best_length if use_match else 0,
            "next_byte": next_symbol if mode == "lz77" else None,
            "literal_byte": data[pos] if mode == "lzss" and not use_match else None,
            "token": token,
        })
        step = max(1, consumed)
        for index in range(pos, min(pos + step, len(data))):
            matcher.insert(index)
        pos += step
    return events


def _lzw_trace(data: bytes, max_bits: int, max_steps: int) -> list[dict]:
    if not data:
        return []
    table = {bytes([i]): i for i in range(256)}
    next_code, width, w, events = 256, 9, bytes([data[0]]), []
    for value in data[1:]:
        if len(events) >= max_steps - 1:
            events.append({"phase": "summary", "title": "Περιορισμός οπτικοποίησης",
                           "description": f"Εμφανίζονται τα πρώτα {max_steps - 1} συμβάντα λεξικού."})
            return events
        c, wc = bytes([value]), w + bytes([value])
        if wc in table:
            w = wc
            continue
        events.append({
            "phase": "dictionary",
            "title": f"Νέα εγγραφή {next_code}",
            "description": f"Εκπομπή κωδικού {table[w]} και εισαγωγή νέας ακολουθίας.",
            "sequence": wc.decode("utf-8", errors="replace"),
            "output_code": table[w],
            "new_code": next_code,
            "code_width": width,
        })
        if next_code < (1 << max_bits):
            table[wc] = next_code
            next_code += 1
            if next_code == (1 << width) and width < max_bits:
                width += 1
        w = c
    events.append({
        "phase": "dictionary",
        "title": "Τελικός κωδικός",
        "description": f"Εκπομπή κωδικού {table[w]}.",
        "output_code": table[w],
        "dictionary_size": len(table),
        "code_width": width,
    })
    return _bounded(events, max_steps)


def _arithmetic_trace(data: bytes, adaptive: bool, max_steps: int) -> list[dict]:
    if not data:
        return []
    counts = Counter({i: 1 for i in range(256)}) if adaptive else Counter(data)
    low, high = 0.0, 1.0
    events = []
    for position, symbol in enumerate(data):
        total = sum(counts.values())
        ordered = sorted(counts)
        cum_low = sum(counts[s] for s in ordered if s < symbol)
        probability = counts[symbol] / total
        span = high - low
        new_low = low + span * cum_low / total
        new_high = new_low + span * probability
        events.append({
            "phase": "interval",
            "title": f"Σύμβολο {position + 1}: {_char(symbol)}",
            "description": "Το τρέχον διάστημα περιορίζεται βάσει της πιθανότητας του συμβόλου.",
            "low_before": low,
            "high_before": high,
            "low_after": new_low,
            "high_after": new_high,
            "probability": probability,
            "model": "adaptive" if adaptive else "static",
        })
        low, high = new_low, new_high
        if adaptive:
            counts[symbol] += 32
        if len(events) >= max_steps:
            break
        # Οι δεκαδικοί αριθμοί χρησιμοποιούνται μόνο για την επεξήγηση.
        if high - low < 1e-12:
            low, high = 0.0, 1.0
    if len(data) > len(events):
        events.append({
            "phase": "summary",
            "title": "Περιορισμός οπτικοποίησης",
            "description": f"Εμφανίζονται {len(events)} από {len(data)} σύμβολα.",
        })
    return events


def build_trace(codec_id: str, data: bytes, params: dict | None = None,
                max_steps: int = 120) -> list[dict]:
    """Return a bounded trace for a codec identifier used by the UI."""
    params = params or {}
    if codec_id == "rle":
        return _rle_trace(data, max_steps, params.get("variant", "packbits"))
    if codec_id == "huffman":
        return _huffman_trace(data, max_steps)
    if codec_id in {"lz77", "lzss"}:
        return _lz_trace(data, params.get("window_size", 4096),
                         params.get("lookahead_size", 18), codec_id, max_steps)
    if codec_id == "lzw":
        return _lzw_trace(data, params.get("max_bits", 12), max_steps)
    if codec_id in {"arithmetic", "adaptive"}:
        return _arithmetic_trace(data, codec_id == "adaptive", max_steps)
    raise KeyError(f"Άγνωστος αλγόριθμος: {codec_id}")
