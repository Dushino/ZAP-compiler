# Claude Code Instructions

## Git Rules — STRICT
- NEVER run `git push` under any circumstances
- NEVER run `git push --force`
- NEVER run `git revert` 
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

## Design ##
- Always think in more generic context. If there is a way how to make things more generic or share logic accross parts of a project, go that way. For example, if there is already working logic for allocating TMP variables, use it for MATH variables as well and check possibility to use it for local variables. In other words: Check all places where allocated variables are used and try to unify approach accross all pieces.
- If there are more copies of the same functionality, try to unify to one piece of code. This minimises design complexity and risk of missing bugs fixes in dusplicated code places.

## PROGRESS.md ##
- After each change in compiler source codes, tests or documentation, update PROGRESS.md to reflect current sutuation.

## Documentation ##
- After each change in grammar, implementation or documentaion perform cross check in all documentaion files in `DOC` folder. Update documentation to reflect current state.
- For every function / method inside the compiler provide short description in a comment before code.
- Always update memory/MEMORY.md file to keep track of changes.

## Test generated for development purposes ##
- There is dedicated folder `generated_tests` for tests created for development purposes. Use this folder for all temporary files not to mess root project folder.

## Regression tests ##
- For all new features implemented, new regression tests must be created in `tests` folder. 
- All previous tests in `./tests/pass` must pass and all tests in `./tests/fail` must fail.
- If there are some tests missing, create new ones both to `pass` and `fail` categories.
- For failed tests, check must be also done if correct error message, line and column numbers. If not correct, test is not successful.
- All tests are stored in separate numbered subdirectories.


## IDE integration ##
- After each change in grammar, implementation or documentaion perform cross check in VS Code ZAP plugin in folder `IDE_Integration`.

## Examples ##
- After each change in grammar, implementation or documentaion perform cross check in all examples in `examples` folder and documentation to reflect current state.

# Compact instructions
- When you are using compact, please focus on test output and code changes


