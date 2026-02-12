; Test pointer dereference and array subscript in expressions
; This verifies that ptr^ and arr[i] can be used in expressions (not just assignments)

byte ^bptr1
byte ^bptr2
word ^wptr1
word ^wptr2
byte barr[] = {10, 20, 30}
word warr[] = {100, 200, 300}

byte b
word w

proc main()
    ; Initialize pointers
    bptr1 = $1000
    bptr2 = $1100
    wptr1 = $1200
    wptr2 = $1300
    
    ; Byte pointer dereference in expressions
    bptr1^ = 1
    bptr2^ = 2
    wptr1^ = $a1b2
    wptr2^ = $c1d2

    b = bptr1^ + 5
    b = bptr1^ + bptr2^
    b = bptr1^ + barr[0]
    
    ; Self-modification: ptr^ = ptr^ + 1
    bptr1^ = bptr1^ + 1
    bptr1^ = bptr1^ - 1
    bptr1^ = bptr1^ + bptr2^
    
    ; Word pointer dereference in expressions
    w = wptr1^ + 10
    w = wptr1^ + wptr2^
    w = wptr1^ + warr[0]
    
    ; Self-modification for word pointers
    wptr1^ = wptr1^ + 1
    wptr1^ = wptr1^ - 1
    wptr1^ = wptr1^ + wptr2^
    
    ; Array subscript in expressions
    b = barr[0] + 1
    b = barr[0] + barr[1]
    b = barr[1] + bptr1^
    
    ; Array self-modification
    barr[0] = barr[0] + 1
    barr[0] = barr[0] + barr[1]
    barr[1] = barr[1] + bptr1^
    
    ; Word array operations
    w = warr[0] + 1
    w = warr[0] + warr[1]
    w = warr[1] + wptr1^
    
    warr[0] = warr[0] + 1
    warr[0] = warr[0] + warr[1]
    warr[1] = warr[1] + wptr1^
    
    ; Comparisons with dereferenced values
    if bptr1^ == bptr2^
        b = 1
    end
    
    if barr[0] < barr[1]
        b = 2
    end
    
    ; Logical operations
    b = !bptr1^
    if !barr[0]
        b = 3
    end
end
