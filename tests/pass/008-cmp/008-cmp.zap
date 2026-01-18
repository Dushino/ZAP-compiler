; compare tests
; test_comparsions.zap

byte ^ptr = 40000   ; atari screen start with BASIC enabled

const byte chtrue = $11      ; ATASCII character for TRUE result
const byte chfalse = $10     ; ATASCII character for FALSE result

proc compare1(byte a, byte b)

    if a > b then
        ptr^ = chtrue
    else
        ptr^ = chfalse
    endif
    ptr = ptr + 1

    if a >= b then
        ptr^ = chtrue
    else
        ptr^ = chfalse
    endif
    ptr = ptr + 1

    if a == b then
        ptr^ = chtrue
    else
        ptr^ = chfalse
    endif
    ptr = ptr + 1

    if a <= b then
        ptr^ = chtrue
    else
        ptr^ = chfalse
    endif
    ptr = ptr + 1

    if a < b then
        ptr^ = chtrue
    else
        ptr^ = chfalse
    endif
    ptr = ptr + 1

    if a != b then
        ptr^ = chtrue
    else
        ptr^ = chfalse
    endif
    ptr = ptr + 2


end

; main -----------------------------------------
proc main()

    
    compare1(1,2)   ; should read 000111 - OK
    compare1(3,3)   ; should read 011100 - OK
    compare1(4,3)   ; should read 110001 - OK

end

