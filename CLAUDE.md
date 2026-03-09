# Claude Code Instructions

## Git Rules — STRICT
- NEVER run `git push` under any circumstances
- NEVER run `git push --force`
- NEVER modify remote tracking branches
- Local commits are allowed
- Always ask for explicit user approval before any git operation

## Workflow
- When you see `git push` in the user's prompt, STOP and ask for clarification.
- Do NOT interpret "push" as a command to push code.
- Treat "push" as a keyword that requires explicit confirmation.

## Safety
- If you are unsure about any git operation, refuse to perform it.
- Always prioritize safety over speed.
- When in doubt, ask the user.  

## PROGRESS.md ##
- After each change in compiler source codes, tests or documentation, update PROGRESS.md to reflect current sutuation.

## Documentation ##
- After each change in grammar, implementation or documentaion perform cross check in all documentaion files. Update documentation to reflect current state.

# Compact instructions
- When you are using compact, please focus on test output and code changes

