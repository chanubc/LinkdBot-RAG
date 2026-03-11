---
name: start-feature
description: Start a new LinkdBot-RAG feature by validating the feature description, creating a GitHub issue from the repo template, syncing main, creating a correctly named branch, and printing the ready-to-work summary. Use when the user wants to begin implementation work following this repository's Git workflow.
---

# Start Feature

Use this skill when the user wants to start a new feature or asks to follow the repository's feature-start workflow.

This skill is **project-local** and follows:
- `.claude/commands/start-feature.md`
- `.github/ISSUE_TEMPLATE/issue_template.md`
- `.github/PULL_REQUEST_TEMPLATE.md`
- `CLAUDE.md`

## Workflow

1. Read `.claude/commands/start-feature.md`.
2. Ensure the user has provided a concrete feature description.
   - If missing, ask for it briefly.
3. Create a GitHub issue using `.github/ISSUE_TEMPLATE/issue_template.md`.
4. Extract the created issue number `N`.
5. Update local `main`.
6. Create and checkout a branch named:
   - `prefix/#N-{english-kebab-case-description}`
   - choose the appropriate prefix such as `feat`, `fix`, `refactor`, or `chore`
7. Print:

```text
✅ 준비 완료!
📌 이슈: #{N}
🌿 브랜치: prefix/#N-{설명}

이제 작업을 시작하세요.
```

## Execution Notes

- Prefer the repository's exact issue and PR templates.
- Do not invent a different branch naming scheme.
- If GitHub CLI auth or network access blocks issue creation, report the blocker clearly and stop there.
- If the feature description is in Korean, convert the branch suffix to concise English kebab-case.
- Keep output compact.

## Commands Reference

Issue creation pattern:

```bash
gh issue create --title "[FEAT] {기능 설명}" --body "$(cat <<'EOF'
## 📌 𝗧𝗮𝘀𝗸
- [ ] {기능 설명}

## 💡 𝗥𝗲𝗳𝗲𝗿𝗲𝗻𝗰𝗲

EOF
)"
```

Main sync:

```bash
git checkout main
git pull origin main
```

Branch creation:

```bash
git checkout -b prefix/#N-{description}
```
