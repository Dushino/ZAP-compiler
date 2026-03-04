; Example: ref_11_pointers.zap
; Source: ZAP_LANGUAGE_REFERENCE.md, section "Pointers" (lines 2279-2475)
;
; Demonstrates: pointer decl, address-of, deref, arithmetic, paren deref, NULL

; --- Pointer Declaration ---
byte px = 42
byte ^bptr = @px
word ^waddr

; --- Dereferencing ---
proc deref_example()
    byte x = 42
    byte ^ptr = @x
    byte y = ptr^       ; y = 42
    ptr^ = 99           ; x = 99
end

; --- Pointer Arithmetic ---
proc pointer_arithmetic()
    byte arr[] = {10, 20, 30, 40, 50}
    byte ^ptr = @arr
    byte value = 0
    word addresses[] = {$1000, $2000, $3000}
    word ^wptr = @addresses
    word addr2 = 0
    word diff = 0

    ; BYTE pointers: +1 moves 1 byte
    ptr = ptr + 1
    value = ptr^             ; value = 20

    ; WORD pointers: +1 moves 2 bytes
    wptr = wptr + 1
    addr2 = wptr^            ; addr2 = $2000

    ; Pointer difference
    diff = wptr - @addresses ; diff = 1
end

; --- Parenthesized Pointer Dereference ---
struct Point
    byte x
    byte y
end

proc paren_deref()
    byte arr[5] = {10, 20, 30, 40, 50}
    byte ^ptr = @arr
    byte val = 0
    word warr[3] = {$1111, $2222, $3333}
    word ^wptr = @warr
    long larr[3] = {$11111111, $22222222, $33333333}
    long ^lptr = @larr
    Point pts[3] = {{1,2}, {3,4}, {5,6}}
    Point ^sptr = @pts

    ; Write to arr[2] via computed pointer
    (ptr + 2)^ = 99

    ; Read from computed pointer
    val = (ptr + 3)^         ; val = 40

    ; WORD pointer
    (wptr + 1)^ = $ABCD

    ; LONG pointer
    (lptr + 1)^ = $DEADBEEF

    ; Struct pointer
    (sptr + 1)^.x = 99

    ; Compound assignment
    (ptr + 1)^ += 5
end

; --- NULL Pointer Idiom ---
const word NULL = $0000

proc null_check()
    byte data = 10
    byte ^ptr = @data

    ; Set pointer to null
    ptr = NULL

    ; Test if pointer is null
    if ptr == NULL
        ; handle null case
    end

    ; Test if pointer is NOT null
    ptr = @data
    if ptr != NULL
        ; safe to dereference
    end
end

; --- Pointer Comparisons ---
proc pointer_compare()
    byte a = 1
    byte b = 2
    byte ^p1 = @a
    byte ^p2 = @b

    if p1 == @a
        ; pointer vs pointer
    end

    if p1 == 0
        ; pointer vs literal zero
    end
end

proc main()
    deref_example()
    pointer_arithmetic()
    paren_deref()
    null_check()
    pointer_compare()
end
