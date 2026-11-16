// Every request carries the signed-in email in X-Dev-User (development sign-in).
// When real sign-in is added, replace the header in headers() with a Bearer token.
const BASE = import.meta.env.VITE_API_URL || "/api";

let currentUser = "";
export const setUser = (email) => {
  currentUser = email;
};

export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.status = status;
  }
}

const headers = () => ({ "Content-Type": "application/json", "X-Dev-User": currentUser });

async function request(method, path, body) {
  let res;
  try {
    res = await fetch(BASE + path, {
      method,
      headers: headers(),
      body: body ? JSON.stringify(body) : undefined,
    });
  } catch {
    throw new ApiError("Can't reach the server. Check that the backend is running on port 8000.", 0);
  }
  if (!res.ok) {
    let detail = "";
    try {
      const data = await res.json();
      detail = typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail);
    } catch {
      /* response had no JSON body */
    }
    throw new ApiError(detail || `Request failed (${res.status})`, res.status);
  }
  return res.json();
}

export const getMe = () => request("GET", "/me");
export const ask = (question, conversationId) =>
  request("POST", "/ask", { question, conversation_id: conversationId || null });
export const clearConversation = (id) => request("DELETE", `/conversations/${encodeURIComponent(id)}`);
export const escalate = (conversationId, question, note) =>
  request("POST", "/escalate", { conversation_id: conversationId || null, question: question || "", note: note || "" });
export const sendFeedback = (conversationId, helpful, comment = "") =>
  request("POST", "/feedback", { conversation_id: conversationId, helpful, comment });
export const listTickets = (status) => request("GET", `/hr/tickets${status ? `?status=${status}` : ""}`);
export const updateTicket = (id, changes) => request("PATCH", `/hr/tickets/${id}`, changes);
