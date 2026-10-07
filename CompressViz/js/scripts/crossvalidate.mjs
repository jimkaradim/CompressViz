#!/usr/bin/env node
/**
 * crossvalidate.mjs — Διασταύρωση JavaScript έναντι Python
 *
 * Διαβάζει τα διανύσματα ελέγχου που παρήγαγε το crossvalidate.py και
 * επιβεβαιώνει ότι η JavaScript υλοποίηση παράγει ΤΑΥΤΟΣΗΜΑ bytes.
 *
 * Συγκρίνεται το SHA-256, όχι το μέγεθος: δύο υλοποιήσεις μπορεί να
 * συμφωνούν σε μήκος αλλά να διαφέρουν σε περιεχόμενο (π.χ. διαφορετική
 * σειρά ισοβαθμιών στο δέντρο Huffman), και τότε η μία δεν αποκωδικοποιεί
 * την έξοδο της άλλης.
 *
 *     python3 crossvalidate.py && node js/scripts/crossvalidate.mjs
 */

import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import { adaptive, arithmetic, huffman, lz77, lzw, rle } from "../src/algorithms/index.js";

const here = dirname(fileURLToPath(import.meta.url));
const vectorsPath = join(here, "..", "..", "vectors.json");

const CODECS = {
  rle_pairs:    { module: rle, params: { variant: "pairs" } },
  rle_packbits: { module: rle, params: { variant: "packbits" } },
  huffman:      { module: huffman, params: {} },
  lz77:         { module: lz77, params: { windowSize: 4096, lookaheadSize: 18, mode: "lz77" } },
  lzss:         { module: lz77, params: { windowSize: 4096, lookaheadSize: 18, mode: "lzss" } },
  lzw12:        { module: lzw, params: { maxBits: 12 } },
  arithmetic:   { module: arithmetic, params: {} },
  adaptive:     { module: adaptive, params: {} },
};

const sha256 = (bytes) => createHash("sha256").update(Buffer.from(bytes)).digest("hex");
const hexToBytes = (hex) => {
  const out = new Uint8Array(hex.length / 2);
  for (let i = 0; i < out.length; i++) out[i] = parseInt(hex.substr(i * 2, 2), 16);
  return out;
};

let data;
try {
  data = JSON.parse(readFileSync(vectorsPath, "utf-8"));
} catch {
  console.error(`  Δεν βρέθηκε το ${vectorsPath}.`);
  console.error("  Τρέξε πρώτα: python3 crossvalidate.py");
  process.exit(1);
}

console.log("=".repeat(66));
console.log("  Διασταύρωση JavaScript ↔ Python");
console.log("=".repeat(66));

let checks = 0;
const mismatches = [];
const perCodec = {};

for (const vec of data.vectors) {
  const input = hexToBytes(vec.input_hex);

  if (sha256(input) !== vec.input_sha256) {
    mismatches.push(`${vec.name}: η ίδια η είσοδος δεν ταιριάζει`);
    continue;
  }

  for (const [codecId, expected] of Object.entries(vec.expected)) {
    const { module, params } = CODECS[codecId];
    checks++;
    perCodec[codecId] ??= { ok: 0, bad: 0 };

    let blob;
    try {
      blob = module.compress(input, params);
    } catch (e) {
      perCodec[codecId].bad++;
      mismatches.push(`${codecId} / ${vec.name}: εξαίρεση ${e.message}`);
      continue;
    }

    const got = sha256(blob);
    if (got === expected.sha256 && blob.length === expected.length) {
      perCodec[codecId].ok++;
    } else {
      perCodec[codecId].bad++;
      mismatches.push(
        `${codecId} / ${vec.name}: μήκος JS=${blob.length} PY=${expected.length}, ` +
        `sha JS=${got.slice(0, 12)}… PY=${expected.sha256.slice(0, 12)}…`
      );
    }

    // Επιπλέον: η JS πρέπει να αποκωδικοποιεί τη δική της έξοδο
    const restored = module.decompress(blob);
    if (restored.length !== input.length ||
        !restored.every((b, i) => b === input[i])) {
      mismatches.push(`${codecId} / ${vec.name}: αποτυχία round-trip στη JS`);
    }
  }
}

console.log(`\n  Διανύσματα: ${data.vectors.length}   Έλεγχοι: ${checks}\n`);
for (const [codecId, r] of Object.entries(perCodec)) {
  const mark = r.bad === 0 ? "✓" : "✗";
  console.log(`  ${mark} ${codecId.padEnd(14)} ${r.ok}/${r.ok + r.bad} ταυτόσημα`);
}

console.log("\n" + "=".repeat(66));
if (mismatches.length) {
  console.log(`  ΑΠΟΤΥΧΙΑ: ${mismatches.length} αποκλίσεις`);
  for (const m of mismatches.slice(0, 20)) console.log(`    - ${m}`);
  process.exit(1);
}
console.log("  ΟΙ ΔΥΟ ΥΛΟΠΟΙΗΣΕΙΣ ΠΑΡΑΓΟΥΝ ΤΑΥΤΟΣΗΜΑ BYTES");
console.log("  (σύγκριση SHA-256, όχι μόνο μεγέθους)");
