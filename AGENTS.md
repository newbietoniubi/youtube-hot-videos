## 1) Branching & Git Workflow

### Branch policy
- **Never commit directly to `main`.**
- Create a short-lived branch per task:
  - `feat/<topic>` (new feature)
  - `fix/<topic>` (bug fix)
  - `chore/<topic>` (refactor, tooling, deps)

Examples:
- `feat/generation-queue`
- `feat/stripe-subscription`
- `fix/job-status-stuck`
- `chore/add-observability`

### Commit policy
- Use Conventional Commits:
  - `feat: ...`
  - `fix: ...`
  - `chore: ...`
  - `refactor: ...`
  - `test: ...`
- Each commit must be **independently revertible** (avoid mixing unrelated changes).
- Prefer small commits over one huge commit.

### Pull request policy
- Every branch merges via PR.
- PR must include:
  - Summary of changes
  - How to test
  - Risk areas / rollout notes (if applicable)
  - Screenshots for UI changes
