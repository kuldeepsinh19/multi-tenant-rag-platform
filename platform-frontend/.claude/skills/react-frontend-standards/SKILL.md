---
name: react-frontend-standards
description: Clean-architecture and safety standards for the React + TypeScript frontend of this AI project. Use this whenever writing, reviewing, or refactoring any frontend code — components, hooks, state, API calls, streaming chat UI, forms — so Claude builds accessible, secure, well-structured React without being re-told the rules. Triggers on any mention of React, components, hooks, TSX, the chat UI, frontend, or client-side work, even for a small change.
---

# React frontend standards

Assumes the root `project-conventions` skill. This covers the browser side of a
production AI app whose backend is FastAPI + a LangGraph agent.

## Stack baseline

- **React 18+ with TypeScript, strict mode on.** No `any` unless truly unavoidable and
  commented. Prefer `unknown` + narrowing over `any`.
- **Vite** for build/dev. Function components + hooks only — no class components.
- **Data fetching via TanStack Query** (React Query) for server state, not raw `useEffect`
  fetch chains. It gives you caching, retries, loading/error states, and dedup for free —
  hand-rolling those is where bugs live.

## Component architecture

- **Presentational vs container split.** Components that render should not also fetch,
  transform, and hold business logic. Push data-fetching into hooks (`useConversation()`,
  `useSendMessage()`) and keep the component focused on rendering.
- **One component, one responsibility.** If a component file is over ~150 lines or has
  more than a couple of `useState`s doing unrelated things, split it.
- **Colocate.** A component's styles, tests, and local types live next to it, not in a
  distant `types/` dump.
- **No prop drilling past 2 levels.** Use composition (`children`) or a scoped context.
  Don't reach for global state to avoid passing one prop.

## State management

- **Server state ≠ UI state.** Server state (messages, retrieval results, agent status)
  lives in React Query. UI state (is-this-modal-open, draft input text) lives in local
  `useState` or a small store (Zustand) if it's genuinely global.
- **Never duplicate server state into local state** and try to keep them in sync — that
  desync is a classic bug. Read from the query cache.
- **Derive, don't store.** If a value can be computed from existing state, compute it in
  render; don't add a `useState` + `useEffect` to mirror it.

## The API layer

- **All backend calls go through a single typed API client module** (`src/api/`), never
  `fetch()` scattered in components. One place to add auth headers, base URL, error
  normalization, and retries.
- **Request/response types mirror the backend Pydantic models.** When the backend schema
  changes, the TS type changes with it. Consider generating types from the OpenAPI schema
  the FastAPI backend exposes, so they can't drift.
- **Handle every state the UI can be in:** loading, empty, error, success, and — for this
  app specifically — *rate-limited (429)* and *escalated-to-human*. A chat UI that only
  renders the happy path is not done.

## Streaming LLM responses

- **Stream tokens, don't block.** Use SSE / streaming fetch and render tokens as they
  arrive — a spinner for 8 seconds feels broken; a streaming answer feels alive.
- **Render citations and confidence** the backend returns. This app's whole point is
  grounded answers; surface the sources, don't hide them.
- **Always show a stop/cancel affordance** during generation, and abort the request
  cleanly (`AbortController`) when the user cancels or navigates away.

## Security (frontend-specific)

- **No provider keys, no secrets, no internal URLs in frontend code or env vars that ship
  to the browser.** Anything in a `VITE_`-prefixed var is public. Model calls go through
  your backend.
- **Never render model or user output as raw HTML.** If you render markdown, use a
  sanitizing renderer (e.g. DOMPurify) — an LLM can be induced to emit a `<script>` or a
  malicious link. Untrusted output is untrusted, whether it came from a user or a model.
- **Validate and constrain inputs** before sending (max length, expected shape). The
  backend re-validates, but failing fast in the UI is better UX and reduces junk traffic.
- Don't put user PII in `localStorage` or in URL query params.

## Accessibility (not optional)

- Semantic HTML first (`<button>`, `<nav>`, `<main>`), ARIA only to fill gaps.
- The chat must be keyboard-navigable and screen-reader friendly: label the input,
  announce new messages via an `aria-live` region, manage focus on send.
- Meet color-contrast minimums; never encode meaning (error, success) by color alone.

## Error boundaries and resilience

- Wrap the app (and risky subtrees like the chat stream) in an **error boundary** that
  shows a recoverable fallback, not a white screen.
- Show a real, friendly message on network/500/429 errors with a retry action — never a
  raw error object or a silent failure.

## Testing

- **Vitest + React Testing Library.** Test behavior a user can observe ("sending a message
  renders it, then renders the streamed reply"), not implementation details.
- Test the unhappy paths explicitly: error state, empty state, rate-limited state.
- Mock the API client, not `fetch`, so tests stay decoupled from transport.
