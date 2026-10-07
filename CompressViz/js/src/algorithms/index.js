/**
 * index.js — Μητρώο αλγορίθμων
 *
 * Κάθε άρθρωμα εκθέτει την ίδια διεπαφή:
 *
 *     compress(data: Uint8Array, params) -> Uint8Array
 *     decompress(blob: Uint8Array)       -> Uint8Array
 *     headerBits(data, params)           -> number
 *     trace(data, params)                -> { steps, blob, totalBits, ... }
 *
 * Ο διαχωρισμός compress/trace είναι σκόπιμος. Στην αρχική έκδοση η
 * οπτικοποίηση ΗΤΑΝ και η μέτρηση: τα βήματα παρήγαγαν το «συμπιεσμένο»
 * αποτέλεσμα και από εκεί υπολογιζόταν ο λόγος συμπίεσης. Έτσι τα
 * σφάλματα του κωδικοποιητή δεν μπορούσαν να εντοπιστούν, γιατί κανένας
 * αποκωδικοποιητής δεν τα έλεγχε ποτέ. Πλέον οι μετρικές προέρχονται
 * πάντα από την compress() και επαληθεύονται με round-trip.
 */

import * as adaptive from "./adaptive.js";
import * as arithmetic from "./arithmetic.js";
import * as huffman from "./huffman.js";
import * as lz77 from "./lz77.js";
import * as lzw from "./lzw.js";
import * as rle from "./rle.js";

export { adaptive, arithmetic, huffman, lz77, lzw, rle };
export * from "./bitio.js";

export const ALGORITHMS = {
  rle: {
    module: rle,
    label: "RLE",
    full: "Run-Length Encoding (PackBits)",
    color: "#10B981",
    family: "Run-length",
    ideal: "Bitmaps, fax, ομοιόμορφες περιοχές",
    params: { variant: "packbits" },
    description:
      "Αντικαθιστά διαδοχικές επαναλήψεις του ίδιου συμβόλου με ζεύγος " +
      "(πλήθος, σύμβολο). Απλός και γρήγορος, αλλά ωφέλιμος μόνο όταν η " +
      "είσοδος έχει μακριά runs. Σε αγγλικό κείμενο επεκτείνει τα δεδομένα.",
  },
  huffman: {
    module: huffman,
    label: "Huffman",
    full: "Canonical Huffman Coding",
    color: "#60A5FA",
    family: "Entropy",
    ideal: "Κείμενο, ήχος, γενικής χρήσης",
    params: {},
    description:
      "Χτίζει βέλτιστο δέντρο από τις συχνότητες συμβόλων, δίνοντας " +
      "συντομότερους κωδικούς στα συχνότερα. Αποδεδειγμένα βέλτιστος για " +
      "κωδικοποίηση ενός συμβόλου τη φορά, με L < H(X) + 1.",
  },
  lzss: {
    module: lz77,
    label: "LZSS",
    full: "Lempel-Ziv-Storer-Szymanski",
    color: "#F87171",
    family: "Dictionary",
    ideal: "Γενικά αρχεία, βάση του DEFLATE",
    params: { windowSize: 4096, lookaheadSize: 18, mode: "lzss" },
    description:
      "Κυλιόμενο παράθυρο πάνω στα ήδη επεξεργασμένα δεδομένα. Ένα flag " +
      "bit διακρίνει αντιστοίχιση (offset, length) από σκέτο literal, ώστε " +
      "να μην πληρώνεται πλήρες token όταν δεν υπάρχει ωφέλιμη αντιστοίχιση.",
  },
  lz77: {
    module: lz77,
    label: "LZ77",
    full: "LZ77 (τριάδες)",
    color: "#FB923C",
    family: "Dictionary",
    ideal: "Ιστορικό ενδιαφέρον· εκπαιδευτική σύγκριση με LZSS",
    params: { windowSize: 4096, lookaheadSize: 18, mode: "lz77" },
    description:
      "Η αρχική μορφή του 1977: κάθε token είναι τριάδα " +
      "(offset, length, next_char). Πληρώνει πλήρες token ακόμη και όταν " +
      "δεν βρίσκει αντιστοίχιση, γι' αυτό μπορεί να επεκτείνει τα δεδομένα.",
  },
  lzw: {
    module: lzw,
    label: "LZW",
    full: "Lempel-Ziv-Welch",
    color: "#A78BFA",
    family: "Dictionary",
    ideal: "GIF, TIFF, Unix compress",
    params: { maxBits: 12 },
    description:
      "Χτίζει δυναμικά λεξικό κατά την κωδικοποίηση και εκπέμπει ακέραιους " +
      "κωδικούς. Ο αποκωδικοποιητής ανακατασκευάζει το λεξικό μόνος του, " +
      "άρα δεν χρειάζεται καθόλου κεφαλίδα.",
  },
  adaptive: {
    module: adaptive,
    label: "Adaptive AC",
    full: "Adaptive Arithmetic Coding",
    color: "#34D399",
    family: "Entropy (adaptive)",
    ideal: "Ροές δεδομένων, μικρά αρχεία",
    params: {},
    description:
      "Ίδιος πυρήνας με το Arithmetic Coding, αλλά το μοντέλο συχνοτήτων " +
      "χτίζεται σταδιακά και ταυτόχρονα σε κωδικοποιητή και αποκωδικοποιητή. " +
      "Δεν μεταδίδεται καθόλου μοντέλο — η κεφαλίδα είναι μόλις 4 bytes. " +
      "Το τίμημα είναι το κόστος εκμάθησης στην αρχή του αρχείου.",
  },
  arithmetic: {
    module: arithmetic,
    label: "AC",
    full: "Arithmetic Coding",
    color: "#F59E0B",
    family: "Entropy",
    ideal: "Σχεδόν βέλτιστο για κάθε πηγή",
    params: {},
    description:
      "Κωδικοποιεί ολόκληρο το μήνυμα ως έναν αριθμό στο [0, 1). Κάθε " +
      "σύμβολο στενεύει το διάστημα αναλογικά με την πιθανότητά του. Με " +
      "ακέραια αριθμητική και κλιμάκωση πλησιάζει το φράγμα Shannon.",
  },
};

/** Εκτελεί έναν αλγόριθμο και ΕΠΑΛΗΘΕΥΕΙ ότι είναι lossless. */
export function runVerified(id, data) {
  const { module, params } = ALGORITHMS[id];
  const blob = module.compress(data, params);
  const restored = module.decompress(blob);

  let lossless = restored.length === data.length;
  if (lossless) {
    for (let i = 0; i < data.length; i++) {
      if (restored[i] !== data[i]) { lossless = false; break; }
    }
  }

  const headerBits = module.headerBits(data, params);
  const totalBits = blob.length * 8;

  return {
    id, blob, lossless,
    headerBits,
    payloadBits: totalBits - headerBits,
    totalBits,
    originalBits: data.length * 8,
    ratio: data.length ? (totalBits / (data.length * 8)) * 100 : 0,
    bitsPerSymbol: data.length ? totalBits / data.length : 0,
  };
}

/** Ίχνος οπτικοποίησης με τις μετρικές να προέρχονται από την compress(). */
export function runTrace(id, data, overrides = {}) {
  const { module, params } = ALGORITHMS[id];
  return module.trace(data, { ...params, ...overrides });
}
