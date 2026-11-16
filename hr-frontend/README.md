# HR Help: Frontend

React (Vite) chat app for the HR Policy Assistant backend.

## Run (Windows, macOS or Linux)
You need Node.js 18 or newer (`node --version`). Get it from nodejs.org if missing.

1. Start the backend first (in its own terminal): `uvicorn hr_assistant.api:create_app --factory --reload`
2. In this folder:
```bash
npm install
npm run dev
```
3. Open http://localhost:5173 and pick an account.

In development the app calls `/api/...` on its own address and Vite forwards it to
`http://127.0.0.1:8000`, so there is nothing to configure and no CORS setup.

## What it does
- **Sign-in screen:** development accounts only (matches the backend's `employees.json`). Any email in that file works through "Another employee email".
- **Ask HR:** chat with memory (the backend keeps the conversation; refreshing the page keeps it too). Each answer shows the policy excerpts it is based on, highlighted. Page numbers appear when the source has them.
- **Talk to HR:** appears under answers, and prominently when the assistant couldn't find an answer or the topic is sensitive. Sends a ticket with the conversation and an optional note.
- **Helpful / Not helpful:** sent to the backend log.
- **HR inbox:** only for accounts with `"is_hr": true`. Filter tickets by status, read the conversation, assign to yourself, start work, mark resolved, reopen. Refreshes every 30 seconds.

## Files
| File | Purpose |
|---|---|
| `src/api.js` | All backend calls, the sign-in header, and friendly error messages |
| `src/App.jsx` | Sign-in gate, sidebar and switching between Ask HR and HR inbox |
| `src/SignIn.jsx` | Development account picker |
| `src/Chat.jsx` | Conversation, excerpts, Talk to HR form, feedback, composer |
| `src/HRInbox.jsx` | Ticket list and detail for HR staff |
| `src/format.js` | Country names and date formatting |
| `src/styles.css` | All styling: colours and fonts are variables at the top |
| `vite.config.js` | Dev server and the `/api` proxy |

## Production build
```bash
# set the backend address, then build
echo VITE_API_URL=https://your-backend.example.com > .env
npm run build        # output in dist/
```
Host `dist/` on any static host and add that address to `ALLOWED_ORIGINS` in the backend's `.env`.
Before real use, replace the dev sign-in: change `headers()` in `src/api.js` to send a real login token.

## Known limits
- Dev sign-in has no password; anyone who can open the page can pick any account.
- Chat history is kept in the browser tab (session storage) and on the backend, which forgets it on restart.
- Document links in excerpts appear only after originals move to blob storage; until then excerpts show the file title.
