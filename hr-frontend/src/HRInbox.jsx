import { useCallback, useEffect, useState } from "react";
import { listTickets, updateTicket } from "./api";
import { COUNTRIES, formatTime } from "./format";

const FILTERS = [
  ["open", "Open"],
  ["in_progress", "In progress"],
  ["resolved", "Resolved"],
  ["all", "All"],
];
const STATUS_LABEL = { open: "Open", in_progress: "In progress", resolved: "Resolved" };

export default function HRInbox({ me }) {
  const [filter, setFilter] = useState("open");
  const [tickets, setTickets] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      const r = await listTickets(filter === "all" ? undefined : filter);
      setTickets(r.tickets);
      setError("");
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [filter]);

  useEffect(() => {
    setLoading(true);
    load();
    const timer = setInterval(load, 30000);
    return () => clearInterval(timer);
  }, [load]);

  const selected = tickets.find((t) => t.id === selectedId) || tickets[0] || null;

  async function change(changes) {
    if (!selected) return;
    setSaving(true);
    try {
      const updated = await updateTicket(selected.id, changes);
      setTickets((list) =>
        filter === "all" || filter === updated.status
          ? list.map((t) => (t.id === updated.id ? updated : t))
          : list.filter((t) => t.id !== updated.id)
      );
      setError("");
    } catch (e) {
      setError(e.message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="inbox">
      <header className="chat-head">
        <div>
          <h2 className="page-title">HR inbox</h2>
          <p className="scope">Questions employees sent to HR. The list refreshes every 30 seconds.</p>
        </div>
      </header>

      <div className="filters" role="tablist" aria-label="Ticket status">
        {FILTERS.map(([value, label]) => (
          <button
            key={value}
            type="button"
            role="tab"
            aria-selected={filter === value}
            className="filter"
            onClick={() => setFilter(value)}
          >
            {label}
          </button>
        ))}
      </div>

      {error && (
        <p className="inline-error" role="alert">
          {error}
        </p>
      )}

      <div className="inbox-body">
        <ul className="ticket-list" aria-label="Tickets">
          {loading && <li className="muted">Loading tickets…</li>}
          {!loading && tickets.length === 0 && <li className="muted">No tickets in this view.</li>}
          {tickets.map((t) => (
            <li key={t.id}>
              <button
                type="button"
                className="ticket-row"
                aria-current={selected && selected.id === t.id ? "true" : undefined}
                onClick={() => setSelectedId(t.id)}
              >
                <span className="ticket-top">
                  <span className="ticket-name">{t.employee_name}</span>
                  <span className="ticket-status">{STATUS_LABEL[t.status] || t.status}</span>
                </span>
                <span className="ticket-question">{t.question || "No question text"}</span>
                <span className="ticket-time">{formatTime(t.created_at)}</span>
              </button>
            </li>
          ))}
        </ul>

        {selected ? (
          <article className="ticket-detail">
            <h3 className="ticket-title">Ticket #{selected.id}</h3>
            <dl className="facts">
              <div>
                <dt>Employee</dt>
                <dd>
                  {selected.employee_name} ({selected.employee_email})
                </dd>
              </div>
              <div>
                <dt>Country</dt>
                <dd>{COUNTRIES[selected.country] || selected.country}</dd>
              </div>
              <div>
                <dt>Sent</dt>
                <dd>{formatTime(selected.created_at)}</dd>
              </div>
              <div>
                <dt>Why it was sent</dt>
                <dd>{selected.reason}</dd>
              </div>
              <div>
                <dt>Status</dt>
                <dd>
                  {STATUS_LABEL[selected.status] || selected.status}
                  {selected.assigned_to ? `, assigned to ${selected.assigned_to}` : ", unassigned"}
                </dd>
              </div>
            </dl>

            <h4 className="detail-heading">Question</h4>
            <p className="detail-text">{selected.question || "No question text"}</p>

            {selected.note && (
              <>
                <h4 className="detail-heading">Note from the employee</h4>
                <p className="detail-text">{selected.note}</p>
              </>
            )}

            {selected.transcript.length > 0 && (
              <>
                <h4 className="detail-heading">Conversation so far</h4>
                <ol className="transcript">
                  {selected.transcript.map((turn, i) => (
                    <li key={i}>
                      <p className="t-q">{turn.question}</p>
                      <p className="t-a">{turn.answer}</p>
                    </li>
                  ))}
                </ol>
              </>
            )}

            <div className="row actions">
              {selected.assigned_to !== me.email && (
                <button type="button" className="btn ghost" disabled={saving} onClick={() => change({ assigned_to: me.email })}>
                  Assign to me
                </button>
              )}
              {selected.status === "open" && (
                <button type="button" className="btn human" disabled={saving} onClick={() => change({ status: "in_progress" })}>
                  Start working
                </button>
              )}
              {selected.status !== "resolved" && (
                <button type="button" className="btn" disabled={saving} onClick={() => change({ status: "resolved" })}>
                  Mark resolved
                </button>
              )}
              {selected.status === "resolved" && (
                <button type="button" className="btn ghost" disabled={saving} onClick={() => change({ status: "open" })}>
                  Reopen
                </button>
              )}
            </div>
          </article>
        ) : (
          !loading && <p className="muted ticket-empty">Select a ticket to read it.</p>
        )}
      </div>
    </section>
  );
}
