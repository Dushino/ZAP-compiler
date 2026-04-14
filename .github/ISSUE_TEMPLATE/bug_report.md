---
name: Bug report
about: Report a problem with the ZAP! compiler
title: "[BUG] "
labels: bug
assignees: ''
---

## Minimal ZAP! source code

Please provide a **minimal** `.zap` file that reproduces the problem. Strip out everything unrelated.

```zap
; Paste your minimal reproducer here
proc main()
    ; ...
end
```

## Compiler command

The exact command you used (including all flags):

```
zapc -6502 -O1 bug.zap -o bug.s
```

## What happened

What did the compiler actually do? Paste the full error message, stack trace, or describe the wrong generated code.

```
<paste compiler output here>
```

## What should have happened

Describe the expected behavior or correct output.

## Environment

- **OS:** (e.g. Windows 11, Ubuntu 22.04, macOS 14)
- **ZAP! version:** (run `zapc --version`)
- **Python version** (if running from source): (run `python --version`)
- **cc65 version** (if relevant): (run `ca65 --version`)

## Additional context

- Does the bug only appear with specific flags (e.g. only with `-O1`, only with `-6502`)?
- Is this a regression from a previous version?
- Any other context that might help.

---

**Checklist before submitting:**
- [ ] My `.zap` file is minimal and self-contained
- [ ] I included the exact compiler command
- [ ] I described both what happened and what should happen
- [ ] This is one bug (not several combined)
