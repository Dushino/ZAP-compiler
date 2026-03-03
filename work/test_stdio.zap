; test_stdio.zap
; working area for testing random parts of stdio.zap

.ifndef ATARI
    .define ATARI
.endif

.include "lib/stdio.zap"
.include "lib/types.zap"
.include "lib/atari/atari_gtia.zap"


struct MyStruct
    byte a
    byte b
    byte c
end


proc main()

    byte ch
    byte ^ptr
    byte msg1[] = "1. Hello World! "        ; BSS segment
    const byte msg2[] = "2. Hello World! "  ; CODE segment
    byte inbuf[16]                          ; BSS segment

    cls()    

    COLOR4 = COLOR_MEDIUM_BLUE + 4

    puts(msg1)
    putchar('\n')    
    puts(msg2)
    putchar('\n')
    puts("3. Hello World!\n")

    ; clear input buffer
    for ch = 0 to 15
        inbuf[ch] = '-'
    end
    inbuf[15] = 0

    ch = gets(inbuf, 8)    
    puts("\n\t1\t123\t1234\t12345\t123456\n")
    putchar('>')
    puts(inbuf)
    putchar('<')
    
    ; COLOR4 = COLOR_MEDIUM_GREEN + 4
end

; EOF
