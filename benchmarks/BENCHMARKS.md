---
name: Atari 8-bit benchmark reference
description: Sieve of Eratosthenes benchmark results for Atari 8-bit languages, with link to comprehensive benchmark repo
type: reference
---

Atari 8-bit language benchmarks (Sieve of Eratosthenes, TEST E):
- Source: https://github.com/pedromagician/Atari800-benchmarks
- Action!: 1.52s (with SDMCTL=0)
- ZAP! before peephole opts: 1.88s (with DMA enabled, PAL)
- ZAP! after peephole opts: 1.204s (with SDMCTL=0, PAL, 2026-03-25)
- ZAP! after LSR Step 3: **0.830s** (with SDMCTL=0, PAL, -6502 -O1, 2026-03-30)
- ZAP! is ~45.4% FASTER than Action! on sieve (both SDMCTL=0)
- **Broke the 1-second barrier (0.992s), then reached 0.830s!**

Full benchmark suite (pedromagician/Atari800-benchmarks, PAL, -6502 -O1):
| Test | What | Action! | ZAP! | Winner |
|------|------|---------|------|--------|
| A | puts 500x | 10.44s | 6.76s | ZAP! +35% |
| B | assign | 0.10s | 0.08s | ZAP! +20% |
| C | increment | 0.10s | 0.06s | ZAP! +40% |
| D | arithmetic | 3.34s | 0.68s | ZAP! +80% |
| E | sieve | 1.52s | 0.82s | ZAP! +46% |
| F | screen fill | 0.52s | 0.58s | Action! +11% |
| **Total** | | **16.02s** | **8.98s** | **ZAP! +44%** |

**How to apply:** Use this benchmark as the performance baseline when evaluating codegen optimizations. The sieve is a good real-world test covering loops, array access with word index, word comparisons, and arithmetic. Both tests must use SDMCTL=0 for fair comparison.
