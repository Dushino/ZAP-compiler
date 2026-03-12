; test_stdio.zap
; working area for testing random parts of stdio.zap

.ifndef ATARI
    .define ATARI
.endif

.include "lib/stdio.zap"
.include "lib/types.zap"
.include "lib/string.zap"
.include "lib/atari/atari_gtia.zap"


const byte Text1[] = "Hello!"
const byte FName[] = "D1:TEST.TXT"


proc main()

    byte rv
    FILE fd
    byte oldname[] = "D1:TEST.TXT"
    byte newname[] = "NEWN.ABC"
    byte name[64]
            
    puts("Open:   ")    
    rv = fopen(@fd, FName, ICAX1_Mode.Write)  
    putx(rv)

    puts("\nWrite:  ")
    rv = fwrite(@fd, Text1, strlen(Text1))
    putx(rv)
    
    puts("\nClose:  ")
    fclose(@fd)
    putx(rv)

    ; puts("Rename: ")
    ; rv = rename(FName, newname)

    ;puts("Remove: ")
    ;rv = remove(FName)

    puts("\n\nOpen:   ")    
    rv = fopen(@fd, FName, ICAX1_Mode.Read)  
    putx(rv)

    puts("\nRead:   ")    
    rv = fread(@fd, name, 5)
    putx(rv)
    name[5] = 0
    puts(name)

    puts("\nClose:  ")
    fclose(@fd)
    putx(rv)

    COLOR4 = COLOR_MEDIUM_GREEN + 8
end

; EOF
