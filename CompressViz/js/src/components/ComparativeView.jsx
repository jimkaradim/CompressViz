/**
 * ComparativeView.jsx — Ταυτόχρονη σύγκριση αλγορίθμων στην ίδια είσοδο
 *
 * Ζητούμενο της εκφώνησης που στην αρχική έκδοση είχε μεταφερθεί στη
 * «Μελλοντική Εργασία». Κάθε γραμμή δείχνει χωριστά κεφαλίδα και ωφέλιμο
 * φορτίο: αυτό είναι το σημείο όπου γίνεται ορατό γιατί ο LZW έχει δομικό
 * πλεονέκτημα (δεν μεταδίδει μοντέλο) και γιατί η αρχική σύγκριση, που
 * αγνοούσε τις κεφαλίδες, ήταν άνιση.
 */

import { Bar, BarChart, Cell, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { ALGORITHMS } from "../algorithms/index.js";
import { MONO, SC } from "../theme.js";
import { Card, LosslessBadge, SectionTitle } from "./ui.jsx";

export default function ComparativeView({ results, shannonRatio, entropy }) {
  const sorted = [...results].sort((a, b) => a.ratio - b.ratio);
  const chartData = sorted.map(r => ({
    name: ALGORITHMS[r.id].label,
    ratio: Number(r.ratio.toFixed(2)),
    color: ALGORITHMS[r.id].color,
  }));

  return (
    <div style={{ display: "grid", gap: 14 }}>
      <Card>
        <SectionTitle note={
          `Το φράγμα Shannon (${shannonRatio.toFixed(2)}%) ισχύει μόνο για μοντέλα ` +
          `μηδενικής τάξης· οι λεξικογραφικοί αλγόριθμοι επιτρέπεται να το περνούν, ` +
          `γιατί εκμεταλλεύονται εξαρτήσεις μεταξύ διαδοχικών συμβόλων.`
        }>
          Λόγος συμπίεσης — μικρότερο είναι καλύτερο
        </SectionTitle>
        <div style={{ height: 240 }}>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={chartData} margin={{ top: 8, right: 8, bottom: 4, left: -18 }}>
              <XAxis dataKey="name" tick={{ fill: SC.textDim, fontSize: 11 }}
                axisLine={{ stroke: SC.border }} tickLine={false} />
              <YAxis tick={{ fill: SC.textDim, fontSize: 11 }} unit="%"
                axisLine={{ stroke: SC.border }} tickLine={false} />
              <Tooltip
                contentStyle={{ background: SC.surface, border: `1px solid ${SC.border}`,
                  borderRadius: 8, fontSize: 12 }}
                labelStyle={{ color: SC.text }}
                formatter={(v) => [`${v}%`, "λόγος"]}
              />
              <ReferenceLine y={100} stroke={SC.bad} strokeDasharray="4 4"
                label={{ value: "χωρίς συμπίεση", fill: SC.bad, fontSize: 10, position: "right" }} />
              <ReferenceLine y={shannonRatio} stroke={SC.warn} strokeDasharray="4 4"
                label={{ value: "φράγμα Shannon", fill: SC.warn, fontSize: 10, position: "right" }} />
              <Bar dataKey="ratio" radius={[5, 5, 0, 0]}>
                {chartData.map((d, i) => <Cell key={i} fill={d.color} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </Card>

      <Card>
        <SectionTitle note={`Εντροπία εισόδου H(X) = ${entropy.toFixed(4)} bits/σύμβολο`}>
          Αναλυτικά μεγέθη
        </SectionTitle>
        <div style={{ overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
            <thead>
              <tr style={{ color: SC.muted, fontSize: 10, textTransform: "uppercase" }}>
                {["Αλγόριθμος", "Οικογένεια", "Κεφαλίδα", "Φορτίο", "Σύνολο",
                  "Ratio", "bits/σύμβ.", "Έλεγχος"].map((h, i) => (
                  <th key={h} style={{ textAlign: i > 1 ? "right" : "left",
                    padding: "7px 9px", borderBottom: `1px solid ${SC.border}`,
                    whiteSpace: "nowrap" }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {sorted.map(r => {
                const meta = ALGORITHMS[r.id];
                return (
                  <tr key={r.id}>
                    <td style={{ padding: "7px 9px", borderBottom: `1px solid ${SC.border}`,
                      color: meta.color, fontWeight: 600, whiteSpace: "nowrap" }}>
                      {meta.full}
                    </td>
                    <td style={{ padding: "7px 9px", borderBottom: `1px solid ${SC.border}`,
                      color: SC.textDim }}>{meta.family}</td>
                    {[
                      r.headerBits.toLocaleString(),
                      r.payloadBits.toLocaleString(),
                      r.totalBits.toLocaleString(),
                    ].map((v, i) => (
                      <td key={i} style={{ padding: "7px 9px", textAlign: "right",
                        borderBottom: `1px solid ${SC.border}`, fontFamily: MONO,
                        color: i === 0 ? SC.warn : SC.textDim }}>{v}</td>
                    ))}
                    <td style={{ padding: "7px 9px", textAlign: "right",
                      borderBottom: `1px solid ${SC.border}`, fontFamily: MONO,
                      color: r.ratio < 100 ? SC.good : SC.bad, fontWeight: 600 }}>
                      {r.ratio.toFixed(2)}%
                    </td>
                    <td style={{ padding: "7px 9px", textAlign: "right",
                      borderBottom: `1px solid ${SC.border}`, fontFamily: MONO,
                      color: SC.textDim }}>{r.bitsPerSymbol.toFixed(3)}</td>
                    <td style={{ padding: "7px 9px", textAlign: "right",
                      borderBottom: `1px solid ${SC.border}` }}>
                      <LosslessBadge ok={r.lossless} />
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
