# Frontend

React + TypeScript app for the Social Listening Outreach Agent (Vite, Tailwind, TanStack Query).

```bash
npm ci            # install exact versions from package-lock.json
npm run dev       # http://localhost:5173, /api is forwarded to the backend on :8000
npm run typecheck
npm run lint
npm test
npm run build     # writes dist/, which the FastAPI backend serves in production
```
