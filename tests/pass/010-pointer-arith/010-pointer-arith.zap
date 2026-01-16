; Test pointer arithmetic with type-aware scaling
; WORD pointers should move by 2 bytes when adding 1

word arr[] = {$1111, $2222, $3333} @$5000
; word arr[] = {$1111, $2222, $3333} ; is in BSS

proc main()
    byte ^ptr
    word ^wptr
    
    ; Test BYTE pointer arithmetic
    ptr = arr
    ptr = ptr + 1
    ptr^ = $f1
    ptr = ptr - 1
    ptr^ = $f0

    
    ; Test WORD pointer arithmetic  
    wptr = arr
    wptr = wptr + 2
    wptr^ = $ccf2
    wptr = wptr - 1
    wptr^ = $aaf3
end
