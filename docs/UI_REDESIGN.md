# Workspace UI redesign

The interface adapts the supplied visual references: a quiet gray canvas, inset white navigation and header panels, rounded cards, large restrained typography, pill controls, and a warm orange accent. The dashboard adds a deep green feature panel and a small index-health ring. The ring uses the actual ready/total document counts; it does not represent retrieval quality or provider availability.

All seven pages share the same design tokens in `frontend/src/app/globals.css`: overview, knowledge base, assistant, retrieval playground, evaluation lab, settings, and sign-in. The implementation keeps Next.js App Router, Tailwind v4, owned shadcn-style Button/Dialog components, Radix focus handling, TanStack Query, Zod, and Recharts. No new runtime dependencies, backend routes, model behavior, authentication, or database schema were introduced for the redesign.

Navigation groups primary work and technical exploration. The header's page finder opens with Cmd+K or Ctrl+K, filters existing pages, and supports native keyboard navigation, Escape, and focus restoration. It searches navigation only, not document contents. Document search remains in the knowledge base and retrieval playground. A mobile navigation dialog replaces the sidebar below 1024px.

Document upload, progress, page-local filename/status filters, chunk inspection, and confirmed deletion retain the existing API contracts. Chat keeps its bounded session-only history, source links, quotes, usage/timing fields, and safe text rendering. Search scores and evaluation artifacts retain their original semantics. Reranking stays disabled when the backend reports it unavailable. Example questions are editable suggestions, not fabricated answers.

Shared tokens cover light and dark themes, semantic success/error states, focus rings, loading shimmer, subtle transitions, responsive table scrolling, and reduced-motion support. System typography avoids external font requests. The main light-theme orange was darkened for readable small labels and white button text. This is not a claim of a complete WCAG audit.

## Executed checks

```sh
cd frontend
npm run build
# Run typecheck after build; both touch generated .next types.
npm run typecheck
npm run lint
npm test
npm run format:check
npm run check:client
cd ..
.venv/bin/python scripts/demo_frontend.py
```

- Production build: passed, all application pages generated.
- TypeScript, ESLint, Prettier: passed.
- Vitest: 30 passed, five files.
- Playwright: five passed. Real browser -> Next BFF -> FastAPI -> PostgreSQL/pgvector, with deterministic embedding/answer fixtures and a temporary isolated tenant. Covers upload, chunk inspection, hybrid search, validated citation/source panel, abstention, evaluation, deletion, unauthorized access, origin checks, index-health counts, page-finder keyboard/filter/navigation behavior, dark mode, and mobile-dialog focus restoration.
- Responsive browser assertions: all six workspace routes at 390, 768, and 1440px without document-level horizontal overflow. Tables intentionally scroll inside their cards.
- Client-boundary scan: passed across 34 browser JavaScript assets; not a comprehensive security audit.
- Live workspace visual review: six uploaded documents and seven chunks displayed correctly. Review did not alter those records or call paid AI providers. Backend readiness remained HTTP 200 after testing.

The first concurrent typecheck/build attempt raced while Next regenerated its type files. Running the final build and typecheck sequentially passed. Visual review also identified an absolutely positioned accessibility label escaping a narrow table's scroll container; making that container positioned fixed the document-level overflow.

Screenshots under `docs/screenshots/` come from the isolated fixture integration run with reduced motion, so captures show settled panels rather than intermediate entrance-animation frames. Actual development-workspace captures remain under `/tmp/eke-redesign/` and are not included in the repository. `frontend/scripts/review-design.mjs` can capture a running operator-authorized workspace using a process-only `DEMO_PASSWORD`; never publish private document screenshots without review.

## Limits

Browser automation was run in Chromium, not Safari or Firefox. Backend AI quality was not re-evaluated. The previously observed rejection of some multi-document generated quotations remains a backend limitation: the UI shows the safe error, and source validation is not bypassed. The shared demo session is still not a multi-user SaaS identity system. No GitHub push or deployment was performed.


## Focused chat reference update

The assistant now follows the separately supplied chat screenshot: an icon navigation rail, soft gray frame, white canvas with a subtle warm tint, centered welcome heading, an original inline SVG companion, a wide bottom composer, and prompt chips. Dark theme and small-screen navigation retain the same functions. The chat now inherits the same warm orange accent, gray canvas, white surfaces, neutral text, and dark-mode tokens as the rest of the workspace. Its illustration uses those tokens too.

The model badge reports the server-configured model, not a browser-selectable model. “Add documents” and “Manage documents” open the existing knowledge-base upload flow. Conversation context is the existing optional bounded request history; hybrid retrieval is the actual backend mode. Source details open automatically for cited answers, can be toggled, and retain original metadata and supporting quotes. Unsupported image generation, voice input, research modes, paid plans, and fabricated chat histories are omitted.

The five browser integration tests include a dedicated test for suggested-question insertion/focus, context toggling, source-panel open/close, empty send state, new-conversation reset, and the upload-page link. The existing real browser/BFF/SQL workflow still verifies a supported cited fixture answer and abstention. Vitest remains 30 passing tests; build, typecheck, lint, formatting, and client-boundary checks pass. Live visual checks cover 390, 768, and 1440px, dark theme, prompt insertion, and panel toggling without paid model calls or document changes. These checks do not change the previously documented model-quality limitations.

The three `assistant-welcome-*.png` files show the executed live welcome screen: no private documents or answers are present. `assistant-desktop.png` remains an isolated scripted-answer integration capture. `frontend/scripts/review-chat.mjs` produces the read-only welcome-screen checks using a process-only demo password.
