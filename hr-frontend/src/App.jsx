import { useEffect, useState } from "react";
import { getMe, setUser } from "./api";
import { scopeLabel } from "./format";
import SignIn from "./SignIn";
import Chat from "./Chat";
import HRInbox from "./HRInbox";

const USER_KEY = "hr.user";

export default function App() {
  const [email, setEmail] = useState(() => {
    try {
      return sessionStorage.getItem(USER_KEY) || "";
    } catch {
      return "";
    }
  });
  const [me, setMe] = useState(null);
  const [error, setError] = useState("");
  const [view, setView] = useState("chat");

  useEffect(() => {
    if (!email) return;
    let cancelled = false;
    setUser(email);
    setMe(null);
    getMe()
      .then((profile) => !cancelled && setMe(profile))
      .catch((e) => {
        if (cancelled) return;
        setError(`${e.message} (${email})`);
        signOut();
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [email]);

  function signIn(next) {
    setError("");
    try {
      sessionStorage.setItem(USER_KEY, next);
    } catch {
      /* storage blocked: sign-in lasts until refresh */
    }
    setEmail(next);
  }

  function signOut() {
    try {
      sessionStorage.removeItem(USER_KEY);
    } catch {
      /* ignore */
    }
    setEmail("");
    setMe(null);
    setView("chat");
  }

  if (!email) return <SignIn onSignIn={signIn} error={error} />;
  if (!me) return <p className="loading-screen" role="status">Loading your profile…</p>;

  return (
    <div className="shell">
      <aside className="side">
        <h1 className="wordmark">HR Help</h1>
        <nav className="nav" aria-label="Main">
          <button type="button" className="nav-item" aria-current={view === "chat" ? "page" : undefined} onClick={() => setView("chat")}>
            Ask HR
          </button>
          {me.is_hr && (
            <button type="button" className="nav-item" aria-current={view === "inbox" ? "page" : undefined} onClick={() => setView("inbox")}>
              HR inbox
            </button>
          )}
        </nav>
        <div className="who">
          <p className="who-name">{me.name}</p>
          <p className="who-scope">{scopeLabel(me)}</p>
          <button type="button" className="link" onClick={signOut}>
            Sign out
          </button>
        </div>
      </aside>
      <main className="main">{view === "chat" ? <Chat me={me} /> : <HRInbox me={me} />}</main>
    </div>
  );
}
