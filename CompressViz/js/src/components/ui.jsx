/**
 * ui.jsx — Κοινά δομικά στοιχεία διεπαφής
 */

import { MONO, SC } from "../theme.js";

export function Card({ children, color, style = {} }) {
  return (
    <div style={{
      background: SC.surface,
      border: `1px solid ${color ? color + "33" : SC.border}`,
      borderRadius: 10,
      padding: 16,
      ...style,
    }}>
      {children}
    </div>
  );
}

export function StatCard({ label, value, sub, color, small }) {
  return (
    <div style={{
      background: SC.surface,
      border: `1px solid ${color ? color + "33" : SC.border}`,
      borderRadius: 10,
      padding: small ? 10 : 14,
      minWidth: 0,
    }}>
      <div style={{
        fontSize: 10, letterSpacing: 0.6, textTransform: "uppercase",
        color: SC.muted, marginBottom: 4,
      }}>
        {label}
      </div>
      <div style={{
        fontSize: small ? 16 : 22, fontWeight: 600,
        color: color || SC.text, fontFamily: MONO,
      }}>
        {value}
      </div>
      {sub && (
        <div style={{ fontSize: 10, color: SC.textDim, marginTop: 3 }}>{sub}</div>
      )}
    </div>
  );
}

export function SectionTitle({ children, note }) {
  return (
    <div style={{ marginBottom: 10 }}>
      <div style={{ fontSize: 13, fontWeight: 600, color: SC.text }}>{children}</div>
      {note && <div style={{ fontSize: 11, color: SC.textDim, marginTop: 3 }}>{note}</div>}
    </div>
  );
}

/**
 * Δείκτης επαλήθευσης lossless.
 *
 * Εμφανίζεται δίπλα σε ΚΑΘΕ μετρική. Είναι ο ορατός αντίκτυπος της
 * βασικής διόρθωσης: καμία μέτρηση δεν παρουσιάζεται χωρίς να έχει
 * επαληθευτεί ότι ο αποκωδικοποιητής ανακτά ακριβώς την είσοδο.
 */
export function LosslessBadge({ ok }) {
  return (
    <span style={{
      display: "inline-flex", alignItems: "center", gap: 4,
      fontSize: 10, fontWeight: 600, padding: "2px 7px", borderRadius: 20,
      color: ok ? SC.good : SC.bad,
      background: (ok ? SC.good : SC.bad) + "1A",
      border: `1px solid ${(ok ? SC.good : SC.bad)}44`,
    }}>
      {ok ? "✓ lossless" : "✗ απώλεια"}
    </span>
  );
}

/** Εμφανίσιμη μορφή χαρακτήρα (τα κενά και οι αλλαγές γραμμής φαίνονται). */
export function displayChar(c) {
  if (c === " ") return "␣";
  if (c === "\n") return "↵";
  if (c === "\t") return "⇥";
  return c;
}

export function Button({ children, onClick, active, color, disabled, title }) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      title={title}
      style={{
        border: `1px solid ${active ? (color || SC.text) + "66" : SC.border}`,
        background: active ? (color || SC.text) + "22" : "transparent",
        color: disabled ? SC.muted : active ? (color || SC.text) : SC.textDim,
        borderRadius: 7,
        padding: "6px 11px",
        fontSize: 12,
        cursor: disabled ? "not-allowed" : "pointer",
        fontFamily: "inherit",
        transition: "all 0.15s",
      }}
    >
      {children}
    </button>
  );
}
