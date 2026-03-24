; test_stdio.zap
; working area for testing random parts of stdio.zap

.ifndef ATARI
    .define ATARI
.endif

.include "lib/stdio.zap"
.include "lib/types.zap"
.include "lib/string.zap"
.include "lib/atari/atari_gtia.zap"


const byte MsgTests[] = "stdio.zap tests ------------------\n\n"
const byte MsgTest1[] = "Files:\n"
const byte Text1[] = "Hello!"
const byte FName[] = "D1:TEST.TXT"


proc prnrv(byte rv)
    putx(rv)
    puts("\n")
end


func byte test_files()
    byte rv = 0
    
    FILE fd
    byte oldname[] = "D1:TEST.TXT"
    byte newname[] = "NEWN.ABC"
    ; byte name[33]       ; 3 (device D1: ) + 14 (filename) + 1 (separator for rename) + 14 (filename) + 1 (0) = 33 
    byte buf[32]
    
    
    puts("Open:   ")    
    rv += fopen(@fd, FName, ICAX1_Mode.Write)  
    putx(rv)                
    puts("\nWrite:  ")
    rv += fwrite(@fd, Text1, strlen(Text1))
    putx(rv)    
    puts("\nClose:  ")
    fclose(@fd)
    putx(rv)    
        
    puts("\n\nOpen:   ")    
    rv += fopen(@fd, FName, ICAX1_Mode.Read)  
    putx(rv)
    puts("\nRead:   ")    
    rv += fread(@fd, buf, 5)
    putx(rv)
    putchar('-')
    buf[5] = 0
    puts(buf)
    rv += fgetc(@fd)
    putchar(rv)
    puts("\nClose:  ")
    fclose(@fd)
    putx(rv)
    

    ;puts("Rename: ")
    ;rv = rename(FName, newname)
    ;puts("Remove: ")
    ;rv = remove(FName)    

    return rv
end




proc main() 
    byte rv
    word temp1

    puts(MsgTests)

    puts(MsgTest1)
    rv = test_files()

    puts("\n\nVysledek:")
    prnrv(rv)

    temp1 = rv + 42

    COLOR4 = rv & $ff
end

; EOF
