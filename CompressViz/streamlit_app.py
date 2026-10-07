"""CompressViz — Python/Streamlit visualisation application."""

from __future__ import annotations

from collections import Counter
import csv
import hashlib
import io
import json
import time

import pandas as pd
import streamlit as st

from compressviz import adaptive, arithmetic, huffman, lz77, lzw, rle
from compressviz.trace import build_trace


st.set_page_config(page_title="CompressViz", page_icon="🗜️", layout="wide")

# Οι αλγόριθμοι που εμφανίζονται στο μενού και οι αρχικές τους ρυθμίσεις.
ALGORITHMS = {
    "rle": ("RLE / PackBits", rle, {"variant": "packbits"}),
    "huffman": ("Canonical Huffman", huffman, {}),
    "lz77": ("LZ77", lz77, {"window_size": 4096, "lookahead_size": 18, "mode": "lz77"}),
    "lzss": ("LZSS", lz77, {"window_size": 4096, "lookahead_size": 18, "mode": "lzss"}),
    "lzw": ("LZW", lzw, {"max_bits": 12}),
    "arithmetic": ("Static Arithmetic", arithmetic, {}),
    "adaptive": ("Adaptive Arithmetic", adaptive, {}),
}


def parse_input(mode: str, text: str, uploaded) -> tuple[bytes, str]:
    """Μετατρέπει το κείμενο ή το αρχείο σε bytes για τη συμπίεση."""
    if mode == "Αρχείο":
        if uploaded is None:
            return b"", "Δεν έχει επιλεγεί αρχείο"
        return uploaded.getvalue(), uploaded.name
    return text.encode("utf-8"), "κείμενο UTF-8"


@st.cache_data(show_spinner=False)
def measure(codec_id: str, data: bytes, params_key: tuple) -> dict:
    """Τρέχει έναν αλγόριθμο και συγκεντρώνει τις βασικές μετρήσεις."""
    label, module, params = ALGORITHMS[codec_id]
    params = dict(params_key)
    started = time.perf_counter()
    blob = module.compress(data, **params)
    encode_ms = (time.perf_counter() - started) * 1000
    started = time.perf_counter()
    # Αποσυμπιέζουμε αμέσως, ώστε να ελέγξουμε ότι δεν χάθηκαν δεδομένα.
    restored = module.decompress(blob)
    decode_ms = (time.perf_counter() - started) * 1000
    header = module.header_bits(data, **params)
    total = len(blob) * 8
    original = len(data) * 8
    return {
        "id": codec_id,
        "algorithm": label,
        "blob": blob,
        "original_bits": original,
        "header_bits": header,
        "payload_bits": total - header,
        "total_bits": total,
        "ratio_pct": total / original * 100 if original else 0.0,
        "saving_pct": (1 - total / original) * 100 if original else 0.0,
        "bits_per_symbol": total / len(data) if data else 0.0,
        "encode_ms": encode_ms,
        "decode_ms": decode_ms,
        "lossless": restored == data,
    }


def bit_rows(blob: bytes, header_bits: int) -> pd.DataFrame:
    """Χωρίζει το συμπιεσμένο αποτέλεσμα σε γραμμές των οκτώ bytes."""
    rows = []
    for offset in range(0, len(blob), 8):
        chunk = blob[offset: offset + 8]
        rows.append({
            "offset": offset,
            "hex": " ".join(f"{b:02X}" for b in chunk),
            "bits": " ".join(f"{b:08b}" for b in chunk),
            "τμήμα": "κεφαλίδα" if offset * 8 < header_bits else "φορτίο",
        })
    return pd.DataFrame(rows)


st.title("CompressViz")
st.caption("Διαδραστική οπτικοποίηση και επαληθευμένη σύγκριση lossless αλγορίθμων σε Python")

with st.sidebar:
    # Όλες οι επιλογές εισόδου μένουν συγκεντρωμένες στην αριστερή στήλη.
    st.header("Είσοδος και παράμετροι")
    input_mode = st.radio("Τύπος εισόδου", ["Κείμενο", "Αρχείο"], horizontal=True)
    text = st.text_area("Κείμενο", "TO BE OR NOT TO BE, THAT IS THE QUESTION.", height=130,
                        disabled=input_mode == "Αρχείο")
    uploaded = st.file_uploader("Αρχείο κειμένου ή δυαδικών δεδομένων",
                                disabled=input_mode != "Αρχείο")
    codec_id = st.selectbox("Αλγόριθμος", ALGORITHMS,
                            format_func=lambda key: ALGORITHMS[key][0])
    selected_params = dict(ALGORITHMS[codec_id][2])
    if codec_id in {"lz77", "lzss"}:
        selected_params["window_size"] = st.select_slider(
            "Παράθυρο", [256, 512, 1024, 2048, 4096, 8192, 16384, 32768], value=4096)
        selected_params["lookahead_size"] = st.slider("Lookahead", 4, 64, 18)
    elif codec_id == "lzw":
        selected_params["max_bits"] = st.slider("Μέγιστο πλάτος κωδικού", 9, 16, 12)
    max_steps = st.slider("Μέγιστα οπτικά βήματα", 20, 300, 120, 10)

data, source_name = parse_input(input_mode, text, uploaded)
if not data:
    st.info("Δώστε κείμενο ή επιλέξτε ένα μη κενό αρχείο.")
    st.stop()

# Η συγκριτική καρτέλα εκτελεί όλους τους codecs. Ο στατικός arithmetic
# codec κρατά το συνολικό πλήθος συμβόλων σε πεδίο που επιβάλλει αυτό το όριο.
# Ελέγχουμε το μέγεθος εδώ, ώστε ένα μεγάλο αρχείο να δίνει καθαρό μήνυμα
# στον χρήστη και όχι μη χειριζόμενη εξαίρεση κατά τη μέτρηση.
max_comparative_input_bytes = arithmetic.QUARTER - 1
if len(data) > max_comparative_input_bytes:
    st.error(
        "Η συγκριτική λειτουργία υποστηρίζει αρχεία έως "
        f"{max_comparative_input_bytes:,} bytes, επειδή εκτελεί και τον "
        "στατικό αριθμητικό κωδικοποιητή."
    )
    st.stop()

# Η σύγκριση χρησιμοποιεί το ίδιο αρχείο για όλους τους αλγορίθμους.
results = [measure(key, data, tuple(sorted(
    (selected_params if key == codec_id else ALGORITHMS[key][2]).items()
))) for key in ALGORITHMS]
current = next(row for row in results if row["id"] == codec_id)
entropy = arithmetic.entropy(data)

st.write(f"**Πηγή:** {source_name} · **Μέγεθος:** {len(data):,} bytes · "
         f"**SHA-256:** `{hashlib.sha256(data).hexdigest()}`")

metrics = st.columns(6)
metrics[0].metric("Αρχικό", f"{len(data):,} B")
metrics[1].metric("Συμπιεσμένο", f"{len(current['blob']):,} B")
metrics[2].metric("Λόγος", f"{current['ratio_pct']:.2f}%")
metrics[3].metric("Εξοικονόμηση", f"{current['saving_pct']:.2f}%")
metrics[4].metric("bits/σύμβολο", f"{current['bits_per_symbol']:.3f}")
metrics[5].metric("Round-trip", "Επιτυχία" if current["lossless"] else "Αποτυχία")

tabs = st.tabs(["Ροή", "Βήμα-βήμα", "Bitstream", "Στατιστικά", "Σύγκριση", "Εξαγωγή"])

with tabs[0]:
    # Απλή παρουσίαση των σταδίων από την είσοδο μέχρι τις μετρικές.
    phases = [
        ("1", "Parser", f"{len(data):,} bytes"),
        ("2", "Compressor", ALGORITHMS[codec_id][0]),
        ("3", "Trace generator", f"έως {max_steps} events"),
        ("4", "Visualizer", "ροή, βήματα, bitstream"),
        ("5", "Metrics", "μέγεθος, χρόνος, entropy, round-trip"),
    ]
    columns = st.columns(len(phases))
    for column, (number, title, detail) in zip(columns, phases):
        column.subheader(f"{number}. {title}")
        column.caption(detail)

with tabs[1]:
    # Τα βήματα είναι περιορισμένα, ώστε ένα μεγάλο αρχείο να μη γεμίσει τη σελίδα.
    trace = build_trace(codec_id, data, selected_params, max_steps)
    if "trace_index" not in st.session_state:
        st.session_state.trace_index = 0
    if "trace_playing" not in st.session_state:
        st.session_state.trace_playing = False
    st.session_state.trace_index = min(st.session_state.trace_index, max(0, len(trace) - 1))
    a, b, c, play, pause, speed_col, d = st.columns([1, 1, 1, 1, 1, 1.5, 4])
    if a.button("← Πίσω", disabled=st.session_state.trace_index == 0):
        st.session_state.trace_index -= 1
    if b.button("Μπροστά →", disabled=st.session_state.trace_index >= len(trace) - 1):
        st.session_state.trace_index += 1
    if c.button("Αρχή"):
        st.session_state.trace_index = 0
        st.session_state.trace_playing = False
    if play.button("▶ Play"):
        st.session_state.trace_playing = True
    if pause.button("⏸ Pause"):
        st.session_state.trace_playing = False
    playback_speed = speed_col.selectbox("Ταχύτητα", [0.25, 0.5, 1.0, 2.0],
                                         index=2, label_visibility="collapsed")
    if len(trace) > 1:
        chosen = d.slider("Βήμα", 1, len(trace), st.session_state.trace_index + 1)
    else:
        chosen = 1
        d.caption("Βήμα 1 / 1")
    st.session_state.trace_index = chosen - 1
    event = trace[st.session_state.trace_index]
    st.subheader(event.get("title", "Βήμα"))
    st.write(event.get("description", ""))
    detail = {k: v for k, v in event.items() if k not in {"title", "description"}}
    st.json(detail, expanded=True)
    if st.session_state.trace_playing:
        if st.session_state.trace_index < len(trace) - 1:
            time.sleep(1.0 / playback_speed)
            st.session_state.trace_index += 1
            st.rerun()
        else:
            st.session_state.trace_playing = False

with tabs[2]:
    # Εμφάνιση των πραγματικών bytes που παρήγαγε ο compressor.
    st.caption("Η διάκριση γίνεται ανά byte· το τελευταίο byte μπορεί να περιέχει padding bits.")
    st.dataframe(bit_rows(current["blob"], current["header_bits"]),
                 width="stretch", hide_index=True, height=430)
    st.download_button("Λήψη συμπιεσμένου stream", current["blob"],
                       file_name=f"{codec_id}.cvz", mime="application/octet-stream")

with tabs[3]:
    # Συχνότητες συμβόλων και κατανομή κεφαλίδας/ωφέλιμου φορτίου.
    left, right = st.columns(2)
    frequencies = Counter(data)
    freq_df = pd.DataFrame([
        {"σύμβολο": (chr(k) if 32 <= k < 127 else f"0x{k:02X}"), "συχνότητα": v}
        for k, v in frequencies.most_common(40)
    ]).set_index("σύμβολο")
    left.subheader("Συχνότητες συμβόλων")
    left.bar_chart(freq_df)
    right.subheader("Κατανομή stream")
    right.bar_chart(pd.DataFrame({"bits": {
        "κεφαλίδα": current["header_bits"], "φορτίο": current["payload_bits"]
    }}))
    right.write(f"Entropy: **{entropy:.4f} bits/σύμβολο**")
    right.write(f"Shannon bound: **{entropy * len(data):,.1f} bits**")
    right.write(f"Encode: **{current['encode_ms']:.3f} ms** · Decode: **{current['decode_ms']:.3f} ms**")

with tabs[4]:
    # Κοινός πίνακας αποτελεσμάτων για άμεση σύγκριση.
    compare = pd.DataFrame([{k: v for k, v in row.items() if k != "blob"} for row in results])
    st.bar_chart(compare.set_index("algorithm")[["ratio_pct"]])
    st.dataframe(compare[["algorithm", "ratio_pct", "saving_pct", "header_bits",
                          "payload_bits", "bits_per_symbol", "encode_ms", "decode_ms", "lossless"]],
                 width="stretch", hide_index=True)

with tabs[5]:
    # Τα αποτελέσματα μπορούν να χρησιμοποιηθούν ξανά χωρίς χειροκίνητη αντιγραφή.
    serialisable = [{k: v for k, v in row.items() if k != "blob"} for row in results]
    payload = {
        "input": {"name": source_name, "bytes": len(data),
                  "sha256": hashlib.sha256(data).hexdigest(),
                  "entropy_bits_per_symbol": entropy},
        "results": serialisable,
    }
    st.download_button("Αποτελέσματα JSON", json.dumps(payload, ensure_ascii=False, indent=2),
                       "compressviz_results.json", "application/json")
    csv_buffer = io.StringIO()
    writer = csv.DictWriter(csv_buffer, fieldnames=serialisable[0].keys())
    writer.writeheader()
    writer.writerows(serialisable)
    st.download_button("Αποτελέσματα CSV", csv_buffer.getvalue(),
                       "compressviz_results.csv", "text/csv")
    st.download_button("Trace JSON", json.dumps(build_trace(
        codec_id, data, selected_params, max_steps), ensure_ascii=False, indent=2),
        f"{codec_id}_trace.json", "application/json")
