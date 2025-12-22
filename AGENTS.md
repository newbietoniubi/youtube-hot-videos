## 1) Branching & Git Workflow

### Branch policy
- For small changes (docs, typos, comments): commit directly to `main`
- For larger features/fixes: optionally use short-lived branches:
  - `feat/<topic>` (new feature)
  - `fix/<topic>` (bug fix)
  - `chore/<topic>` (refactor, tooling, deps)
- Merge branches locally, no PR required (personal project)
- Delete branch after merge: `git branch -d <branch>`

### Commit policy
- Use Conventional Commits:
  - `feat: ...`
  - `fix: ...`
  - `chore: ...`
  - `refactor: ...`
  - `test: ...`
- Each commit must be **independently revertible** (avoid mixing unrelated changes)
- Prefer small commits over one huge commit

### Git suggestion policy
- After completing code changes, provide suggested `git add` and `git commit` commands
- Include appropriate conventional commit message
- Do NOT run these commands automatically; let user execute after testing

### Testing policy
- After modifying backend Python code, run `pytest` and report results
- If tests fail, fix the issue before completing the task