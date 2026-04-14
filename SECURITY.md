# Security Policy

## Supported Versions

The ZAP! compiler is currently in pre-1.0 development. Only the latest released version is supported with security updates.

| Version | Supported          |
| ------- | ------------------ |
| 0.9.x   | :white_check_mark: |
| < 0.9   | :x:                |

## Reporting a Vulnerability

The ZAP! compiler is a developer tool that runs locally on a user's machine. It does not handle untrusted network input, user credentials, or sensitive data. The most likely classes of security-relevant issues are:

- Crashes or undefined behavior in the compiler itself when processing crafted input
- Path traversal or arbitrary file write via `.include` directives, `-I` paths, or output file flags
- Generated code that behaves differently from what the source describes (correctness issues that could mask malicious behavior)

If you discover a security issue, please **do not open a public GitHub issue**. Instead:

1. Open a [private security advisory](https://github.com/Dushino/ZAP-compiler/security/advisories/new) on GitHub, or
2. Contact the maintainer directly via the email listed on the maintainer's GitHub profile

Please include:

- A minimal `.zap` file or input that triggers the issue
- The exact compiler command used
- A description of the impact (what an attacker could achieve)
- Your environment (OS, ZAP! version, Python version)

You can expect an initial response within 7 days. We will work with you to confirm the issue, prepare a fix, and coordinate disclosure.

## Scope

In scope:

- The ZAP! compiler (`compiler.py` and supporting Python modules)
- The standard library (`lib/`)
- Build scripts (`Makefile`, `make.bat`, `make_dist.sh`, `make_dist.bat`)

Out of scope:

- Issues in the cc65 toolchain (report to the cc65 project)
- Issues in the Atari hardware emulator you use to run the output
- Issues that require an attacker to have already compromised your local machine
