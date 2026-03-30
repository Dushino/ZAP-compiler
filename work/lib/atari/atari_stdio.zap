; ============================================================
; Module: atari_stdio
; File:   lib/atari/atari_stdio.zap
; Platform: Atari 400/800/XL/XE  (6502/65C02)
; Depends:  errno, types, string
;
; Description:
;   Complete Atari 8-bit I/O library.  Provides:
;     - Direct-mapped text-mode screen output (40x24)
;     - Keyboard input with blinking cursor and full-line editing
;     - File and device I/O via the Atari CIO subsystem (IOCB channels)
;   Critical inner loops use inline 6502 assembly for performance.
;
;   Normally included indirectly through stdio.zap when -D ATARI is
;   defined.  Can also be included directly if needed.
;
;
; Exports (screen output):
;   proc cls()                                      -- clear screen
;   proc putchar(byte ch)                           -- print one character
;   proc puts(byte^ str)                            -- print null-terminated string
;   proc crlf()                                     -- newline + scroll
;   proc gotoxy(byte x, byte y)                     -- move cursor
;   proc cursor_on()                                -- show cursor (inverse video)
;   proc cursor_off()                               -- hide cursor
;   proc putx(byte value)                           -- print byte as 2 hex digits
;   proc printb(byte arg, lzero=1, ralign=1)        -- print byte as decimal
;   func byte ascii_to_screen(byte ch)              -- ATASCII -> screen code
;
; Exports (keyboard input):
;   func byte getchar()                             -- wait for key press
;   func byte getc()                                -- alias for getchar
;   func byte getcblink()                           -- wait with blinking cursor
;   func byte gets(byte^ buf, byte max_len)         -- read edited input line
;   proc delay(byte delay)                          -- wait N vertical blanks
;
; Exports (file I/O — CIO based):
;   func byte  fopen  (FILE^ fd, byte^ filename, byte mode)   IMPLEMENTED
;   func ERRNO fclose (FILE^ fd)                              IMPLEMENTED
;   func word  fwrite (FILE^ fd, byte^ buffer, word size)     IMPLEMENTED
;   func byte  fread  (FILE^ fd, byte^ buffer, word size)     IMPLEMENTED
;   func byte  fgetc  (FILE^ fd)                              IMPLEMENTED
;   func BOOL  feof   (FILE^ fd)                              IMPLEMENTED
;   func ERRNO ferror (FILE^ fd)                              IMPLEMENTED
;   func ERRNO rename (byte^ oldname, byte^ newname)          IMPLEMENTED
;   func ERRNO remove (byte^ filename)                        IMPLEMENTED
;   func byte  fputc  (...)                                   TODO
;   func byte  fprintf(...)                                   TODO
;   func byte  fputs  (...)                                   TODO
;   func byte  fscanf (...)                                   TODO
;
; Exports (hardware / CIO):
;   struct IOCB_Block          -- CIO channel control block layout
;   IOCB_Block IOCB[8] @$0340  -- 8 CIO channels
;   enum ICCOM_COMMANDS        -- CIO command codes
;   enum ICAX1_Mode            -- file access modes (DOS 2.0)
;   byte KBHIT @764            -- keyboard status register
;   byte TIMER @20             -- vertical blank counter
;   const ATARI_KEY_*          -- ATASCII key code constants
;
; Status: Partial (screen/keyboard complete; file I/O partial; formatted I/O TODO)
; ============================================================

.module "atari_stdio"

.include "../errno.zap"
.include "../types.zap"
.include "../string.zap"
; .include "../keys.zap"


; Screen
byte cur_xpos, cur_ypos                     ; cursor position on the screen
const byte SCREEN_X_SIZE = 40
const byte SCREEN_Y_SIZE = 24
byte ^vlstart[SCREEN_Y_SIZE]    #noexport   ; vertical line start positions for each row of the screen
byte ^curptr                    #noexport   ; current position in the screen memory for output

; Keyboard
byte KBHIT @764

enum KEY
    ENTER          = $9B
    LEFT           = $1E
    RIGHT          = $1F
    UP             = $1C
    DOWN           = $1D
    CTRL_LEFT      = $2B
    CTRL_RIGHT     = $2A
    CTRL_UP        = $2D
    CTRL_DOWN      = $3D
    HOME           = $7D
    DELETE         = $FE
    INSERT         = $FF
    BACKSPACE      = $7E
    ESCAPE         = $1B
end

byte kbcode @$D209

; Timer
byte TIMER @20


; IOCB 
struct IOCB_Block
    byte ICHID      ; handler Identifier
    byte ICDNO      ; device number (disk)
    byte ICCOM      ; command
    byte ICSTA      ; status
    word ICBA       ; buffer address
    word ICPT       ; address of put byte
    word ICBL       ; buffer length
    byte ICAX1      ; auxiliary information
    byte ICAX2      ; -
    byte ICAX3      ; the remaining auxiliary
    byte ICAX4      ; bytes are rarely used
    byte ICAX5      ; -
    byte ICAX6      ; -
end


; System IOCB blocks
IOCB_Block IOCB[8] @$0340


; ICCOM command codes
enum ICCOM_COMMANDS
    ; build - in
    Open        = $03
    Close       = $0C
    GetChr      = $07
    PutChr      = $0B
    GetRec      = $05
    PutRec      = $09
    Status      = $0D
    ; DOS 2.5 commands
    Rename      = $20
    Delete      = $21    
end


; AUX1 values for fopen
enum ICAX1_Mode
    Read        = 4       ; input operation; positions file pointer to start of file.
    Directory   = 6       ; disk directory input operation.
    Write       = 8       ; output operation; positions file pointer to start of file.
    Append      = 9       ; output operation; positions file pointer to end of file.
    ReadWrite   = 12      ; input/output operation; positions file pointer to start of file.
end 


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
    cls()
end


/*
    COMHEADER and AUTOSTRT data area
    needed by linker for proper atari .com file generation
*/
proc atari_file_data_area() #keep #noexport

    asm
        .segment "COMHEADER"
        .import __RAM_START__, __BSS_LOAD__
        .word $FFFF     		; first block marker
        .word __RAM_START__		; starting address
        .word __BSS_LOAD__ - 1 	; last byte  
    end

    .ifdef AUTOSTART
    asm
        .segment "AUTOSTRT" 
        .word   $02e2, $02e3, __RAM_START__
    end
    .endif

end


/*
    Clear Screen and reset cursor position
*/
proc cls()

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
        rts         ; call keyboard handler
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
        while i < 20
            delay(1)
            if KBHIT != 255
                cursor_off()
                return getchar()
            end
            i += 1   
        end

        ; cursor off
        cursor_off()
        i = 0
        while i < 20
            delay(1)
            if KBHIT != 255
                return getchar()                
            end
            i += 1   
        end
    end
    return getchar()
end


/*
    crlf - move cursor to the beginning of the next line, scroll screen if needed
*/
proc crlf()

    cur_xpos = 0
    curptr = vlstart[cur_ypos]

    if cur_ypos < SCREEN_Y_SIZE - 1
        cur_ypos = cur_ypos + 1
        curptr = vlstart[cur_ypos] + cur_xpos
    else
        ; scroll screen up
        memcpy(vlstart[0], vlstart[1], (SCREEN_Y_SIZE - 1) * SCREEN_X_SIZE)
        ; clear last line
        memset(vlstart[SCREEN_Y_SIZE - 1], 0, SCREEN_X_SIZE)
        curptr = vlstart[SCREEN_Y_SIZE - 1] + cur_xpos
    end
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
        case '\n'       ; newline
            crlf()
            return

        case '\t'       ; tab
            repeat
                putchar(' ')
            until (cur_xpos & $03) == 3
            return

        case '\0'       ; null terminator - ignore
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
    puts - print null-terminated string to the screen
    Optimized: inlines ascii_to_screen and screen store to avoid
    per-character function call overhead (putchar + ascii_to_screen).
    Only \n is handled inline; \t and \0 are not expected in string literals.
*/
proc puts(byte ^str)
    byte ch

    ch = str^
    while ch != 0
        if ch == '\n'
            crlf()
        else
            ; inline ascii_to_screen: ATASCII -> screen code
            asm
                        lda _PUTS_CH
                        asl a
                        adc #$c0
                        bpl puts_a2s_ok
                        eor #$40
            puts_a2s_ok:
                        lsr a
                        bcc puts_a2s_store
                        eor #$80
            puts_a2s_store:
                        ldy #$00
                        sta (_CURPTR),y
            end
            curptr += 1
            cur_xpos += 1
            if cur_xpos >= SCREEN_X_SIZE
                cur_xpos = 0
                if cur_ypos < SCREEN_Y_SIZE - 1
                    cur_ypos += 1
                    curptr = vlstart[cur_ypos]
                else
                    crlf()
                end
            end
        end
        str += 1
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
    byte i, j
    byte ^tmpp

    ; read characters from keyboard until newline
    bufp = buffer
    while BOOL.TRUE
        ch = getcblink()

        switch ch

            case Key.ENTER
            case Key.ESCAPE
            case Key.UP
            case Key.DOWN
                return ch

            case Key.BACKSPACE
                if pos > 0
                    pos -= 1
                    ; screen
                    cur_xpos -= 1
                    curptr -= 1                    
                    i = pos
                    tmpp = curptr
                    while i < max_len
                        tmpp += 1
                        ch = tmpp^
                        tmpp -= 1
                        tmpp^ = ch
                        tmpp += 1
                        i += 1
                    end
                    tmpp^ = 0

                    ; buffer
                    bufp -= 1
                    i = pos
                    tmpp = bufp
                    while i < max_len
                        tmpp += 1
                        ch = tmpp^
                        tmpp -= 1
                        tmpp^ = ch
                        tmpp += 1
                        i += 1
                    end
                    tmpp^ = ' '
                end
                break

            case Key.DELETE
                if pos < max_len
                    ; screen
                    i = pos
                    tmpp = curptr
                    while i < max_len
                        tmpp += 1
                        ch = tmpp^
                        tmpp -= 1
                        tmpp^ = ch
                        tmpp += 1
                        i += 1
                    end
                    tmpp^ = 0

                    ; buffer
                    i = pos
                    tmpp = bufp
                    while i < max_len
                        tmpp += 1
                        ch = tmpp^
                        tmpp -= 1
                        tmpp^ = ch
                        tmpp += 1
                        i += 1
                    end
                    tmpp -= 1
                    tmpp^ = ' '
                end
                break
            
            case Key.LEFT
                if pos > 0
                    ; screen
                    cur_xpos -= 1
                    curptr -= 1                    
                    ; buffer
                    bufp -= 1
                    pos -= 1
                end
                break

            case Key.RIGHT
                if (cur_xpos < SCREEN_X_SIZE - 1) && (pos < max_len - 1)
                    ; screen
                    cur_xpos += 1
                    curptr += 1                    
                    ; buffer
                    bufp += 1
                    pos += 1
                end
                break

            default
                ; screen
                ; curptr^ = ascii_to_screen(ch)

                ; buffer
                bufp^ = ch                

                if pos < max_len - 1
                    ; screen
                    putchar(ch)   ; echo the character back to the screen
                    ; buffer
                    bufp^ = ch                
                    bufp += 1
                    pos += 1
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
    if file != NULL
        file^.error = error_code
    end
end


/* 
    Find free IOCB block
*/
func byte find_free_IOCB()
    byte i

    for i = 1 to 8        
        
        if IOCB[i].ICHID == 255            
            return i
        end
    end    
    return 255 ; no free IOCB found
end


/*
    CIO - call CIO handler with the specified parameters and return status
*/
func byte CIO(byte ch, byte command, word adr=0, word len = 0, byte aux1 = 0, byte aux2 = 0)
    byte rv = 0
    
    ch &= $07

    IOCB[ch].ICCOM = command
    IOCB[ch].ICBA  = adr
    IOCB[ch].ICBL  = len
    if command == ICCOM_COMMANDS.Open
        IOCB[ch].ICAX1 = aux1
        IOCB[ch].ICAX2 = aux2
        IOCB[ch].ICAX3 = 0
    end

    asm
        lda _CIO_CH
        asl
        asl
        asl
        asl        
        tax        
        jsr $E456           ; call CIO handler    
        sta _CIO_RV 
    end

    if command != ICCOM_COMMANDS.GetChr ||
            adr != 0 ||
            len != 0
        rv = IOCB[ch].ICSTA        
    end


    if rv == 1  ; remap ATARI OK to 0
        rv = 0
    end

    return rv
end


/*
    Check and set EOF flag in FILE struct
*/
proc checkeof(FILE ^fd, byte errno) #noexport

    if fd == NULL
        return
    end

    if errno == 136
        fd^.eof = BOOL.TRUE
    elseif errno == 0
        fd^.eof = BOOL.FALSE
    end
end


/*
    fopen - open file
*/
func byte fopen(FILE^ fd, byte^ filename, byte mode)    
    byte id, rv

    if fd == NULL        
        return ERRNO.EBADF
    end
    
    id = find_free_IOCB()
    if id == 255
        return ERRNO.ENODEV
    end

    fd^.fd = id
    CIO(id, ICCOM_COMMANDS.Close)    
    rv = CIO(id, ICCOM_COMMANDS.Open, filename, 0, mode, 0)

    set_fderror(fd, rv)        
    checkeof(fd, rv)

    return rv
end


/*
    fclose - close file    
*/
func ERRNO fclose(FILE^ fd)
    byte rv

    if fd == NULL        
        return ERRNO.EBADF
    end

    rv = CIO(fd^.fd, ICCOM_COMMANDS.Close)
    rv = ERRNO.OK
    set_fderror(fd, rv)

    return ERRNO.OK
end


/*
    ferror - check for error
*/
func ERRNO ferror(FILE^ fd)
    if fd == NULL
        return ERRNO.EBADF
    end 
    
    return fd^.error
end


/*
    feof - check for end of file
*/
func BOOL feof(FILE^ fd)

    if fd == NULL
        return ERRNO.EBADF
    end     
        
    return fd^.eof
end


/*
    rename - rename file    
*/
func ERRNO rename(const byte^ oldname, const byte^ newname)
    const byte max_len = 32
    byte names[max_len+1]
    byte len, rv
    byte id

    id = find_free_IOCB()
    if id == 255
        return ERRNO.EINVAL
    end
    len = strlen(oldname) + strlen(newname) + 1
    
    if len > max_len-1
        return ERRNO.ENAMETOOLONG
    end
    
    strncpy(names, oldname, max_len)
    strncat(names, ",", max_len)
    strncat(names, newname, max_len)

    CIO(id, ICCOM_COMMANDS.Close)
    rv = CIO(id, ICCOM_COMMANDS.Rename, names)

    return rv
end


/*
    remove - remove file
*/
func ERRNO remove(byte^ filename)
    byte rv
    byte id

    id = find_free_IOCB()
    if id == 255
        return ERRNO.EINVAL
    end

    CIO(id, ICCOM_COMMANDS.Close)    
    rv = CIO(id, ICCOM_COMMANDS.Delete, filename)

    return rv
end



/*
    fread - read from file
*/
func byte fread(FILE^ fd, byte ^buffer, word size)
    byte rv

    if fd == NULL        
        return ERRNO.EBADF
    end
    
    rv = CIO(fd^.fd, ICCOM_COMMANDS.GetChr, buffer, size)
    checkeof(fd, rv)
    set_fderror(fd, rv)

    return rv
end


/*
    fwrite - write to file
*/
func word fwrite(FILE^ fd, byte ^buffer, word size)
    byte rv

    if fd == NULL        
        return ERRNO.EBADF
    end
    
    rv = CIO(fd^.fd, ICCOM_COMMANDS.PutChr, buffer, size)
    checkeof(fd, rv)
    set_fderror(fd, rv)

    return rv
end


/*
    fgetc - get character from file
    For single-byte GetChr, CIO returns the character in the accumulator
    (not the status).  We read ICSTA directly for the actual status.
*/
func byte fgetc(FILE^ fd)
    byte ch
    byte rv

    if fd == NULL
        return ERRNO.EBADF
    end

    ch = CIO(fd^.fd, ICCOM_COMMANDS.GetChr)
    rv = IOCB[fd^.fd].ICSTA                ; raw Atari status (1=OK, 136=EOF)

    set_fderror(fd, rv)
    if rv == 136
        fd^.eof = BOOL.TRUE
        return 0
    end

    if rv != 1                              ; 1 = Atari OK (raw, not CIO-remapped)
        return 0
    end

    return ch
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
    printb - print 1 Byte decimal number to the screen with optional leading zeroes
*/
proc printb(byte arg, const byte lzero=1, const byte ralign=1)
    byte i, j
    byte divisor = 100
    byte buf[3] = {'0', '0', '0'}
    const byte div[4] = {100, 10, 1, 0}

    i = 0
    divisor = div[i]
    while divisor > 0 
        while arg >= divisor
            buf[i] += 1
            arg -= divisor
        end
        i += 1
        divisor = div[i]
    end

    if !lzero
        for i=0 to 3
            if buf[i] != '0'
                break
            end
        end
    else
        i = 0
    end

    if ralign
        for j = 0 to i
            putchar(' ')
        end
    end

    for j = i to 3
        putchar(buf[j])
    end

end



; EOF
