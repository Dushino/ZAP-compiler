; printb / printw / printl / putxw — decimal and hex print functions
; Tests compilation of shared BCD conversion engine and all print variants

.ifndef ATARI
    .define ATARI
.endif

.include "lib/stdio.zap"
.include "lib/types.zap"


proc main()
    byte  b = 42
    word  w = 12345
    long  l = 1000000

    ; --- printb: all argument combinations ---
    printb(b)                   ; default: lzero=1, ralign=1
    printb(b, 0)                ; no leading zeros, ralign=1
    printb(b, 0, 0)             ; no leading zeros, no align
    printb(b, 1, 0)             ; leading zeros, no align
    printb(0)                   ; zero value
    printb(255)                 ; max byte
    printb(100, 0, 0)           ; exact hundreds

    ; --- printw: all argument combinations ---
    printw(w)                   ; default
    printw(w, 0)                ; no leading zeros
    printw(w, 0, 0)             ; no leading zeros, no align
    printw(w, 1, 0)             ; leading zeros, no align
    printw(0)                   ; zero
    printw(65535)               ; max word
    printw(10000, 0, 0)         ; exact ten-thousands

    ; --- printl: all argument combinations ---
    printl(l)                   ; default
    printl(l, 0)                ; no leading zeros
    printl(l, 0, 0)             ; no leading zeros, no align
    printl(l, 1, 0)             ; leading zeros, no align
    printl(0)                   ; zero
    printl(4294967295)          ; max long (if supported)

    ; --- putx / putxw ---
    putx(b)                     ; byte hex
    putxw(w)                    ; word hex
    putxw(0)                    ; zero word hex
    putxw($ABCD)                ; literal word hex

    ; --- mixed usage in expressions ---
    b = 99
    printb(b + 1, 0, 0)        ; expression as argument
    w = 1000
    printw(w + 234, 0, 0)      ; expression as argument
end
