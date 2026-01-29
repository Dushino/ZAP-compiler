


proc init()
    word dlstart @560
    byte dlist[16] @40000

    dlstart = 40000
    dlist[0] = $70       
    dlist[1] = $70
    dlist[2] = $70 
    dlist[3] = $40 + 2      ; GR.0 + LMS
    dlist[4] = 40008 % 256  ; low byte of screen memory address
    dlist[5] = 40008 / 256  ; high byte of screen memory address
    dlist[6] = $02
    dlist[7] = $02

    dlist[8] = 'A'
    dlist[9] = 'B'
    dlist[10] = 'C'
    dlist[11] = 'D'
    dlist[12] = 'E'
    dlist[13] = 'F'
    dlist[14] = 'G'
    dlist[15] = $FF         ; end of display list
end


proc main()
    word i
    byte color_bk @712
    byte ^dlstart @560      ; system storage for DL address
    word ^dlptr             ; pointer into display list
    byte ^vram

    init()

    ;color_bk = 0            ; black background     
    ;dlptr = dlstart         ; copy display list address into ZP pointer        
    ;dlptr = dlptr + 2       ; skip first four bytes (2xWORD) of display list
    ;vram = dlptr^           ; get screen memory address from display list    
    ;vram^ = 1
end
