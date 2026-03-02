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

byte KBHIT @764
byte TIMER @20

const byte ATARI_KEY_RETURN         = $9B
const byte ATARI_KEY_LEFT           = $1E
const byte ATARI_KEY_RIGHT          = $1F
const byte ATARI_KEY_UP             = $1C
const byte ATARI_KEY_DOWN           = $1D
const byte ATARI_KEY_CTRL_LEFT      = $2B
const byte ATARI_KEY_CTRL_RIGHT     = $2A
const byte ATARI_KEY_CTRL_UP        = $2D
const byte ATARI_KEY_CTRL_DOWN      = $3D
const byte ATARI_KEY_HOME           = $7D
const byte ATARI_KEY_DELETE         = $FE
const byte ATARI_KEY_INSERT         = $FF
const byte ATARI_KEY_BACKSPACE      = $7E
const byte ATARI_KEY_ESCAPE         = $1B


byte kbcode @$D209
byte scr1 @40000


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

    cur_xpos = 0
    cur_ypos = 0    
    curptr = vlstart[0]
    
    memset(vlstart[0], 0, SCREEN_X_SIZE * SCREEN_Y_SIZE)   
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
    delay - wait for a specified time
*/
proc delay(byte delay)
    
    TIMER = 0
    while TIMER < delay
    end
end


/*
    cursor_on - turn on cursor
*/
proc cursor_on()
    curptr^ = curptr^ | $80    
end


/*
    cursor_off - turn off cursor
*/
proc cursor_off()
    curptr^ = curptr^ & $7F    
end


/*
    getcblink - wait for keyboard key press and return ATASCII code
    blinking cursor
*/
func byte getcblink() 
    byte i

    KBHIT = 255
    while BOOL.TRUE
        ; cursor on
        cursor_on()
        i = 0
        while i < 4
            delay(5)
            if KBHIT != 255
                cursor_off()
                return getchar()
            end
            i = i + 1   
        end

        ; cursor off
        cursor_off()
        i = 0
        while i < 4
            delay(5)
            if KBHIT != 255
                return getchar()                
            end
            i = i + 1   
        end
    end
    return getchar()
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
        ; clear last line
        memset(vlstart[SCREEN_Y_SIZE - 1], 0, SCREEN_X_SIZE)
    end
    curptr = vlstart[cur_ypos]
end


/*
    Convert ASCII to screen code
*/
func byte ascii_to_screen(byte ch)
    ; convert ATASCII to screen code, handle inverse bit
    asm
                    lda _ASCII_TO_SCREEN_CH
                    asl a               ; shift out the inverse bit
                    adc #$c0            ; grab the inverse bit; convert ATASCII to screen code
                    bpl ascii_to_screen_codeok        ; screen code ok?
                    eor #$40            ; needs correction
ascii_to_screen_codeok:     lsr a               ; undo the shift
                    bcc ascii_to_screen_sputc
                    eor #$80            ; restore the inverse bit            
ascii_to_screen_sputc:
                    sta _ASCII_TO_SCREEN_CH
    end

    return ch
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

    curptr^ = ascii_to_screen(ch)
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
    putbkspc - print backspace to the screen
*/
proc putbkspc()

    if cur_xpos > 0
        cur_xpos = cur_xpos - 1                    
        curptr = curptr - 1
        curptr^ = 0
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
    gotoxy - move cursor to the specified position
*/
proc gotoxy(byte x, byte y)
    cur_xpos = x
    cur_ypos = y
    curptr = vlstart[cur_ypos] + cur_xpos
end



/*
    gets - read characters from keyboard until newline or ESC, store them in buffer
    return: keycode    
*/
func byte gets(const byte ^buffer, const byte max_len)
    byte  ch             ; read character
    byte  pos = 0        ; buffer position
    byte ^bufp           ; current character pointer in buffer
    

    ; read characters from keyboard until newline
    bufp = buffer
    while BOOL.TRUE
        ch = getcblink()

        switch ch

            case ATARI_KEY_RETURN
            case ATARI_KEY_ESCAPE
            case ATARI_KEY_UP
            case ATARI_KEY_DOWN
                COLOR4 = COLOR_MEDIUM_GREEN + 14                
                return ch

            case ATARI_KEY_BACKSPACE
                ; TODO: test
                ; 0123456789
                ; pos = 5, cur_xpos = 5, bufp points to '5'
                ; max_len = 10
                if pos > 0
                    ; screen
                    cur_xpos = cur_xpos - 1
                    curptr = curptr - 1                    
                    memcpy(curptr, curptr + 1, max_len - pos - 1)   ; shift the rest of the line left
                    curptr[max_len - 1] = 1
                    ; buffer
                    bufp = bufp - 1
                    pos = pos - 1
                    memcpy(bufp, bufp + 1, max_len - pos - 1)   ; shift the rest of the buffer left
                end
                break

            case ATARI_KEY_DELETE
                ; TODO: implement delete
                break
            
            case ATARI_KEY_LEFT
                if pos > 0
                    ; screen
                    cur_xpos = cur_xpos - 1
                    curptr = curptr - 1                    
                    ; buffer
                    bufp = bufp - 1
                    pos = pos - 1
                end
                break

            case ATARI_KEY_RIGHT
                if (cur_xpos < SCREEN_X_SIZE - 1) && (pos < max_len - 1)
                    ; screen
                    cur_xpos = cur_xpos + 1
                    curptr = curptr + 1                    
                    ; buffer
                    bufp = bufp + 1
                    pos = pos + 1
                end
                break

            default
                if pos == max_len
                    ; screen
                    curptr^ = ascii_to_screen(ch)

                    ; buffer
                    bufp^ = ch                
                else
                    ; screen
                    putchar(ch)   ; echo the character back to the screen
                    ; buffer
                    bufp^ = ch                
                    bufp = bufp + 1
                    pos = pos + 1
                end
                break                
        end
    end

    return 0
end


/*
    set FD error code
*/
proc set_fderror(FILE^ file, byte error_code) #NOEXPORT
    ;if file != NULL
    ;    file^.error = error_code
    ;end
end


/*
    fopen - open file
*/
func byte fopen(FILE^ fd, byte^ filename, byte mode)
    
    fd = NULL

    ; TODO: implement file opening  
    ;if fd == NULL        
    ;    return 0
    ;end
    
    set_fderror(fd, ERRNO.ENODEV)
    
    return 0
end


/*
    fclose - close file
*/
func ERRNO fclose(FILE^ fd)
    ; TODO: implement file closing  
    ;if fd == NULL
    ;    return ERRNO.EBADF
   ; end
    set_fderror(fd, ERRNO.ENODEV)
    return fd^.error
end


/*
    ferror - check for error
*/
func ERRNO ferror(FILE^ fd)
    ; TODO: implement error checking  
    ;if fd == NULL
    ;    return ERRNO.EBADF
    ;end 
    set_fderror(fd, ERRNO.ENODEV)
    return fd^.error
end


/*
    feof - check for end of file
*/
func BOOL feof(FILE^ fd)
    ; TODO: implement end of file checking  
    ;if fd == NULL
    ;    return BOOL.TRUE
    ;end     
    
    set_fderror(fd, ERRNO.ENODEV)
    fd^.eof = BOOL.TRUE
    return BOOL.TRUE
end


/*
    rename - rename file
*/
func ERRNO rename(FILE^ fd, const byte ^oldname, const byte ^newname)
    ; TODO: implement file renaming  
    ;if fd == NULL
    ;    return ERRNO.EBADF
    ;end 
    set_fderror(fd, ERRNO.ENODEV)
    return fd^.error
end


/*
    remove - remove file
*/
func ERRNO remove(byte^ filename)
    ; TODO: implement file removal  
    ;if filename == NULL
    ;    return ERRNO.EBADF
    ;end 
    
    return ERRNO.ENODEV
end


/*
    fseek - seek in file
*/
func ERRNO fseek(FILE^ fd, long offset, byte whence)
    ; TODO: implement file seeking  
    ;if fd == NULL
    ;    return ERRNO.EBADF
    ;end
    set_fderror(fd, ERRNO.ENODEV)
    return fd^.error
end


/*
    ftell - tell file position
*/
func long ftell(FILE^ fd)
    ; TODO: implement file position telling  
    ;if fd == NULL
    ;    return 0
    ;end 
    return 0
end


/*
    fread - read from file
*/
func word fread(FILE^ fd, byte ^buffer, word size, word count)
    ; TODO: implement file reading  
    ;if fd == NULL
    ;    return 0
    ;end 
    return 0
end


/*
    fwrite - write to file
*/
func word fwrite(FILE^ fd, byte ^buffer, word size, word count)
    ; TODO: implement file writing  
    ;if fd == NULL
    ;    return 0
    ;end 
    return 0
end


/*
    fgetc - get character from file
*/
func byte fgetc(FILE^ fd)
    ; TODO: implement file reading  
    ;if fd == NULL        
    ;    return 0
    ;end 
    set_fderror(fd, ERRNO.ENODEV)
    return 0
end


/*
    fputc - put character to file
*/
func byte fputc(FILE^ fd, byte ch)
    ; TODO: implement file writing  
    ;if fd == NULL
    ;    return 0
    ;end 
    set_fderror(fd, ERRNO.ENODEV)
    return 0
end


/*
    fprintf - print formatted string to file
*/
func byte fprintf(FILE^ fd, const byte ^format, word arg1 = 0, 
                word arg2 = 0, word arg3 = 0, word arg4 = 0, word arg5 = 0, word arg6 = 0, word arg7 = 0, word arg8 = 0)    
    ; TODO: implement file writing  
    ;if fd == NULL
    ;    return 0
    ;end 
    set_fderror(fd, ERRNO.ENODEV)
    return 0
end


/*
    fputs - put string to file
*/
func byte fputs(FILE^ fd, const byte ^str)
    ; TODO: implement file writing  
    ;if fd == NULL
    ;    return 0    
    ;end 
    set_fderror(fd, ERRNO.ENODEV)
    return 0    
end


/*
    fscanf - read formatted string from file
*/
func byte fscanf(FILE^ fd, const byte ^format, word arg1 = 0, 
                word arg2 = 0, word arg3 = 0, word arg4 = 0, word arg5 = 0, word arg6 = 0, word arg7 = 0, word arg8 = 0)    
    ; TODO: implement file reading  
    ;if fd == NULL
    ;    return 0
    ;end 
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
