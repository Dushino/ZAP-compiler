; Test 201: Nested function calls in arguments
; Verifies that parameter slot sharing does not corrupt values when
; a later argument expression calls a function whose parameter shares
; the same __LVSLOT as an earlier argument's parameter.
;
; This is the exact pattern that caused the fwrite/strlen bug:
;   foo(buf, strlen(buf)) where foo::buffer and strlen::ptr share __LVSLOT_1

byte result @40000 = 0


; Helper: walk a pointer forward N bytes (modifies its local ptr parameter)
func byte walk_ptr(byte ^ptr, byte n)
    byte i
    for i = 0 to n
        ptr += 1       ; this MODIFIES the local param 'ptr' (and its __LVSLOT)
    end
    return ptr^
end


; Target: accepts a pointer and a byte computed by a nested call.
; If the pointer param was clobbered by walk_ptr's evaluation,
; it will read from the wrong address.
func byte combine(byte ^data, byte extra)
    return data^ + extra
end


; Pattern: two word-width params, second is a nested call
func word add_w(word a, word b)
    return a + b
end

func word get_val(word x)
    return x + 100
end


proc main()
    byte buf[] = {10, 20, 30, 40, 50}
    byte r
    word w

    ; --- Test 1: combine(buf, walk_ptr(buf, 3)) ---
    ; walk_ptr: for i=0 to 3 => 3 increments => ptr = buf+3 => buf[3]=40
    ; combine: data^ = buf[0] = 10, extra = 40 => 10 + 40 = 50
    r = combine(buf, walk_ptr(buf, 3))
    if r == 50
        result += 1     ; +1
    end

    ; --- Test 2: word params with nested call ---
    ; add_w(500, get_val(200)) = 500 + (200+100) = 800
    w = add_w(500, get_val(200))
    if w == 800
        result += 1     ; +2
    end

    ; --- Test 3: pointer first arg, nested call second arg ---
    ; walk_ptr: for i=0 to 1 => 1 increment => ptr = buf+1 => buf[1]=20
    ; combine: data^ = buf[0] = 10, extra = 20 => 10 + 20 = 30
    r = combine(buf, walk_ptr(buf, 1))
    if r == 30
        result += 1     ; +3
    end

    ; --- Test 4: multiple nested calls in both args ---
    ; add_w(get_val(10), get_val(20))
    ; = (10+100) + (20+100) = 110 + 120 = 230
    w = add_w(get_val(10), get_val(20))
    if w == 230
        result += 1     ; +4
    end
end
