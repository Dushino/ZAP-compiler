; Test 170: Skipped default arguments — proc(1,,3) syntax
; Verifies that omitting an argument in a call uses its default value.
;
; Checks (result +1 each):
;  1.  proc call: skip middle arg → default used
;  2.  proc call: skip first arg → default used
;  3.  proc call: skip last arg (trailing omit)
;  4.  proc call: skip two consecutive middle args
;  5.  func call (expression context): skip middle arg → default used
;  6.  func call: skip first arg → default used
;  7.  proc call: all args provided (no skip) → still works
;  8.  proc call: all args omitted (empty call) → all defaults
;
; Expected result: 8 = $08

byte result @40000 = 0
byte out @40001 = 0

proc add3(byte a = 10, byte b = 20, byte c = 30)
    out = a + b + c
end

proc add4(byte a = 1, byte b = 2, byte c = 3, byte d = 4)
    out = a + b + c + d
end

func byte fadd(byte a = 10, byte b = 20, byte c = 30)
    return a + b + c
end

proc main()
    byte tmp

    ; --- 1: skip middle arg: add3(1,,3) → a=1, b=20(default), c=3 → 24 ---
    add3(1,,3)
    if out == 24
        result = result + 1     ; 1
    end

    ; --- 2: skip first arg: add3(,5,6) → a=10(default), b=5, c=6 → 21 ---
    add3(,5,6)
    if out == 21
        result = result + 1     ; 2
    end

    ; --- 3: skip last arg: add3(1,2) → a=1, b=2, c=30(default) → 33 ---
    add3(1,2)
    if out == 33
        result = result + 1     ; 3
    end

    ; --- 4: skip two consecutive middle: add4(1,,,4) → a=1, b=2(def), c=3(def), d=4 → 10 ---
    add4(1,,,4)
    if out == 10
        result = result + 1     ; 4
    end

    ; --- 5: func skip middle: fadd(1,,3) → 1+20+3 = 24 ---
    tmp = fadd(1,,3)
    if tmp == 24
        result = result + 1     ; 5
    end

    ; --- 6: func skip first: fadd(,5,6) → 10+5+6 = 21 ---
    tmp = fadd(,5,6)
    if tmp == 21
        result = result + 1     ; 6
    end

    ; --- 7: all provided: add3(1,2,3) → 6 ---
    add3(1,2,3)
    if out == 6
        result = result + 1     ; 7
    end

    ; --- 8: all defaults: add3() → 10+20+30 = 60 ---
    add3()
    if out == 60
        result = result + 1     ; 8
    end
end
