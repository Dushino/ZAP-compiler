; Regression test: compound assignment through pointer dereference (wptr^+=, lptr^+=).
;
; Checks:
;   1: wptr^ += 50   — wval = 100+50 = 150
;   2: wptr^ *= 2    — wval = 150*2 = 300
;   3: lptr^ += 5000 — lval = 1000+5000 = 6000
;   4: lptr^ *= 3    — lval = 6000*3 = 18000
;
; result @$0200 — expected = 4

byte result @$0200 = 0

word wval = 100
long lval = 1000

proc main()
    word ^wptr = @wval
    long ^lptr = @lval

    ; 1
    wptr^ += 50
    if wval == 150
        result = result + 1
    end

    ; 2
    wptr^ *= 2
    if wval == 300
        result = result + 1
    end

    ; 3
    lptr^ += 5000
    if lval == 6000
        result = result + 1
    end

    ; 4
    lptr^ *= 3
    if lval == 18000
        result = result + 1
    end
end
