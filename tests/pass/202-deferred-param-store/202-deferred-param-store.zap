; Test 202: Deferred parameter store — exact fwrite/strlen pattern
; The function write_data(ptr, buf, len) has 3 memory params.
; Calling write_data(fd, text, count_bytes(text)) must not clobber
; the 'buf' param when count_bytes() walks the string (modifying its
; local pointer that shares an __LVSLOT with write_data::buf).

byte result @40000 = 0


; count_bytes: walks a pointer forward, counting non-zero bytes.
; Its parameter 'ptr' is modified in the loop body.
func byte count_bytes(byte ^ptr)
    byte count = 0
    while ptr^ != 0
        count += 1
        ptr += 1        ; modifies __LVSLOT holding 'ptr'
    end
    return count
end


; write_data: returns first byte of buf + len.  If buf was clobbered
; by count_bytes, buf^ will NOT be the first character.
func byte write_data(byte channel, byte ^buf, byte len)
    return buf^ + len
end


; sum3: three word-width params.  Tests deferred store for word args.
func word sum3(word a, word b, word c)
    return a + b + c
end

func word double(word x)
    return x + x
end


proc main()
    byte text[] = "Hello"
    byte text2[] = "AB"
    byte r
    word w

    ; --- Test 1: write_data(1, text, count_bytes(text)) ---
    ; count_bytes("Hello") = 5.  text[0] = 'H' = $48 = 72.
    ; write_data: buf^ + len = 72 + 5 = 77
    r = write_data(1, text, count_bytes(text))
    if r == 77
        result += 1     ; +1
    end

    ; --- Test 2: write_data with literal channel, different text ---
    r = write_data(2, text2, count_bytes(text2))
    ; count_bytes("AB") = 2.  text2[0] = 'A' = $41 = 65.
    ; 65 + 2 = 67
    if r == 67
        result += 1     ; +2
    end

    ; --- Test 3: sum3 with nested calls in last two args ---
    ; sum3(100, double(50), double(75))
    ; = 100 + 100 + 150 = 350
    w = sum3(100, double(50), double(75))
    if w == 350
        result += 1     ; +3
    end

    ; --- Test 4: deeply nested ---
    ; write_data(0, text, count_bytes(text) + count_bytes(text2))
    ; = 72 + (5 + 2) = 79
    r = write_data(0, text, count_bytes(text) + count_bytes(text2))
    if r == 79
        result += 1     ; +4
    end
end
