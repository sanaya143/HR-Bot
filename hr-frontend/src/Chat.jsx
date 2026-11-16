import { useEffect, useRef, useState } from "react";
import { ask, clearConversation, escalate, sendFeedback } from "./api";
import { scopeLabel } from "./format";

const STARTERS = [
  "How many casual leave days do I get?",
  "What is the notice period if I resign?",
  "Can I work from home every day?",
];

let counter = 0;
const uid = () => `${Date.now()}-${counter++}`;

const storeKey = (email) => `hr.chat.${email}`;
function loadChat(email) {
  try {
    return JSON.parse(sessionStorage.getItem(storeKey(email))) || {};
  } catch {
    return {};
  }
}
function saveChat(email, data) {
  try {
    sessionStorage.setItem(storeKey(email), JSON.stringify(data));
  } catch {
    /* storage full or blocked: the chat still works, it just won't survive a refresh */
  }
}

function Excerpt({ c }) {
  const label = c.page ? `${c.title}, page ${c.page}` : c.title;
  const text = c.snippet.trim() + (c.snippet.length >= 220 ? "…" : "");
  return (
    <li className="excerpt">
      <p className="excerpt-source">
        {c.url ? (
          <a href={c.url} target="_blank" rel="noreferrer">
            {label}
          </a>
        ) : (
          label
        )}
      </p>
      <p className="excerpt-text">
        <mark>{text}</mark>
      </p>
    </li>
  );
}

function EscalateBox({ msg, conversationId, onSent, primary }) {
  const [open, setOpen] = useState(false);
  const [note, setNote] = useState("");
  const [sending, setSending] = useState(false);
  const [err, setErr] = useState("");

  if (msg.ticketId) {
    return (
      <p className="sent" role="status">
        Sent to HR as ticket #{msg.ticketId}. A person will follow up with you.
      </p>
    );
  }
  if (!open) {
    return (
      <button type="button" className={primary ? "btn human" : "link"} onClick={() => setOpen(true)}>
        Talk to HR
      </button>
    );
  }

  async function submit(e) {
    e.preventDefault();
    setSending(true);
    setErr("");
    try {
      const r = await escalate(conversationId, msg.question, note.trim());
      onSent(r.ticket_id);
    } catch (ex) {
      setErr(ex.message);
    } finally {
      setSending(false);
    }
  }

  return (
    <form className="escalate-form" onSubmit={submit}>
      <label htmlFor={`note-${msg.id}`}>Add details for HR (optional)</label>
      <textarea id={`note-${msg.id}`} rows={3} maxLength={2000} value={note} onChange={(e) => setNote(e.target.value)} />
      {err && (
        <p className="inline-error" role="alert">
          {err}
        </p>
      )}
      <div className="row">
        <button type="submit" className="btn human" disabled={sending}>
          {sending ? "Sending…" : "Send to HR"}
        </button>
        <button type="button" className="link" onClick={() => setOpen(false)}>
          Cancel
        </button>
      </div>
    </form>
  );
}

function BotMessage({ m, conversationId, patch, retry }) {
  if (m.error) {
    return (
      <div className="msg bot error" role="alert">
        <p>{m.text}</p>
        <button type="button" className="link" onClick={() => retry(m)}>
          Try again
        </button>
      </div>
    );
  }

  const answered = m.answeredFrom === "documents" || m.answeredFrom === "cache";
  const citations = m.citations || [];

  async function rate(helpful) {
    patch(m.id, { rated: helpful ? "up" : "down" });
    try {
      await sendFeedback(conversationId, helpful);
    } catch {
      patch(m.id, { rated: null });
    }
  }

  return (
    <div className="msg bot">
      <p className="answer">{m.text}</p>

      {citations.length > 0 && (
        <>
          <p className="based-on">Based on {citations.length === 1 ? "this policy text" : `${citations.length} policy excerpts`}</p>
          <ul className="excerpts">
            {citations.map((c) => (
              <Excerpt key={c.id} c={c} />
            ))}
          </ul>
        </>
      )}

      {m.escalate && (
        <div className="callout">
          <p>
            {m.answeredFrom === "escalation"
              ? "A person can handle this properly. Send it to HR and they will follow up with you."
              : "HR can answer this one. Send your question and they will reply to you."}
          </p>
          <EscalateBox msg={m} conversationId={conversationId} primary onSent={(id) => patch(m.id, { ticketId: id })} />
        </div>
      )}

      {answered && (
        <div className="message-actions">
          {m.rated ? (
            <span className="thanks" role="status">
              Thanks for the feedback.
            </span>
          ) : (
            <span className="rate">
              <button type="button" className="link" onClick={() => rate(true)}>
                Helpful
              </button>
              <button type="button" className="link" onClick={() => rate(false)}>
                Not helpful
              </button>
            </span>
          )}
          <EscalateBox msg={m} conversationId={conversationId} onSent={(id) => patch(m.id, { ticketId: id })} />
        </div>
      )}
    </div>
  );
}

export default function Chat({ me }) {
  const saved = useRef(loadChat(me.email)).current;
  const [conversationId, setConversationId] = useState(saved.conversationId || null);
  const [msgs, setMsgs] = useState(saved.msgs || []);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const endRef = useRef(null);
  const inputRef = useRef(null);

  useEffect(() => {
    saveChat(me.email, { conversationId, msgs });
  }, [me.email, conversationId, msgs]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ block: "end", behavior: "smooth" });
  }, [msgs, busy]);

  useEffect(() => {
    const el = inputRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 160)}px`;
  }, [text]);

  const patch = (id, changes) => setMsgs((ms) => ms.map((m) => (m.id === id ? { ...m, ...changes } : m)));

  async function send(question) {
    const q = (question ?? text).trim();
    if (!q || busy) return;
    setText("");
    setBusy(true);
    setMsgs((ms) => [...ms, { id: uid(), role: "user", text: q }]);
    try {
      const r = await ask(q, conversationId);
      setConversationId(r.conversation_id);
      setMsgs((ms) => [
        ...ms,
        {
          id: uid(),
          role: "bot",
          question: q,
          text: r.answer,
          citations: r.citations || [],
          answeredFrom: r.answered_from,
          escalate: r.escalate,
          ticketId: r.ticket_id || null,
        },
      ]);
    } catch (e) {
      setMsgs((ms) => [...ms, { id: uid(), role: "bot", error: true, question: q, text: e.message }]);
    } finally {
      setBusy(false);
    }
  }

  function retry(errorMsg) {
    setMsgs((ms) => ms.filter((m) => m.id !== errorMsg.id).slice(0, -1));
    send(errorMsg.question);
  }

  async function newConversation() {
    const id = conversationId;
    setMsgs([]);
    setConversationId(null);
    setText("");
    if (id) {
      try {
        await clearConversation(id);
      } catch {
        /* the server forgets old conversations on its own */
      }
    }
  }

  function onKeyDown(e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  }

  return (
    <section className="chat">
      <header className="chat-head">
        <div>
          <h2 className="page-title">Ask HR</h2>
          <p className="scope">Answers come from the policies that apply to you: {scopeLabel(me)}.</p>
        </div>
        <button type="button" className="btn ghost" onClick={newConversation} disabled={!msgs.length || busy}>
          New conversation
        </button>
      </header>

      <div className="log" role="log" aria-live="polite" aria-label="Conversation">
        {msgs.length === 0 && (
          <div className="empty">
            <p className="empty-title">What would you like to know?</p>
            <p>Ask about leave, notice period, expenses or any other HR policy. Every answer shows the policy text it came from.</p>
            <ul className="starters">
              {STARTERS.map((s) => (
                <li key={s}>
                  <button type="button" className="starter" onClick={() => send(s)}>
                    {s}
                  </button>
                </li>
              ))}
            </ul>
          </div>
        )}
        {msgs.map((m) =>
          m.role === "user" ? (
            <div key={m.id} className="msg user">
              <p>{m.text}</p>
            </div>
          ) : (
            <BotMessage key={m.id} m={m} conversationId={conversationId} patch={patch} retry={retry} />
          )
        )}
        {busy && (
          <p className="thinking" role="status">
            Checking your policy documents<span className="dots" aria-hidden="true"></span>
          </p>
        )}
        <div ref={endRef} />
      </div>

      <form
        className="composer"
        onSubmit={(e) => {
          e.preventDefault();
          send();
        }}
      >
        <label htmlFor="question" className="sr-only">
          Your question
        </label>
        <textarea
          id="question"
          ref={inputRef}
          rows={1}
          maxLength={1000}
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={onKeyDown}
          placeholder="Type your question"
        />
        <button type="submit" className="btn" disabled={busy || !text.trim()}>
          Ask
        </button>
      </form>
    </section>
  );
}
