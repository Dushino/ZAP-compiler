# Non-ZP Pointers Analysis - Document Index

## 📋 Complete Analysis Package
Analysis of how the ZAP compiler handles pointers and solutions for supporting non-zero-page fixed-address pointers.

**Problem**: `byte ^DLIST @560` (pointer at fixed address outside zero page) isn't properly supported because the 6502's indirect addressing requires pointers to be in zero page.

---

## 📚 Documents (Read in Order)

### 1️⃣ **QUICK_REFERENCE.md** ⚡ START HERE (5 min)
- **Best for**: Getting oriented quickly
- **Contains**:
  - One-sentence problem summary
  - Quick limitations table
  - 3-phase solution overview
  - One-page implementation summary
  - Key insight breakdown
  - Test examples
  - Quick validation checklist
- **Read if**: You have 5 minutes and want the essentials

### 2️⃣ **README_NON_ZP_POINTERS.md** 📖 NAVIGATION HUB (10 min)
- **Best for**: Choosing your reading path
- **Contains**:
  - Package overview
  - Reading guides by role (PM, architect, developer, maintainer)
  - Key insights summary
  - Code change summary
  - Common Q&A
  - Implementation checklist
  - Glossary
- **Read if**: You need to decide what to read next

### 3️⃣ **NON_ZP_POINTERS_SUMMARY.md** 📝 EXECUTIVE SUMMARY (15 min)
- **Best for**: Understanding the business case and solution outline
- **Contains**:
  - The problem explained
  - Why this matters (use cases)
  - Technical breakdown (5 sections)
  - Where it fails (code locations)
  - The solution in 3 phases
  - Files to modify
  - Validation with test case
  - Impact assessment
  - Next steps
- **Read if**: You need to make decisions about implementation priority

### 4️⃣ **ANALYSIS_NON_ZP_POINTERS.md** 🔍 DETAILED ANALYSIS (45 min)
- **Best for**: Deep technical understanding
- **Contains**:
  - Problem statement with code example
  - Current architecture (5 components analyzed)
  - Root causes (3 major issues)
  - Solution architecture (5 parts detailed)
  - Implementation stages with checkpoints
  - Code change summary
  - Test case validation
  - Summary of approach
- **Read if**: You're implementing or doing thorough code review

### 5️⃣ **ARCHITECTURE_DIAGRAMS.md** 📊 VISUAL REFERENCE (30 min)
- **Best for**: Visual learners and understanding data flows
- **Contains**:
  - Memory layout comparisons (before/after)
  - Data flow diagrams (4 scenarios)
  - Dereferencing scenarios (3 cases)
  - Decision tree (can we dereference?)
  - Symbol table evolution
  - Code generation examples (3 detailed)
  - Memory allocation algorithm
  - Phase implementation roadmap
  - Test matrix
- **Read if**: You learn better with diagrams and visual examples

### 6️⃣ **IMPLEMENTATION_GUIDE.md** 💻 HANDS-ON CODING (ongoing reference)
- **Best for**: Actual implementation
- **Contains**:
  - Quick reference: code locations (file, line range)
  - Exact modifications needed for each component
  - Change complexity table
  - Phase 1 behavior specification
  - Testing strategy
  - Edge cases to handle
  - Validation checklist
  - Phase 2 preparation notes
- **Read if**: You're writing the actual code

---

## 🎯 Reading Paths by Role

### 👔 Project Manager / Decision Maker (20 min)
1. QUICK_REFERENCE.md - "Problem in One Sentence" section
2. NON_ZP_POINTERS_SUMMARY.md - "Why This Matters" section
3. QUICK_REFERENCE.md - "Summary Table"
4. Decision: Is this a priority?

### 👨‍🏫 Architect / Code Reviewer (60 min)
1. QUICK_REFERENCE.md (5 min)
2. README_NON_ZP_POINTERS.md - sections on architecture gap (5 min)
3. ANALYSIS_NON_ZP_POINTERS.md - "Current Architecture Analysis" (20 min)
4. ANALYSIS_NON_ZP_POINTERS.md - "Root Causes" (15 min)
5. ARCHITECTURE_DIAGRAMS.md - "Decision Tree" and "Symbol Table" (10 min)
6. IMPLEMENTATION_GUIDE.md - change locations (5 min)

### 👨‍💻 Developer / Implementer (120 min ongoing)
1. QUICK_REFERENCE.md (5 min)
2. ARCHITECTURE_DIAGRAMS.md - "Data Flow" and "Dereferencing" (20 min)
3. IMPLEMENTATION_GUIDE.md - "Quick Reference" (20 min)
4. Implement Phase 1 using IMPLEMENTATION_GUIDE.md (60 min)
5. Test using test cases (15 min)

### 🔧 Future Maintainer
1. Bookmark QUICK_REFERENCE.md
2. Bookmark IMPLEMENTATION_GUIDE.md
3. Refer to ARCHITECTURE_DIAGRAMS.md when debugging pointer issues
4. Check README_NON_ZP_POINTERS.md glossary for terminology

---

## 🔑 Key Concepts Map

```
Problem
  ├─ Fixed-address pointers outside zero page
  ├─ 6502 indirect addressing requires ZP
  └─ Compiler assumes all pointers in ZP

Root Causes
  ├─ Conflation of storage location with dereferenceability
  ├─ No tracking of pointer location
  └─ Codegen assumes ZP access always possible

Solution Phases
  ├─ Phase 1: Assignment support (flag + mark)
  ├─ Phase 2: Dereferencing support (copy to temp)
  └─ Phase 3: Pointer arithmetic (16-bit math)

Implementation
  ├─ symbols.py: Add pointer_in_zp flag
  ├─ codegen_expr.py: Mark and check flag
  └─ sema_expr.py: Optional validation

Testing
  ├─ Phase 1: Assignment compiles
  ├─ Phase 2: Dereferencing works
  └─ Phase 3: Math operations work
```

---

## 📊 Document Matrix

| Document | Length | Level | Focus | Code? |
|----------|--------|-------|-------|-------|
| QUICK_REFERENCE | 2 min | Beginner | Overview | ✅ Yes |
| README_NON_ZP | 10 min | Intermediate | Navigation | ⚠️ Snippets |
| NON_ZP_SUMMARY | 15 min | Intermediate | Business case | ⚠️ Examples |
| ANALYSIS | 45 min | Advanced | Deep technical | ✅ Yes |
| DIAGRAMS | 30 min | Intermediate | Visual | ✅ Charts |
| IMPLEMENTATION | Ongoing | Advanced | Hands-on | ✅ Exact |

---

## ⚙️ Implementation Roadmap

```
📖 READ DOCUMENTS (This folder)
  ├─ QUICK_REFERENCE.md (5 min)
  ├─ ARCHITECTURE_DIAGRAMS.md (30 min)
  └─ IMPLEMENTATION_GUIDE.md (reference)
        ↓
💻 IMPLEMENT PHASE 1 (2-4 hours)
  ├─ Add pointer_in_zp flag
  ├─ Mark non-ZP pointers
  ├─ Add error check
  └─ Test assignment scenario
        ↓
🧪 VALIDATE PHASE 1
  ├─ Test: 003-pointers.zap compiles
  ├─ Test: Error on dereference attempt
  ├─ Test: Assembly output correct
  └─ Test: Existing tests still pass
        ↓
💻 IMPLEMENT PHASE 2 (4-6 hours) [OPTIONAL]
  ├─ Modify _gen_deref() for temp-based access
  ├─ Handle non-ZP pointer detection
  └─ Generate temp copy code
        ↓
🧪 VALIDATE PHASE 2
  ├─ Test: Dereference non-ZP pointers
  ├─ Test: Assembly correctness
  └─ Test: Performance acceptable
```

---

## 🔍 Quick Navigation by Question

**Q: What's the problem?**
→ QUICK_REFERENCE.md "Problem in One Sentence"

**Q: Why should we care?**
→ NON_ZP_POINTERS_SUMMARY.md "Why This Matters"

**Q: How does it work now?**
→ ANALYSIS_NON_ZP_POINTERS.md "Current Architecture Analysis"

**Q: What exactly is broken?**
→ ARCHITECTURE_DIAGRAMS.md "Dereferencing: Three Scenarios"

**Q: How do we fix it?**
→ NON_ZP_POINTERS_SUMMARY.md "The Solution in 3 Phases"

**Q: Where do I make changes?**
→ IMPLEMENTATION_GUIDE.md "Quick Reference: Code Change Locations"

**Q: What code should I write?**
→ IMPLEMENTATION_GUIDE.md sections 2a-2c

**Q: How do I test it?**
→ IMPLEMENTATION_GUIDE.md "Testing Strategy"

**Q: What could go wrong?**
→ IMPLEMENTATION_GUIDE.md "Edge Cases to Handle"

**Q: Is this backward compatible?**
→ README_NON_ZP_POINTERS.md or QUICK_REFERENCE.md

---

## 📌 Files Referenced in Analysis

### Core Compiler Files Analyzed
- `symbols.py` - Symbol table and type system
- `codegen_expr.py` - Code generation for expressions
- `sema_expr.py` - Semantic type checking for expressions
- `compiler_pipeline.py` - Overall compilation orchestration

### Test Files
- `tests/pass/003-pointers.zap` - Key test case with fixed-address pointers

### Generated Files (This Analysis)
- `QUICK_REFERENCE.md` - Summary
- `README_NON_ZP_POINTERS.md` - Navigation
- `NON_ZP_POINTERS_SUMMARY.md` - Executive summary
- `ANALYSIS_NON_ZP_POINTERS.md` - Detailed analysis
- `ARCHITECTURE_DIAGRAMS.md` - Visual reference
- `IMPLEMENTATION_GUIDE.md` - Implementation details
- `ARCHITECTURE_INDEX.md` - This file

---

## ✅ Pre-Implementation Checklist

- [ ] Read QUICK_REFERENCE.md
- [ ] Read ARCHITECTURE_DIAGRAMS.md "Data Flow" section
- [ ] Understand the decision tree in ARCHITECTURE_DIAGRAMS.md
- [ ] Have IMPLEMENTATION_GUIDE.md open for reference
- [ ] Identify test cases to validate
- [ ] Plan implementation timeline
- [ ] Set up test environment

---

## 🚀 Quick Start (10 minutes)

1. Read QUICK_REFERENCE.md (5 min)
2. Look at ARCHITECTURE_DIAGRAMS.md "Example 1" (2 min)
3. Check IMPLEMENTATION_GUIDE.md for exact changes (3 min)
4. Ready to implement!

---

## 📞 Questions?

Refer to:
- **"Why" questions**: README_NON_ZP_POINTERS.md "Common Questions Answered"
- **"How" questions**: IMPLEMENTATION_GUIDE.md
- **"What" questions**: ARCHITECTURE_DIAGRAMS.md
- **"Where" questions**: IMPLEMENTATION_GUIDE.md line numbers

---

**Last Updated**: 2026-01-16  
**Status**: Analysis Complete ✅ | Ready for Implementation 🚀
**Total Documentation**: ~12,000 words across 6 documents
**Estimated Implementation Time**: 6-18 hours (3 phases)
