; atari_stdio.zap

.module "atari_stdio"
.include "../errno.zap"
.include "../types.zap"


/*
    * cls       vyčištění obrazovky
  
    * getchar	zadání jednoho znaku ze stdin
    * getc	    čtení jednoho znaku ze souboru
    * gets	    vstup ze stdin (bez formátování)
    * putchar	výstup jednoho znaku do stdout
    * puts	    výstup řetězce do stdout
    * fopen	    otevření souboru
    * fclose	zavření souboru
    * ferror	při chybě program vrací, že návratová hodnota se nerovná 0
    * feof	    kontrola, zda byl dosažen EOF (End-Of-File) souboru
    * rename	přejmenování souboru
    * remove	mazání souboru
    * fseek	    pohybování kurzorem v souboru
    * ftell	    zjištění aktuální pozice kurzoru v souboru
    * fread	    čtení dat ze souboru
    * fwrite	zápis dat do souboru
    * fgetc     čtení jednoho znaku ze souboru
    * fputc     zápis jednoho znaku do souboru
    * fgets	    čtení řádku ze souboru
    * fprintf	zápis formátovaného řetězce do souboru
    * fputs	    zápis řádku do souboru
    * fscanf	čtení formátovaného řetězce ze souboru
    * printf	výstup formátovaného řetězce do stdout
    * snprintf	zápis formátovaného řetězce do char pole (bezpečné)
    * sprintf	zápis formátovaného řetězce do char pole
    * sscanf	čtení formátovaného řetězce ze char pole
*/



byte cur_xpos, cur_ypos                     ; cursor position on the screen
const byte SCREEN_X_SIZE = 40
const byte SCREEN_Y_SIZE = 24

byte ^vlstart[SCREEN_Y_SIZE]    #noexport   ; vertical line start positions for each row of the screen
byte ^curptr                    #noexport   ; current position in the screen memory for output


; initialize internals for faster screen IO
proc CONSTRUCTOR() 
    word scrstart @88
    byte ^data
    byte i

    data = scrstart
    for i = 0 to SCREEN_Y_SIZE
        vlstart[i] = data
        data = data + SCREEN_X_SIZE   
    end
end


/*
    COMHEADER and AUTOSTRT data area
    needed by linker for proper atari .com file generation
*/
proc atari_file_data_area() #keep #noexport
    asm
        .segment "COMHEADER"
        .import __RAM_START__, __RAM_LAST__
        .word $FFFF     		; second block marker
        .word __RAM_START__		; RUN address
        .word __RAM_LAST__    	; last byte  

        .segment "AUTOSTRT"
        .import __RAM_START__, __RAM_LAST__
        .word $FFFF     		; second block marker
        .word __RAM_START__		; RUN address
        .word __RAM_LAST__    	; last byte

        .segment "CODE"        
    end
end


/*
    Fill memory with byte value
*/
proc memset(word dest, byte value, word count)
    word i
    byte ^ptr = dest

    for i = 0 to count
        ptr^ = value
        ptr = ptr + 1
    end
end


/*
    Copy memory from source to destination    
*/
proc memcpy(word dest, word src, word count)
    word i
    byte ^ptr1 = dest
    byte ^ptr2 = src

    for i = 0 to count
        ptr1^ = ptr2^
        ptr1 = ptr1 + 1
        ptr2 = ptr2 + 1
    end
end


/*
    Clear Screen and reset cursor position
*/
proc cls()
    word i
    byte ^ptr1 = vlstart[0]

    cur_xpos = 0
    cur_ypos = 0    
    curptr = vlstart[0]
    
    memset(vlstart[0], 0, SCREEN_X_SIZE * SCREEN_Y_SIZE)   ; clear color memory    
end


/*
    Wait for keyboard key press and return ATASCII code
*/
func byte getchar()
    byte ch

    asm
        LDA $e425
        PHA
        LDA $e424
        PHA
        rts        
        sta _GETCHAR_CH
    end

    return ch
end

/*
    getc	    čtení jednoho znaku ze souboru
*/
func byte getc()
    return getchar()
end


/*
    putx - print HEX BYTE value as two characters
*/
proc putx(byte value)
    const byte hex_digits[] = "0123456789ABCDEF"
    putchar(hex_digits[value >> 4])
    putchar(hex_digits[value & $0F])
end


/*
    crlf - move cursor to the beginning of the next line, scroll screen if needed
*/
proc crlf()
    cur_xpos = 0

    if cur_ypos < SCREEN_Y_SIZE - 1
        cur_ypos = cur_ypos + 1
    else
        ; scroll screen up
        memcpy(vlstart[0], vlstart[1], (SCREEN_Y_SIZE - 1) * SCREEN_X_SIZE)
        memset(vlstart[SCREEN_Y_SIZE - 1], 0, SCREEN_X_SIZE)
    end
    curptr = vlstart[cur_ypos]
end


/*
    putchar to current screen location and move cursor forward, scroll screen if needed
*/
proc putchar(byte ch)

    switch ch
        case 10         ; newline
            crlf()
            return

        case '\t'       ; tab
            repeat
                putchar(' ')
            until (cur_xpos & $03) == 0
            return
    end

    ; convert ATASCII to screen code, handle inverse bit
    asm
                    lda _PUTCHAR_CH
                    asl a               ; shift out the inverse bit
                    adc #$c0            ; grab the inverse bit; convert ATASCII to screen code
                    bpl putchar_codeok        ; screen code ok?
                    eor #$40            ; needs correction
putchar_codeok:     lsr a               ; undo the shift
                    bcc putchar_sputc
                    eor #$80            ; restore the inverse bit            
putchar_sputc:
                    sta _PUTCHAR_CH
    end

    curptr^ = ch
    curptr = curptr + 1
    
    cur_xpos = cur_xpos + 1
    if cur_xpos >= SCREEN_X_SIZE
        cur_xpos = 0

        if cur_ypos < SCREEN_Y_SIZE - 1
            cur_ypos = cur_ypos + 1
            curptr = vlstart[cur_ypos]
        else
            crlf()
        end
    end
end


/*
    puts - print null-terminated string to the screen
*/
proc puts(byte ^str)
    byte ch
    ch = str^
    while ch != 0
        putchar(ch)
        str = str + 1
        ch = str^
    end
end


/*
    gets - read characters from keyboard until newline, store them in buffer as null-terminated string
*/
func byte gets(byte ^buffer, byte max_len)
    byte ch
    byte count = 0

    ch = getchar()
    while (ch != 155) && (count < max_len - 2)
        putchar(ch)   ; echo the character back to the screen
        buffer^ = ch
        buffer = buffer + 1
        count = count + 1
        ch = getchar()
    end
    buffer^ = 0   ; null-terminate the string

    return count
end


/*
    set FD error code
*/
proc set_fderror(FILE^ file, byte error_code) #NOEXPORT
    if file != NULL
        file^.error = error_code
    end
end


/*
    fopen - open file
*/
func byte fopen(FILE^ fd, byte^ filename, byte mode)
    
    fd = NULL

    ; TODO: implement file opening  
    if fd == NULL        
        return 0
    end
    
    set_fderror(fd, ERRNO.ENODEV)
    
    return 0
end


/*
    fclose - close file
*/
func ERRNO fclose(FILE^ fd)
    ; TODO: implement file closing  
    if fd == NULL
        return ERRNO.EBADF
    end
    set_fderror(fd, ERRNO.ENODEV)
    return fd^.error
end


/*
    ferror - check for error
*/
func ERRNO ferror(FILE^ fd)
    ; TODO: implement error checking  
    if fd == NULL
        return ERRNO.EBADF
    end 
    set_fderror(fd, ERRNO.ENODEV)
    return fd^.error
end


/*
    feof - check for end of file
*/
func BOOL feof(FILE^ fd)
    ; TODO: implement end of file checking  
    if fd == NULL
        return BOOL.TRUE
    end     
    
    set_fderror(fd, ERRNO.ENODEV)
    fd^.eof = BOOL.TRUE
    return BOOL.TRUE
end


/*
    rename - rename file
*/
func ERRNO rename(FILE^ fd, const byte ^oldname, const byte ^newname)
    ; TODO: implement file renaming  
    if fd == NULL
        return ERRNO.EBADF
    end 
    set_fderror(fd, ERRNO.ENODEV)
    return fd^.error
end


/*
    remove - remove file
*/
func ERRNO remove(byte^ filename)
    ; TODO: implement file removal  
    if filename == NULL
        return ERRNO.EBADF
    end 
    
    return ERRNO.ENODEV
end


/*
    fseek - seek in file
*/
func ERRNO fseek(FILE^ fd, long offset, byte whence)
    ; TODO: implement file seeking  
    if fd == NULL
        return ERRNO.EBADF
    end
    set_fderror(fd, ERRNO.ENODEV)
    return fd^.error
end


/*
    ftell - tell file position
*/
func long ftell(FILE^ fd)
    ; TODO: implement file position telling  
    if fd == NULL
        return 0
    end 
    return 0
end


/*
    fread - read from file
*/
func word fread(FILE^ fd, byte ^buffer, word size, word count)
    ; TODO: implement file reading  
    if fd == NULL
        return 0
    end 
    return 0
end


/*
    fwrite - write to file
*/
func word fwrite(FILE^ fd, byte ^buffer, word size, word count)
    ; TODO: implement file writing  
    if fd == NULL
        return 0
    end 
    return 0
end


/*
    fgetc - get character from file
*/
func byte fgetc(FILE^ fd)
    ; TODO: implement file reading  
    if fd == NULL        
        return 0
    end 
    set_fderror(fd, ERRNO.ENODEV)
    return 0
end


/*
    fputc - put character to file
*/
func byte fputc(FILE^ fd, byte ch)
    ; TODO: implement file writing  
    if fd == NULL
        return 0
    end 
    set_fderror(fd, ERRNO.ENODEV)
    return 0
end


/*
    fprintf - print formatted string to file
*/
func byte fprintf(FILE^ fd, const byte ^format, word arg1 = 0, 
                word arg2 = 0, word arg3 = 0, word arg4 = 0, word arg5 = 0, word arg6 = 0, word arg7 = 0, word arg8 = 0)    
    ; TODO: implement file writing  
    if fd == NULL
        return 0
    end 
    set_fderror(fd, ERRNO.ENODEV)
    return 0
end


/*
    fputs - put string to file
*/
func byte fputs(FILE^ fd, const byte ^str)
    ; TODO: implement file writing  
    if fd == NULL
        return 0    
    end 
    set_fderror(fd, ERRNO.ENODEV)
    return 0    
end


/*
    fscanf - read formatted string from file
*/
func byte fscanf(FILE^ fd, const byte ^format, word arg1 = 0, 
                word arg2 = 0, word arg3 = 0, word arg4 = 0, word arg5 = 0, word arg6 = 0, word arg7 = 0, word arg8 = 0)    
    ; TODO: implement file reading  
    if fd == NULL
        return 0
    end 
    set_fderror(fd, ERRNO.ENODEV)
    return 0
end


/*
    printf - print formatted string to screen
*/
func byte printf(const byte ^format, word arg1 = 0, 
                word arg2 = 0, word arg3 = 0, word arg4 = 0, word arg5 = 0, word arg6 = 0, word arg7 = 0, word arg8 = 0)    
    return 0
end


/*
    rewind - move file cursor to the beginning of the file
*/
func ERRNO rewind(FILE^ fd)
    return fseek(fd, 0, SEEK_SET)
end


/*
    scanf - read formatted string from screen
*/
func byte scanf(const byte ^format, word arg1 = 0, 
                word arg2 = 0, word arg3 = 0, word arg4 = 0, word arg5 = 0, word arg6 = 0, word arg7 = 0, word arg8 = 0)    
    ; TODO: implement console input reading  
    return 0
end


/*
    snprintf - print formatted string to buffer
*/
func byte snprintf(byte ^buffer, word size, const byte ^format, word arg1 = 0, 
                word arg2 = 0, word arg3 = 0, word arg4 = 0, word arg5 = 0, word arg6 = 0, word arg7 = 0, word arg8 = 0)    
    ; TODO: implement buffer writing  
    return 0
end


/*
    sprintf - print formatted string to buffer
*/
func byte sprintf(byte ^buffer, const byte ^format, word arg1 = 0, 
                word arg2 = 0, word arg3 = 0, word arg4 = 0, word arg5 = 0, word arg6 = 0, word arg7 = 0, word arg8 = 0)    
    ; TODO: implement buffer writing  
    return 0
end


/*
    sscanf - read formatted string from buffer
*/
func byte sscanf(const byte ^buffer, const byte ^format, word arg1 = 0, 
                word arg2 = 0, word arg3 = 0, word arg4 = 0, word arg5 = 0, word arg6 = 0, word arg7 = 0, word arg8 = 0)    
    ; TODO: implement buffer reading  
    return 0
end


; EOF
