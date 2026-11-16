import { useState } from "react";

// Matches the sample employees in the backend's employees.json. Edit freely.
const ACCOUNTS = [
  { email: "priya@acme.com", name: "Priya Sharma", detail: "India, full time, engineering" },
  { email: "john@acme.com", name: "John Miller", detail: "United States, full time, manager" },
  { email: "ravi@acme.com", name: "Ravi Kumar", detail: "India, contractor, design" },
  { email: "hr@acme.com", name: "Asha (HR team)", detail: "Can see the HR inbox" },
];

export default function SignIn({ onSignIn, error }) {
  const [other, setOther] = useState("");

  function submitOther(e) {
    e.preventDefault();
    const email = other.trim().toLowerCase();
    if (email) onSignIn(email);
  }

  return (
    <main className="signin">
      <h1 className="wordmark">HR Help</h1>
      <p className="signin-lead">Choose an account to test with. This is development sign-in; company sign-in comes later.</p>
      {error && (
        <p className="inline-error" role="alert">
          {error}
        </p>
      )}
      <ul className="accounts">
        {ACCOUNTS.map((a) => (
          <li key={a.email}>
            <button type="button" className="account" onClick={() => onSignIn(a.email)}>
              <span className="account-name">{a.name}</span>
              <span className="account-detail">{a.detail}</span>
              <span className="account-email">{a.email}</span>
            </button>
          </li>
        ))}
      </ul>
      <form className="other" onSubmit={submitOther}>
        <label htmlFor="other-email">Another employee email</label>
        <div className="row">
          <input id="other-email" type="email" value={other} onChange={(e) => setOther(e.target.value)} placeholder="name@company.com" />
          <button type="submit" className="btn" disabled={!other.trim()}>
            Sign in
          </button>
        </div>
      </form>
    </main>
  );
}
