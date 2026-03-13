; Test: Phase 4 struct base address memoization
; arr[idx].field accessed multiple times across branches and JSR — address
; must be computed only once and reused from the proc-local memo slot.

struct Vec
    byte x
    byte y
end

; 8 Vec elements: 16 bytes total
Vec vecs[8] @$9C40

proc helper()
end

proc main()
    byte i = 3

    ; Access 1: first use — computes & saves to SBM slot
    vecs[i].x = 10

    ; Access 2: across a branch (if) — Phase 4 memo hit, no recompute
    if vecs[i].y == 0
        vecs[i].y = 20
    end

    ; Access 3: after JSR call — Phase 4 memo still valid (local var survives JSR)
    helper()
    vecs[i].x = vecs[i].x + 1

    ; Access 4: change i — memo must be invalidated; next access recomputes
    i = 5
    vecs[i].x = 50
    vecs[i].y = 60
end
