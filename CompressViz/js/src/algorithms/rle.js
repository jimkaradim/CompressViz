/**
 * rle.js — Run-Length Encoding
 *
 * ΔΙΟΡΘΩΣΗ ΚΡΙΣΙΜΟΥ ΣΦΑΛΜΑΤΟΣ
 * ----------------------------
 * Η αρχική computeRLE παρήγαγε "3A" / "5B" μέσα στο ίδιο ρεύμα με τα
 * δεδομένα. Όταν η είσοδος περιέχει ψηφία, η κωδικοποίηση δεν είναι
 * αντιστρέψιμη:
 *
 *     "aa3bb" -> "2a32b"
 *     "2a3bb" -> "2a32b"      // ίδια έξοδος, διαφορετική είσοδος
 *
 * Άρα δεν επρόκειτο για lossless αλγόριθμο. Υλοποιούνται δύο ορθές
 * παραλλαγές, ταυτόσημες με το compressviz/rle.py:
 *
 *   pairs    — κάθε run ως 2 bytes (πλήθος, σύμβολο)
 *   packbits — η πρότυπη παραλλαγή TIFF/PDF/BMP, με φραγμένη επέκταση
 */

import { concatBytes } from "./bitio.js";

const MAX_RUN_PAIRS = 255;
const TAG = { pairs: 0, packbits: 1 };

// ── Παραλλαγή 1: ζεύγη (πλήθος, σύμβολο) ────────────────────────────

function encodePairs(data) {
  const out = [];
  let i = 0;
  while (i < data.length) {
    const sym = data[i];
    let run = 1;
    while (i + run < data.length && data[i + run] === sym && run < MAX_RUN_PAIRS) run++;
    out.push(run, sym);
    i += run;
  }
  return Uint8Array.from(out);
}

function decodePairs(blob) {
  if (blob.length % 2 !== 0) throw new Error("Μη έγκυρο RLE-pairs stream");
  const out = [];
  for (let i = 0; i < blob.length; i += 2) {
    for (let k = 0; k < blob[i]; k++) out.push(blob[i + 1]);
  }
  return Uint8Array.from(out);
}

// ── Παραλλαγή 2: PackBits ───────────────────────────────────────────
//
// Το byte ελέγχου c δηλώνει τι ακολουθεί:
//   0..127    -> ακολουθούν (c + 1) κυριολεκτικά bytes
//   129..255  -> το επόμενο byte επαναλαμβάνεται (257 - c) φορές
//   128       -> δεν γίνεται καμία ενέργεια

function encodePackBits(data) {
  const out = [];
  let i = 0;
  const n = data.length;

  while (i < n) {
    let run = 1;
    while (i + run < n && data[i + run] === data[i] && run < 128) run++;

    if (run >= 2) {
      out.push(257 - run, data[i]);
      i += run;
    } else {
      const start = i;
      i++;
      while (i < n && i - start < 128) {
        if (i + 2 < n && data[i] === data[i + 1] && data[i + 1] === data[i + 2]) break;
        i++;
      }
      out.push(i - start - 1);
      for (let k = start; k < i; k++) out.push(data[k]);
    }
  }
  return Uint8Array.from(out);
}

function decodePackBits(blob) {
  const out = [];
  let i = 0;
  while (i < blob.length) {
    const c = blob[i++];
    if (c === 128) continue;
    if (c < 128) {
      const count = c + 1;
      for (let k = 0; k < count; k++) out.push(blob[i + k]);
      i += count;
    } else {
      const count = 257 - c;
      for (let k = 0; k < count; k++) out.push(blob[i]);
      i++;
    }
  }
  return Uint8Array.from(out);
}

// ── Δημόσια διεπαφή ─────────────────────────────────────────────────

export function compress(data, { variant = "packbits" } = {}) {
  if (!(variant in TAG)) throw new Error(`Άγνωστη παραλλαγή RLE: ${variant}`);
  const body = variant === "packbits" ? encodePackBits(data) : encodePairs(data);
  return concatBytes(Uint8Array.from([TAG[variant]]), body);
}

export function decompress(blob) {
  if (blob.length === 0) throw new Error("Κενό RLE stream");
  const body = blob.subarray(1);
  return blob[0] === 1 ? decodePackBits(body) : decodePairs(body);
}

export function headerBits() { return 8; }

// ── Ίχνος για την οπτικοποίηση ──────────────────────────────────────

/**
 * Παράγει τα βήματα οπτικοποίησης.
 *
 * Το ίχνος περιγράφει τι *βλέπει* ο χρήστης, ενώ η μέτρηση μεγέθους
 * προέρχεται πάντα από την compress(). Τα δύο δεν πρέπει να συγχέονται:
 * στην αρχική έκδοση η οπτικοποίηση ΗΤΑΝ η μέτρηση, και γι' αυτό το
 * σφάλμα του RLE δεν έγινε ποτέ αντιληπτό.
 */
export function trace(data, { variant = "packbits" } = {}) {
  const steps = [];
  const runs = [];
  let i = 0;

  while (i < data.length) {
    const sym = data[i];
    let count = 1;
    const limit = variant === "packbits" ? 128 : MAX_RUN_PAIRS;
    while (i + count < data.length && data[i + count] === sym && count < limit) count++;

    runs.push({ sym, count });
    steps.push({
      phase: "scan",
      title: `Run στη θέση ${i}`,
      pos: i,
      runEnd: i + count - 1,
      char: String.fromCharCode(sym),
      count,
      token: variant === "packbits" && count === 1
        ? `literal '${String.fromCharCode(sym)}'`
        : `(${count}, '${String.fromCharCode(sym)}')`,
      runsCount: runs.length,
      bytesEmitted: variant === "pairs" ? runs.length * 2 : null,
    });
    i += count;
  }

  const blob = compress(data, { variant });
  return {
    steps,
    blob,
    totalBits: blob.length * 8,
    headerBits: headerBits(),
    originalBits: data.length * 8,
    ratio: data.length ? (blob.length * 8) / (data.length * 8) * 100 : 0,
  };
}
