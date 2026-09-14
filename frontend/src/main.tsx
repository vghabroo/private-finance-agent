import { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import "./styles.css";

type Summary = {
  period: string;
  total_spent: number;
  total_income: number;
  net: number;
  transaction_count: number;
  categories: { category: string; spent: number; income: number; count: number }[];
};

type Transaction = {
  id: number;
  txn_date: string;
  merchant: string;
  amount: number;
  currency: string;
  txn_type: "debit" | "credit";
  category: string;
};

type Insight = {
  id: number;
  insight_type: string;
  detail: string;
  resolved: number;
  created_at: string;
};

type TraceItem = {
  step: number;
  tool: string;
  arguments: Record<string, unknown>;
  result: unknown;
  requires_confirmation: boolean;
};

const API = "http://localhost:8000/api";

const MONTH_LABELS = Array.from({ length: 12 }, (_, i) =>
  new Date(2000, i, 1).toLocaleString("en-US", { month: "long" })
);

const CHART_COLORS = [
  "#4f46e5", "#059669", "#d97706", "#dc2626", "#2563eb",
  "#7c3aed", "#0891b2", "#db2777", "#65a30d", "#ea580c",
];

const money = (value: number) =>
  new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 }).format(value);

const monthName = (period: string) => {
  const [year, month] = period.split("-").map(Number);
  return new Date(year, month - 1, 1).toLocaleString("en-US", { month: "long" });
};

function App() {
  const now = new Date();

  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [insights, setInsights] = useState<Insight[]>([]);

  const [file, setFile] = useState<File | null>(null);
  const [importStatus, setImportStatus] = useState("");
  const [gmailStatus, setGmailStatus] = useState("");

  const [question, setQuestion] = useState("Why did I spend more this month?");
  const [answer, setAnswer] = useState("");
  const [trace, setTrace] = useState<TraceItem[]>([]);

  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const [transactionLimit, setTransactionLimit] = useState(15);

  // Single source of truth for "which month is the dashboard showing" — the
  // spending metric and the pie chart both read from this, so switching
  // months never leaves one part of the page showing a different month's data.
  const [selectedYear, setSelectedYear] = useState(now.getFullYear());
  const [selectedMonth, setSelectedMonth] = useState(now.getMonth() + 1);
  const [monthSummary, setMonthSummary] = useState<Summary | null>(null);

  // Cache of already-fetched months, keyed by "YYYY-M", so revisiting a month
  // shows it instantly instead of refetching. Cleared on import/sync, since
  // that's the only thing that can change what a month's data looks like.
  const [monthCache, setMonthCache] = useState<Record<string, Summary>>({});

  function monthDateRange(year: number, month: number) {
    const start = `${year}-${String(month).padStart(2, "0")}-01`;
    const daysInMonth = new Date(year, month, 0).getDate();
    const end = `${year}-${String(month).padStart(2, "0")}-${String(daysInMonth).padStart(2, "0")}`;
    return { start, end };
  }

  async function loadTransactions(year: number, month: number, limit: number) {
    const { start, end } = monthDateRange(year, month);
    const t = await fetch(
      `${API}/transactions?start_date=${start}&end_date=${end}&limit=${limit}`
    ).then((r) => r.json());
    setTransactions(t);
  }

  async function loadMonthSummary(year: number, month: number, force = false) {
    const key = `${year}-${month}`;

    if (!force && monthCache[key]) {
      setMonthSummary(monthCache[key]);
      return;
    }

    setMonthSummary(null); // clear immediately so a slow fetch never shows the old month's data
    const s = await fetch(`${API}/summary/${year}/${month}`).then((r) => r.json());
    setMonthCache((prev) => ({ ...prev, [key]: s }));
    setMonthSummary(s);
  }

  function goToMonth(year: number, month: number) {
    setSelectedYear(year);
    setSelectedMonth(month);
    setTransactionLimit(15);
    loadMonthSummary(year, month);
    loadTransactions(year, month, 15);
    loadInsights(year, month);
  }

  function shiftMonth(delta: number) {
    let year = selectedYear;
    let month = selectedMonth + delta;
    if (month < 1) { month = 12; year -= 1; }
    if (month > 12) { month = 1; year += 1; }
    goToMonth(year, month);
  }

  function jumpToMonth(year: number, month: number) {
    goToMonth(year, month);
  }

  const isCurrentSelectedMonth = selectedYear === now.getFullYear() && selectedMonth === now.getMonth() + 1;
  const yearOptions = Array.from({ length: 5 }, (_, i) => now.getFullYear() - i);
  const maxSelectableMonth = selectedYear === now.getFullYear() ? now.getMonth() + 1 : 12;
  const monthOptions = Array.from({ length: maxSelectableMonth }, (_, i) => i + 1);

  async function loadInsights(year: number, month: number) {
    const i = await fetch(
      `${API}/insights?unresolved_only=true&year=${year}&month=${month}`
    ).then((r) => r.json());
    setInsights(i);
  }

  async function refresh(invalidateMonths = false) {
    if (invalidateMonths) setMonthCache({});

    await Promise.all([
      loadInsights(selectedYear, selectedMonth),
      loadTransactions(selectedYear, selectedMonth, transactionLimit),
      loadMonthSummary(selectedYear, selectedMonth, invalidateMonths),
    ]);
  }

  function showMoreTransactions() {
    const next = transactionLimit + 15;
    setTransactionLimit(next);
    loadTransactions(selectedYear, selectedMonth, next);
  }

  useEffect(() => {
    refresh().catch((e) => setError(String(e)));
  }, []);

  async function importCsv() {
    if (!file) return;
    setBusy(true);
    setError("");
    const form = new FormData();
    form.append("file", file);

    try {
      const response = await fetch(`${API}/import/csv`, { method: "POST", body: form });
      const body = await response.json();
      if (!response.ok) throw new Error(body.detail ?? "Import failed");
      setImportStatus(`Imported ${body.inserted}; skipped ${body.skipped_duplicates} duplicates.`);
      await refresh(true);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  async function syncGmail() {
    setBusy(true);
    setError("");
    setGmailStatus("");

    try {
      const response = await fetch(`${API}/import/gmail`, { method: "POST" });
      const body = await response.json();
      if (!response.ok) throw new Error(body.detail ?? "Gmail sync failed");
      setGmailStatus(
        `Scanned ${body.scanned_emails} emails — imported ${body.inserted}, skipped ${body.skipped_duplicates} duplicates, ${body.unparsed_emails} unrecognized.`
      );
      await refresh(true);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  async function setBudget(category: string, amount: number) {
    const response = await fetch(`${API}/budgets`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ category, new_amount: amount }),
    });
    const body = await response.json();
    if (!response.ok) throw new Error(body.detail ?? "Could not set budget");
    await refresh();
  }

  async function resolveInsight(id: number) {
    await fetch(`${API}/insights/${id}/resolve`, { method: "POST" });
    await refresh();
  }

  async function scanInsights() {
    setBusy(true);
    setError("");
    try {
      await fetch(`${API}/insights/run`, { method: "POST" });
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  async function askAgent() {
    setBusy(true);
    setError("");
    setAnswer("");
    setTrace([]);

    try {
      const response = await fetch(`${API}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: question }),
      });
      const body = await response.json();
      if (!response.ok) throw new Error(body.detail ?? "Agent request failed");
      setAnswer(body.answer);
      setTrace(body.tool_trace);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  async function confirmProposal(item: TraceItem) {
    const args = item.arguments as { category: string; new_amount: number };
    setError("");
    try {
      await setBudget(args.category, args.new_amount);
      setTrace((prev) => prev.filter((x) => x !== item));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  function dismissProposal(item: TraceItem) {
    setTrace((prev) => prev.filter((x) => x !== item));
  }

  const proposals = trace.filter((item) => item.requires_confirmation);

  return (
    <div className="shell">
      <header className="hero">
        <div>
          <div className="eyebrow">PRIVATE FINANCE • LOCAL AGENT</div>
          <h1>Know where your money goes.</h1>
        </div>
        <div className="privacy">
          <strong>LOCAL MODE</strong>
          <span>Data is stored locally</span>
        </div>
      </header>

      {error && <div className="error">{error}</div>}

      <section className="card import-card">
        <div>
          <h2>Import transactions</h2>
          <p>Sync directly from Gmail transaction alerts. CSV import is available as a fallback.</p>
        </div>
        <div className="import-controls">
          <button onClick={syncGmail} disabled={busy}>Sync Gmail</button>
          <input type="file" accept=".csv" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
          <button className="ghost" onClick={importCsv} disabled={!file || busy}>Import CSV</button>
        </div>
        {gmailStatus && <div className="success">{gmailStatus}</div>}
        {importStatus && <div className="success">{importStatus}</div>}
      </section>

      <section className="metrics">
        <Metric
          label={monthSummary ? `${monthName(monthSummary.period)} spending` : "Spending"}
          value={monthSummary ? money(monthSummary.total_spent) : "—"}
        />
      </section>

      <div className="two-column">
        <section className="card">
          <div className="section-heading">
            <div><h2>Spending breakdown</h2><span>By category</span></div>
          </div>
          <div className="month-nav">
            <button className="ghost" onClick={() => shiftMonth(-1)} aria-label="Previous month">‹</button>
            <select
              value={selectedMonth}
              onChange={(e) => jumpToMonth(selectedYear, Number(e.target.value))}
              aria-label="Select month"
            >
              {monthOptions.map((m) => (
                <option key={m} value={m}>{MONTH_LABELS[m - 1]}</option>
              ))}
            </select>
            <select
              value={selectedYear}
              onChange={(e) => {
                const year = Number(e.target.value);
                const month = year === now.getFullYear() ? Math.min(selectedMonth, now.getMonth() + 1) : selectedMonth;
                jumpToMonth(year, month);
              }}
              aria-label="Select year"
            >
              {yearOptions.map((y) => (
                <option key={y} value={y}>{y}</option>
              ))}
            </select>
            <button className="ghost" onClick={() => shiftMonth(1)} disabled={isCurrentSelectedMonth} aria-label="Next month">›</button>
          </div>
          <PieChart data={monthSummary?.categories.filter((c) => c.spent > 0) ?? []} />
        </section>

        <section className="card agent-card">
          <div className="section-heading">
            <div><h2>Finance Agent</h2><span>Ask questions in natural language</span></div>
          </div>
          <textarea value={question} onChange={(e) => setQuestion(e.target.value)} />
          <button className="primary" onClick={askAgent} disabled={busy}>
            {busy ? "Working locally…" : "Ask agent"}
          </button>
          {answer && <div className="answer">{answer}</div>}

          {proposals.length > 0 && (
            <div className="proposals">
              {proposals.map((item, i) => {
                const args = item.arguments as { category: string; new_amount: number };
                return (
                  <div className="proposal" key={i}>
                    <div>
                      Agent proposes setting the <strong>{args.category}</strong> budget to{" "}
                      <strong>{money(args.new_amount)}</strong>/month. Nothing has been changed yet.
                    </div>
                    <div className="proposal-actions">
                      <button onClick={() => confirmProposal(item)}>Confirm</button>
                      <button className="ghost" onClick={() => dismissProposal(item)}>Dismiss</button>
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          {trace.length > 0 && (
            <details>
              <summary>Agent execution trace · {trace.length} tool calls</summary>
              {trace.map((item, i) => <pre key={i}>{JSON.stringify(item, null, 2)}</pre>)}
            </details>
          )}
        </section>
      </div>

      <section className="card">
        <div className="section-heading">
          <div><h2>Watcher insights</h2><span>{insights.length} open</span></div>
          <button className="ghost" onClick={scanInsights} disabled={busy}>Scan now</button>
        </div>
        {insights.length === 0 && <p>No open insights. Run a scan, or wait for the nightly job.</p>}
        {insights.map((insight) => (
          <div className="insight" key={insight.id}>
            <span className={`tag ${insight.insight_type}`}>{insight.insight_type}</span>
            <span>{insight.detail}</span>
            <button className="ghost" onClick={() => resolveInsight(insight.id)}>Resolve</button>
          </div>
        ))}
      </section>

      <section className="card">
        <div className="section-heading">
          <div><h2>Transactions</h2><span>{monthSummary ? monthName(monthSummary.period) : ""} {selectedYear} · Newest first</span></div>
        </div>
        <TransactionList transactions={transactions} />
        <button className="ghost show-more" onClick={showMoreTransactions} disabled={busy}>
          Show more
        </button>
      </section>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return <div className="metric"><span>{label}</span><strong>{value}</strong></div>;
}

function PieChart({ data }: { data: { category: string; spent: number }[] }) {
  const total = data.reduce((sum, d) => sum + d.spent, 0);

  if (total <= 0) {
    return <p>No spending recorded for this period.</p>;
  }

  let cursor = 0;
  const stops = data.map((d, i) => {
    const start = cursor;
    cursor += (d.spent / total) * 100;
    return `${CHART_COLORS[i % CHART_COLORS.length]} ${start}% ${cursor}%`;
  });

  return (
    <div className="pie-row">
      <div className="pie" style={{ background: `conic-gradient(${stops.join(", ")})` }} />
      <ul className="pie-legend">
        {data.map((d, i) => (
          <li key={d.category}>
            <span className="swatch" style={{ background: CHART_COLORS[i % CHART_COLORS.length] }} />
            <span>{d.category}</span>
            <strong>{money(d.spent)} ({((d.spent / total) * 100).toFixed(0)}%)</strong>
          </li>
        ))}
      </ul>
    </div>
  );
}

function TransactionList({ transactions }: { transactions: Transaction[] }) {
  if (transactions.length === 0) {
    return <p>No transactions yet. Sync Gmail or import a CSV to get started.</p>;
  }

  const groups: { date: string; items: Transaction[] }[] = [];
  for (const txn of transactions) {
    const last = groups[groups.length - 1];
    if (last && last.date === txn.txn_date) {
      last.items.push(txn);
    } else {
      groups.push({ date: txn.txn_date, items: [txn] });
    }
  }

  const formatDate = (isoDate: string) => {
    const [year, month, day] = isoDate.split("-").map(Number);
    return new Date(year, month - 1, day).toLocaleDateString("en-US", {
      weekday: "short", day: "numeric", month: "short", year: "numeric",
    });
  };

  return (
    <div className="transaction-groups">
      {groups.map((group) => {
        const net = group.items.reduce(
          (sum, t) => sum + (t.txn_type === "credit" ? t.amount : -t.amount),
          0
        );
        return (
          <div className="transaction-group" key={group.date}>
            <div className="transaction-group-header">
              <span>{formatDate(group.date)}</span>
              <strong className={net >= 0 ? "credit" : "debit"}>
                {net >= 0 ? "+" : "−"} {money(Math.abs(net))}
              </strong>
            </div>
            <div className="transactions">
              {group.items.map((txn) => (
                <div className="transaction" key={txn.id}>
                  <span>{txn.merchant}</span>
                  <span>{txn.category}</span>
                  <strong className={txn.txn_type}>
                    {txn.txn_type === "credit" ? "+" : "−"} {money(txn.amount)}
                  </strong>
                </div>
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}

createRoot(document.getElementById("root")!).render(<App />);
