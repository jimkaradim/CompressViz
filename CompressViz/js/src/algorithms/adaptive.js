/**
 * adaptive.js — Προσαρμοστικό Arithmetic Coding
 *
 * Κωδικοποιητής και αποκωδικοποιητής ξεκινούν από ταυτόσημο αρχικό
 * μοντέλο και το ενημερώνουν παράλληλα μετά από κάθε σύμβολο. Επειδή ο
 * αποκωδικοποιητής έχει ήδη ανακτήσει το σύμβολο πριν το χρησιμοποιήσει
 * για ενημέρωση, οι δύο πλευρές μένουν συγχρονισμένες χωρίς καμία
 * επικοινωνία. Έτσι δεν μεταδίδεται καθόλου μοντέλο: η κεφαλίδα είναι
 * μόνο 4 bytes για το μήκος του μηνύματος.
 *
 * Πλήρης τεκμηρίωση στο compressviz/adaptive.py. Οι δύο υλοποιήσεις
 * παράγουν ταυτόσημα bytes (έλεγχος στο scripts/crossvalidate.mjs).
 *
 * Μορφή αρχείου:
 *     uint32 N, payload
 */

import { BitReader, BitWriter, bytesToInt, concatBytes, intToBytes } from "./bitio.js";

const NBITS = 24;
const FULL = 1 << NBITS;
const HALF = FULL >>> 1;
const QUARTER = FULL >>> 2;
const THREE_Q = 3 * QUARTER;
const MASK = FULL - 1;

const ALPHABET = 256;
const MAX_TOTAL = QUARTER - 1;
const HEADER_BYTES = 4;
const DEFAULT_INCREMENT = 32;

/**
 * Μοντέλο συχνοτήτων σε δέντρο Fenwick.
 *
 * Η αφελής υλοποίηση με γραμμική σάρωση κοστίζει O(|Σ|) ανά σύμβολο,
 * δηλαδή 256 προσθέσεις για κάθε byte. Το Fenwick tree το μειώνει σε
 * O(log|Σ|) = 8 βήματα για ανάκτηση, ενημέρωση και αναζήτηση συμβόλου.
 */
class AdaptiveModel {
  constructor() {
    this.tree = new Int32Array(ALPHABET + 1);
    for (let i = 1; i <= ALPHABET; i++) {
      this.tree[i] += 1;
      const j = i + (i & -i);
      if (j <= ALPHABET) this.tree[j] += this.tree[i];
    }
    this.total = ALPHABET;
  }

  prefix(i) {
    let s = 0;
    while (i > 0) { s += this.tree[i]; i -= i & -i; }
    return s;
  }

  freq(sym) { return this.prefix(sym + 1) - this.prefix(sym); }

  cum(sym) {
    const low = this.prefix(sym);
    return { low, high: low + this.freq(sym) };
  }

  /** Σύμβολο του οποίου το διάστημα περιέχει το target, σε O(log|Σ|). */
  symbolFor(target) {
    let idx = 0, remaining = target;
    let bit = 1 << (32 - Math.clz32(ALPHABET) - 1);
    while (bit) {
      const nxt = idx + bit;
      if (nxt <= ALPHABET && this.tree[nxt] <= remaining) {
        idx = nxt;
        remaining -= this.tree[nxt];
      }
      bit >>= 1;
    }
    const low = target - remaining;
    return { sym: idx, low, high: low + this.freq(idx) };
  }

  update(sym, increment = DEFAULT_INCREMENT) {
    let i = sym + 1;
    while (i <= ALPHABET) { this.tree[i] += increment; i += i & -i; }
    this.total += increment;
    if (this.total > MAX_TOTAL) this.rescale();
  }

  /**
   * Υποδιπλασιασμός συχνοτήτων με ελάχιστο 1.
   *
   * Ο αποκωδικοποιητής εκτελεί την ίδια ενέργεια στο ίδιο ακριβώς σημείο·
   * διαφορετικά τα δύο μοντέλα αποσυγχρονίζονται.
   */
  rescale() {
    const freqs = new Int32Array(ALPHABET);
    for (let s = 0; s < ALPHABET; s++) freqs[s] = Math.max(1, (this.freq(s) + 1) >> 1);
    this.tree = new Int32Array(ALPHABET + 1);
    let total = 0;
    for (let i = 1; i <= ALPHABET; i++) {
      this.tree[i] += freqs[i - 1];
      const j = i + (i & -i);
      if (j <= ALPHABET) this.tree[j] += this.tree[i];
    }
    for (let s = 0; s < ALPHABET; s++) total += freqs[s];
    this.total = total;
  }
}

export function compress(data, { increment = DEFAULT_INCREMENT } = {}) {
  const header = intToBytes(data.length, 4);
  if (data.length === 0) return header;

  const model = new AdaptiveModel();
  const bw = new BitWriter();
  let low = 0, high = MASK, pending = 0;

  const emit = (bit) => {
    bw.writeBit(bit);
    for (let i = 0; i < pending; i++) bw.writeBit(1 - bit);
    pending = 0;
  };

  for (const byte of data) {
    const { low: cumLo, high: cumHi } = model.cum(byte);
    const total = model.total;
    const rng = high - low + 1;
    high = low + Math.floor((rng * cumHi) / total) - 1;
    low = low + Math.floor((rng * cumLo) / total);

    for (;;) {
      if (high < HALF) emit(0);
      else if (low >= HALF) { emit(1); low -= HALF; high -= HALF; }
      else if (low >= QUARTER && high < THREE_Q) { pending++; low -= QUARTER; high -= QUARTER; }
      else break;
      low = (low * 2) & MASK;
      high = ((high * 2) + 1) & MASK;
    }

    model.update(byte, increment);
  }

  pending++;
  emit(low < QUARTER ? 0 : 1);

  return concatBytes(header, bw.finish());
}

export function decompress(blob, { increment = DEFAULT_INCREMENT } = {}) {
  const n = bytesToInt(blob, 0, 4);
  if (n === 0) return new Uint8Array(0);

  const model = new AdaptiveModel();
  const br = new BitReader(concatBytes(blob.subarray(HEADER_BYTES), new Uint8Array(8)));

  let low = 0, high = MASK;
  let value = br.readBits(NBITS);
  const out = new Uint8Array(n);

  for (let i = 0; i < n; i++) {
    const total = model.total;
    const rng = high - low + 1;
    const target = Math.floor(((value - low + 1) * total - 1) / rng);
    const { sym, low: cumLo, high: cumHi } = model.symbolFor(target);
    out[i] = sym;

    high = low + Math.floor((rng * cumHi) / total) - 1;
    low = low + Math.floor((rng * cumLo) / total);

    for (;;) {
      if (high < HALF) { /* E1 */ }
      else if (low >= HALF) { low -= HALF; high -= HALF; value -= HALF; }
      else if (low >= QUARTER && high < THREE_Q) { low -= QUARTER; high -= QUARTER; value -= QUARTER; }
      else break;
      low = (low * 2) & MASK;
      high = ((high * 2) + 1) & MASK;
      value = ((value * 2) + br.readBit()) & MASK;
    }

    model.update(sym, increment);
  }
  return out;
}

export function headerBits() { return HEADER_BYTES * 8; }

// ── Ίχνος για την οπτικοποίηση ──────────────────────────────────────

/**
 * Δείχνει πώς εξελίσσεται το μοντέλο. Είναι το πιο διδακτικό σημείο του
 * αλγορίθμου: ο χρήστης βλέπει τις συχνότητες να «χτίζονται» από την
 * ομοιόμορφη αρχική κατανομή προς την πραγματική κατανομή του κειμένου.
 */
export function trace(data, { increment = DEFAULT_INCREMENT, maxSteps = 60 } = {}) {
  const steps = [];
  if (data.length === 0) {
    return { steps, blob: compress(data), totalBits: 0, headerBits: 0, originalBits: 0, ratio: 0 };
  }

  const model = new AdaptiveModel();
  const limit = Math.min(data.length, maxSteps);
  let low = 0, high = MASK, pending = 0, emitted = 0;

  steps.push({
    phase: "init",
    title: "Φάση 1 — Ομοιόμορφο αρχικό μοντέλο",
    desc: "Κάθε σύμβολο ξεκινά με συχνότητα 1. Καμία κεφαλίδα δεν μεταδίδεται: " +
          "ο αποκωδικοποιητής ξεκινά από το ίδιο ακριβώς μοντέλο.",
    total: model.total,
    headerBits: headerBits(),
  });

  for (let i = 0; i < limit; i++) {
    const byte = data[i];
    const { low: cumLo, high: cumHi } = model.cum(byte);
    const total = model.total;
    const probBefore = (cumHi - cumLo) / total;
    const costBits = -Math.log2(probBefore);

    const rng = high - low + 1;
    high = low + Math.floor((rng * cumHi) / total) - 1;
    low = low + Math.floor((rng * cumLo) / total);

    const rescalings = [];
    for (;;) {
      if (high < HALF) { rescalings.push("E1"); emitted += 1 + pending; pending = 0; }
      else if (low >= HALF) { rescalings.push("E2"); emitted += 1 + pending; pending = 0; low -= HALF; high -= HALF; }
      else if (low >= QUARTER && high < THREE_Q) { rescalings.push("E3"); pending++; low -= QUARTER; high -= QUARTER; }
      else break;
      low = (low * 2) & MASK;
      high = ((high * 2) + 1) & MASK;
    }

    model.update(byte, increment);

    steps.push({
      phase: "encode",
      title: `Θέση ${i + 1}: '${String.fromCharCode(byte) === " " ? "␣" : String.fromCharCode(byte)}'`,
      char: String.fromCharCode(byte),
      pos: i,
      probBefore,
      costBits,
      freqAfter: model.freq(byte),
      modelTotal: model.total,
      normalizedLow: low / FULL,
      normalizedHigh: (high + 1) / FULL,
      rescalings,
      pendingBits: pending,
      bitsEmitted: emitted,
      desc: `Πιθανότητα πριν την ενημέρωση: ${(probBefore * 100).toFixed(3)}% ` +
            `→ κόστος ${costBits.toFixed(2)} bits. Το μοντέλο μαθαίνει καθώς προχωρά.`,
    });
  }

  const blob = compress(data, { increment });
  steps.push({
    phase: "result",
    title: "Φάση 2 — Αποτέλεσμα",
    desc: "Καμία κεφαλίδα μοντέλου. Το τίμημα είναι το «κόστος εκμάθησης» " +
          "στην αρχή του αρχείου, που αποσβένεται όσο μεγαλώνει η είσοδος.",
    headerBits: headerBits(),
    payloadBits: blob.length * 8 - headerBits(),
    totalBits: blob.length * 8,
    originalBits: data.length * 8,
    visualizedSteps: limit,
    totalSymbols: data.length,
  });

  return {
    steps, blob,
    totalBits: blob.length * 8,
    headerBits: headerBits(),
    originalBits: data.length * 8,
    ratio: (blob.length * 8) / (data.length * 8) * 100,
  };
}
