; Test 152: FOR loop — all data types, step variants, expression bounds — GAP-08
; Supplements 050-control-flow-for (byte step 1/2), 104-word-loops (word step 1),
; and 138-long-control-flow (long step 1).
;
; New territory covered here:
;   byte  — step from variable (general path), bounds from compound expression
;   word  — step constant >1, step from variable, crossing byte boundary, expr bounds
;   long  — step constant >1, step from variable, crossing word boundary, expr bounds
;   pointer as loop variable (iterating over array by address)
;   dereferenced value as end bound
;
; Checks (result +1 each):
;  1.  byte var, step from variable (s=3): for i=0 to 12 step s → 4 iters
;  2.  byte var, bounds from compound expr: for i=a+1 to b*2 (a=2,b=5) → 7 iters
;  3.  word var, step constant >1: for w=0 to 16 step 4 → 4 iters
;  4.  word var, step from variable (ws=5): for w=0 to 20 step ws → 4 iters
;  5.  word var, crosses byte boundary: for w=253 to 259 → 6 iters
;  6.  word var, bounds from expression: for w=wa+2 to wb*3 (wa=3,wb=5) → 10 iters
;  7.  long var, step constant >1: for l=0 to 15 step 3 → 5 iters
;  8.  long var, step from variable (ls=4): for l=0 to 12 step ls → 3 iters
;  9.  long var, crosses word boundary: for l=65533 to 65537 → 4 iters
; 10.  long var, bounds from expressions: for l=lbase to lbase+5 (lbase=100000) → 5 iters
; 11.  pointer as loop var: for ptr=@arr[0] to @arr[0]+4, write 1; sum==4
; 12.  deref as end bound: for i=0 to ptr^ (ptr→target=6) → 6 iters
;
; Expected result: 12 = $0C

byte result @40000 = 0

proc main()
    byte i
    byte cnt
    byte s
    byte a
    byte b
    byte target = 6
    byte sum
    byte arr[4]
    word w
    word ws
    word wa
    word wb
    long l
    long ls
    long lbase
    byte^ ptr

    ; --- 1: byte, step from variable (uses _gen_for_general path) ---
    s = 3
    cnt = 0
    for i = 0 to 12 step s      ; iters: 0,3,6,9 → 4
        cnt = cnt + 1
    end
    if cnt == 4
        result = result + 1     ; 1
    end

    ; --- 2: byte, bounds from compound expressions ---
    a = 2
    b = 5
    cnt = 0
    for i = a + 1 to b * 2     ; start=3, end=10, iters: 3..9 → 7
        cnt = cnt + 1
    end
    if cnt == 7
        result = result + 1     ; 2
    end

    ; --- 3: word, step constant > 1 ---
    cnt = 0
    for w = 0 to 16 step 4     ; iters: 0,4,8,12 → 4
        cnt = cnt + 1
    end
    if cnt == 4
        result = result + 1     ; 3
    end

    ; --- 4: word, step from variable ---
    ws = 5
    cnt = 0
    for w = 0 to 20 step ws    ; iters: 0,5,10,15 → 4
        cnt = cnt + 1
    end
    if cnt == 4
        result = result + 1     ; 4
    end

    ; --- 5: word, crosses byte boundary (255→256) ---
    cnt = 0
    for w = 253 to 259         ; iters: 253,254,255,256,257,258 → 6
        cnt = cnt + 1
    end
    if cnt == 6
        result = result + 1     ; 5
    end

    ; --- 6: word, bounds from expressions ---
    wa = 3
    wb = 5
    cnt = 0
    for w = wa + 2 to wb * 3   ; start=5, end=15, iters: 5..14 → 10
        cnt = cnt + 1
    end
    if cnt == 10
        result = result + 1     ; 6
    end

    ; --- 7: long, step constant > 1 ---
    cnt = 0
    for l = 0 to 15 step 3     ; iters: 0,3,6,9,12 → 5
        cnt = cnt + 1
    end
    if cnt == 5
        result = result + 1     ; 7
    end

    ; --- 8: long, step from variable ---
    ls = 4
    cnt = 0
    for l = 0 to 12 step ls    ; iters: 0,4,8 → 3
        cnt = cnt + 1
    end
    if cnt == 3
        result = result + 1     ; 8
    end

    ; --- 9: long, crosses word boundary (65535→65536) ---
    cnt = 0
    for l = 65533 to 65537     ; iters: 65533,65534,65535,65536 → 4
        cnt = cnt + 1
    end
    if cnt == 4
        result = result + 1     ; 9
    end

    ; --- 10: long, bounds from expressions ---
    lbase = 100000
    cnt = 0
    for l = lbase to lbase + 5 ; iters: 100000..100004 → 5
        cnt = cnt + 1
    end
    if cnt == 5
        result = result + 1     ; 10
    end

    ; --- 11: pointer as loop variable, iterate over byte array ---
    for ptr = @arr[0] to @arr[0] + 4  ; ptr visits arr[0]..arr[3] (4 addrs)
        ptr^ = 1
    end
    sum = arr[0] + arr[1] + arr[2] + arr[3]
    if sum == 4
        result = result + 1     ; 11
    end

    ; --- 12: dereferenced pointer as end bound ---
    ptr = @target               ; target = 6
    cnt = 0
    for i = 0 to ptr^          ; end = 6, iters: 0..5 → 6
        cnt = cnt + 1
    end
    if cnt == 6
        result = result + 1     ; 12
    end
end
