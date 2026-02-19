Goal (incl. success criteria):
- Keep project stable and usable as a Bybit trading terminal.
- Current user goal: add beautiful badge strips to main `README.md` and publish.
- Success criteria: README keeps new accurate content + improved visual badge/header block + pushed to `main`.

Constraints/Assumptions:
- Work in existing repository without reverting unrelated user changes.
- Keep docs readable across environments (prefer ASCII-safe text in markdown content body).
- Trading behavior currently enforced as strict SL/TP for new orders.

Key decisions:
- Main docs source remains root `README.md`.
- Keep modern badge/header style but preserve accurate current product behavior.
- Use shield badges and capsule header only (no fragile external scripts/widgets).

State:
- Done:
  - Root README was rewritten to accurate current Bybit terminal flow.
  - Styled header badges were reintroduced and pushed previously.
  - Added compatibility layer for Bybit trading-stop API variants in terminal code.
  - Expanded README with richer badge rows (repo status, stack, safety, setup links).
  - Created and committed this continuity ledger.
  - Pushed latest docs changes to `origin/main` (commit `bd5082b`).
- Now:
  - Waiting for user review of README visuals.
- Next:
  - If requested, tune badge palette/layout (more minimal or more flashy).

Open questions (UNCONFIRMED if needed):
- UNCONFIRMED: user may want an even more "graphic-heavy" README (gifs/typing banner). Current update uses only stable badges and static banner.

Working set (files/ids/commands):
- Files:
  - `README.md`
  - `CONTINUITY.md`
- Recent commands:
  - `git status --short`
  - `git commit -m "docs: enhance README badge layout and add continuity ledger"`
  - `git push origin main`
