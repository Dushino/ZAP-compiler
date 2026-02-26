CLAUDE.md
# Claude Code Instructions

## Git Rules — STRICT
- NEVER run `git push` under any circumstances
- NEVER run `git push --force`
- NEVER modify remote tracking branches
- Local commits are allowed
- Always ask for explicit user approval before any git operation




Prompt 0:
This is a Python transpiler from ZAP! language to 6502/65c02 assembly using ca65. 
Read the entire codebase, documentation in DOC directory and tests to summarize: the overall architecture, how types are represented, how operators are processed, and how code generation works. 
After each significant change, update PROGRESS.md with what was done, what remains, and any known issues.
Do not change anything yet.


Prompt 1:
Intention is: ################
Find ALL places in the codebase where ############### is. List ALL combinations of data types BYTE, WORD, LONG, pointer and STRUCT and ENUM types, all arithmetic operators +, -, , /, all bitwise operators &, |, ^, ~, all logical operators !, &&, ||, all comparison operators <, >, =, <=, >=, address operator @.
Present this as a table. Do not change anything yet.


Promp 2:
Based on your audit, propose a complete fix plan: what files will be changed, what logic will be added, and in what order. 
Identify if any changes depend on each other. Wait for my approval before making any changes.


Prompt 3:
Fix ############# support completely and consistently across ALL operators: arithmetic (+, -, , /), 
logical (AND, OR, NOT), and comparison (<, >, =, <=, >=). 
Every operator must support BYTE, WORD, LONG, pointer and STRUCT and ENUM types.
Put all your temporary tests into generated_tests directory.
Do not move on to the next step until the current one is fully fixed and tested.


Prompt 4:
For each fix, write a minimal test case in the existing test style in tests/pass that verifies it works for all supported 
data types, all operators and all combinations of operators and datatypes. All tests must pass before you consider the task complete.


Prompt 5:
List every change you made, which files were modified, what was the root cause of each bug, and whether any similar issues may still exist elsewhere in the codebase.


Prompt 6:
Update user facing documentation files in DOC folder. Update ARCHITECTURE.md and PROGRESS.md to match current state.

