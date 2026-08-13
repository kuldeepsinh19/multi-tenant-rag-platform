# platform-frontend

React + TypeScript admin dashboard and embeddable chat widget for a multi-tenant RAG
chatbot platform. Super-admins manage businesses; business admins upload documents and get
an embed snippet; website visitors chat with a business's dedicated, grounded chatbot via
the widget in `widget/`.

## Read the skills first

This repo's engineering standards live in `.claude/skills/` — Claude Code loads them
automatically by relevance. If your tool doesn't support skills, read these directly:

1. `.claude/skills/project-conventions/SKILL.md` — root: security baseline, secrets,
   error philosophy, architecture principles. Applies to **every** change.
2. `.claude/skills/react-frontend-standards/SKILL.md` — components, hooks, state,
   the API layer, streaming chat UI, a11y, frontend security.

## Non-negotiables (condensed — see the skills for full detail and rationale)

- **No provider keys, no secrets, no internal URLs in frontend code or `VITE_` env vars.**
  Everything shipped to the browser is public. All LLM calls go through the backend.
- **Server state lives in TanStack Query; UI state in local `useState`/Zustand.** Never
  duplicate server state into local state.
- **All backend calls go through `src/api/`** — one typed client, never scattered `fetch()`.
  Types generated from the backend's OpenAPI schema so contracts can't drift.
- **Never render model or user output as raw HTML.** Sanitize markdown with DOMPurify.
- **Handle every UI state**: loading, empty, error, 429 rate-limited, escalated-to-human.
- **Accessibility is not optional**: keyboard nav, `aria-live` for new chat messages,
  labeled inputs, color-contrast minimums.

## Project layout

```
src/
├── api/          # single typed API client (mirrors backend Pydantic schemas)
├── components/   # presentational components
├── pages/         # super-admin + business-admin dashboard views
├── hooks/        # useConversation(), useSendMessage(), etc. — data fetching lives here
└── store/        # Zustand, only for genuinely global UI state
widget/           # standalone embeddable chat widget bundle (separate build target)
```
