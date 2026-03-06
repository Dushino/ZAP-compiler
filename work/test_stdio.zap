; test_stdio.zap
; working area for testing random parts of stdio.zap

.ifndef ATARI
    .define ATARI
.endif

.include "lib/stdio.zap"
.include "lib/types.zap"
.include "lib/atari/atari_gtia.zap"

proc main()

    byte ch
    byte ^ptr

    COLOR4 = COLOR_MEDIUM_BLUE + 4

    puts("01234567890\n")    
    printb(123) ; proc printb(byte arg, const byte lzero=0, const byte zeroes=0)
    puts("\n")    
    printb(12) ; proc printb(byte arg, const byte lzero=0, const byte zeroes=0)
    puts("\n")    
    printb(1) ; proc printb(byte arg, const byte lzero=0, const byte zeroes=0)
    puts("\n")    
    printb(123,0) ; proc printb(byte arg, const byte lzero=0, const byte zeroes=0)
    puts("\n")    
    printb(12,0) ; proc printb(byte arg, const byte lzero=0, const byte zeroes=0)
    puts("\n")    
    printb(1,0) ; proc printb(byte arg, const byte lzero=0, const byte zeroes=0)
    puts("\n")    
    printb(123,0, 0) ; proc printb(byte arg, const byte lzero=0, const byte zeroes=0)
    puts("\n")    
    printb(12,0, 0) ; proc printb(byte arg, const byte lzero=0, const byte zeroes=0)
    puts("\n")    
    printb(1,0, 0) ; proc printb(byte arg, const byte lzero=0, const byte zeroes=0)
    puts("\n")    
    
    find_free_IOCB()
    
    ; COLOR4 = COLOR_MEDIUM_GREEN + 4
end

; EOF
