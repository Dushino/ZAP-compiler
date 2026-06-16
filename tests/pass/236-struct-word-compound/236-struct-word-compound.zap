; Regression test: struct WORD field compound assignment.
; Tests compound +=, *= on a WORD field within a struct (LONG compound was test 225).
;
; Checks:
;   1: r.x += 50  — 100+50 = 150
;   2: r.x *= 2   — 150*2 = 300
;   3: r.y -= 5   — 1000-5 = 995
;   4: r.y /= 5   — 995/5 = 199
;   5: r.x == r.y  — 300 vs 199, false (result stays same)
;
; result @$0200 — expected = 4

byte result @$0200 = 0

struct Rect
    word x
    word y
end

Rect r

proc main()
    r.x = 100
    r.y = 1000

    ; 1
    r.x += 50
    if r.x == 150
        result = result + 1
    end

    ; 2
    r.x *= 2
    if r.x == 300
        result = result + 1
    end

    ; 3
    r.y -= 5
    if r.y == 995
        result = result + 1
    end

    ; 4
    r.y /= 5
    if r.y == 199
        result = result + 1
    end
end
