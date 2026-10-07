/**
 * theme.js — Design tokens
 *
 * Διατηρείται η χρωματική ταυτότητα της αρχικής εφαρμογής (σκούρο ναυτικό
 * μπλε με χρωματική κωδικοποίηση ανά αλγόριθμο). Η εξαγωγή τους σε ένα
 * σημείο αντικαθιστά τα inline literals που ήταν διάσπαρτα στο αρχικό
 * αρχείο των 1.001 γραμμών.
 */

export const SC = {
  surface: "#0A1628",
  bg: "#060D1F",
  border: "#1A2640",
  muted: "#64748B",
  text: "#E2E8F0",
  textDim: "#94A3B8",
  good: "#10B981",
  bad: "#F87171",
  warn: "#F59E0B",
};

export const SEG_COLORS = [
  "#F59E0B", "#10B981", "#60A5FA", "#F87171", "#A78BFA",
  "#34D399", "#93C5FD", "#FCA5A5", "#C4B5FD", "#6EE7B7",
  "#FB923C", "#818CF8", "#4ADE80", "#F472B6", "#38BDF8", "#A3E635",
];

export const MONO = "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace";

export const SAMPLES = {
  alice:
    "Alice was beginning to get very tired of sitting by her sister on the " +
    "bank, and of having nothing to do: once or twice she had peeped into " +
    "the book her sister was reading, but it had no pictures or " +
    "conversations in it, and what is the use of a book thought Alice " +
    "without pictures or conversation?",
  repeated:
    "AAAAAABBBBBBCCCCCCDDDDDDDDDDEEEEEEEFFFFFGGGGGG the cat sat on the mat " +
    "with the bat and the hat",
  digits:
    "aa3bb 2a3bb — αυτή η είσοδος αποδεικνύει γιατί το «κειμενικό» RLE " +
    "δεν είναι αντιστρέψιμο",
  short: "the quick brown fox jumps over the lazy dog and then runs far away",
};
