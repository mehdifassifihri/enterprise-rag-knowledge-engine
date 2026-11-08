# Executed frontend screenshots

Updated for the reference-inspired workspace redesign; see [UI_REDESIGN.md](../UI_REDESIGN.md).

These PNGs capture the real Phase 8 Next.js/FastAPI/PostgreSQL browser demo with synthetic documents and controlled embedding/answer providers. They are evidence of UI/data plumbing, not real semantic quality or production deployment. UUIDs and source content are synthetic fixture data; no API credentials or login password are captured.

- `dashboard-desktop.png`: actual tenant totals after one synthetic upload.
- `assistant-desktop.png`: scripted supported answer, real server-validated citation and source panel; the controlled-provider notice is visible.
- `evaluation-desktop.png`: retained measured keyword benchmark and pending semantic strategies.
- `dashboard-mobile.png`: 390px responsive layout; the document table scrolls inside its card.
- `dashboard-dark.png`: dark theme, empty state after fixture cleanup/deletion.

Reproduce with `npm run build` inside frontend, install Playwright Chromium, then run `make demo-frontend` from the root against a disposable migrated PostgreSQL database. Screenshots are first saved under ignored `frontend/test-results/`; inspect synthetic content and copy selected files here. To record live interaction, use `scripts/demo_frontend.py --interactive` and the walkthrough in [FRONTEND.md](../FRONTEND.md). Never record the temporary password or protected configuration.

- `knowledge-desktop.png`, `playground-desktop.png`, and `settings-desktop.png`: redesigned pages from the same isolated fixture run, after test-document cleanup.

- `assistant-welcome-desktop.png`, `assistant-welcome-mobile.png`, `assistant-welcome-dark.png`: the executed focused-chat welcome screen; no private documents or answers are shown and no model calls were made.


## README RAG showcase

`rag-showcase/` contains six unmodified 1440 × 1100 browser screenshots with matching README captions: document ingestion, source chunk inspection, SQL hybrid retrieval/RRF, a two-source cited answer, abstention, and the retained keyword evaluation report. `manifest.json` records the executed capture conditions. The deterministic providers and their limitations remain visible; no source content, scores, benchmark data or response states are fabricated by the screenshot script.

The first five views use the three public fictional documents under `examples/qa/`; the evaluation page reads the existing separate 34-question keyword benchmark artifacts. The model badge describes server configuration, while the visible controlled-provider banner identifies the actual fixture execution. A valid excerpt is traceability evidence, not semantic entailment.

```sh
cd frontend
npm ci
npx playwright install chromium
npm run build
cd ..
# Root .env must point to a migrated local PostgreSQL/pgvector database.
.venv/bin/python scripts/demo_frontend.py --screenshots
```

The script starts temporary services on 8018/3008, uses a fresh isolated tenant and generated process-only credentials, checks both cited quotes against persisted chunks, asserts abstention, then cleans up its own tenant and processes. It does not touch the ordinary workspace or call paid APIs. No private uploads, credentials, login values or synthetic browser traces are published. Review regenerated images before publication; fixture UUIDs and measured timings can vary.
