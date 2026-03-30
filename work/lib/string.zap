; ============================================================
; Module: string
; File:   lib/string.zap
; Platform: All
; Depends:  errno, types
;
; Description:
;   C string.h-inspired memory and string manipulation routines.
;   All strings are null-terminated byte arrays.
;   Functions that scan memory accept an explicit length or max limit.
;
; Exports (functions):
;   func byte^  memchr  (byte^ ptr, const byte val, const word len)
;   func byte   memcmp  (byte^ ptr1, byte^ ptr2, const word len)
;   func byte   strlen  (byte^ ptr, const byte max=255)
;   func byte   strncmp (byte^ str1, byte^ str2, const byte max)
;   func byte^  strnchr (byte^ ptr, const byte val, const byte max)
;
; Exports (procedures):
;   proc memcpy  (byte^ dst, byte^ src, const word len)
;   proc memset  (byte^ dst, const byte val, const word len)
;   proc strncat (byte^ dst, byte^ src, const byte max)
;   proc strncpy (byte^ dst, byte^ src, const byte max)
;
; Return value convention for comparison functions:
;   0 = equal,  1 = first argument is larger,  2 = second is larger
;
; Status: Complete
; ============================================================

.module "string"

.include "errno.zap"
.include "types.zap"



/*
    Returns a pointer to the first occurrence of a value in a block of memory
*/
func byte^ memchr(byte^ ptr, const byte val, const word len)
    byte i

    for i=0 to len
        if ptr^ == val
            return ptr
        end
    end

    return NULL
end


/*
    Compares two blocks of memory to determine which one represents a larger numeric value
    returns:
        0 = the same
        1 = first is bigger
        2 = second is bigger
*/
func byte memcmp(byte^ ptr1, byte^ ptr2, const word len)
    byte a1, a2
    word i

    for i = 0 to len
        a1 = ptr1^
        a2 = ptr2^
        if a1 > a2
            return 1
        elseif a1 < a2
            return 2
        end
        ptr1 += 1
        ptr2 += 1
    end

    return 0
end


/*
    Copy memory from source to destination        
*/
proc memcpy(byte^ dst, byte^ src, const word len)
    ; Optimized overlap-safe memcpy using Y-indexed page loops.
    ; If dst > src (and regions overlap), copies backwards (high→low).
    ; Otherwise copies forwards (low→high). ~17 cycles/byte vs ~45 original.
    asm
        ; Compare dst vs src to choose direction
        lda _MEMCPY_DST+1
        cmp _MEMCPY_SRC+1
        bcc memcpy_fwd          ; dst_hi < src_hi → forward (no overlap risk)
        bne memcpy_bwd          ; dst_hi > src_hi → backward
        lda _MEMCPY_DST
        cmp _MEMCPY_SRC
        bcc memcpy_fwd          ; dst_lo < src_lo → forward
        beq memcpy_done         ; dst == src → nothing to do
        ; fall through to backward

        ; === BACKWARD COPY (dst > src): start from end ===
memcpy_bwd:
        ; Advance src and dst to point to end: ptr += len
        clc
        lda _MEMCPY_SRC
        adc _MEMCPY_LEN
        sta _MEMCPY_SRC
        lda _MEMCPY_SRC+1
        adc _MEMCPY_LEN+1
        sta _MEMCPY_SRC+1
        clc
        lda _MEMCPY_DST
        adc _MEMCPY_LEN
        sta _MEMCPY_DST
        lda _MEMCPY_DST+1
        adc _MEMCPY_LEN+1
        sta _MEMCPY_DST+1

        ; Full pages (backward)
        lda _MEMCPY_LEN+1
        beq memcpy_bwd_rem
        tax                     ; X = page counter
memcpy_bwd_page:
        dec _MEMCPY_SRC+1
        dec _MEMCPY_DST+1
        ldy #$FF
memcpy_bwd_ploop:
        lda (_MEMCPY_SRC),y
        sta (_MEMCPY_DST),y
        dey
        cpy #$FF                ; wrapped from 0 to FF?
        bne memcpy_bwd_ploop
        dex
        bne memcpy_bwd_page
memcpy_bwd_rem:
        ; Remaining bytes (backward)
        lda _MEMCPY_LEN
        beq memcpy_done
        tay                     ; Y = count (starts at len, goes down to 1)
memcpy_bwd_tail:
        dey
        lda (_MEMCPY_SRC),y
        sta (_MEMCPY_DST),y
        cpy #$00
        bne memcpy_bwd_tail
        beq memcpy_done         ; always taken

        ; === FORWARD COPY (dst <= src) ===
memcpy_fwd:
        ; Full pages (forward)
        lda _MEMCPY_LEN+1
        beq memcpy_fwd_rem      ; no full pages
        tax                     ; X = page counter
        ldy #$00
memcpy_fwd_page:
        lda (_MEMCPY_SRC),y
        sta (_MEMCPY_DST),y
        iny
        bne memcpy_fwd_page
        inc _MEMCPY_SRC+1
        inc _MEMCPY_DST+1
        dex
        bne memcpy_fwd_page
memcpy_fwd_rem:
        ; Remaining bytes (forward)
        lda _MEMCPY_LEN
        beq memcpy_done
        tax                     ; X = byte counter
        ldy #$00
memcpy_fwd_tail:
        lda (_MEMCPY_SRC),y
        sta (_MEMCPY_DST),y
        iny
        dex
        bne memcpy_fwd_tail
memcpy_done:
    end
end


/*
    Fill memory with byte value
*/
proc memset(byte^ dst, const byte val, const word len)
    ; Optimized: Y-indexed page loop for bulk fill, then remainder.
    asm
        ; full pages: len+1 >> 8 = number of complete 256-byte pages
        lda _MEMSET_LEN+1
        beq memset_remainder    ; no full pages
        tax                     ; X = page counter
        lda _MEMSET_VAL
        ldy #$00
memset_page:
        sta (_MEMSET_DST),y
        iny
        bne memset_page
        inc _MEMSET_DST+1       ; next dest page
        dex
        bne memset_page
memset_remainder:
        ; remaining bytes: len low byte
        lda _MEMSET_LEN
        beq memset_done         ; no remainder
        tax                     ; X = byte counter
        lda _MEMSET_VAL
        ldy #$00
memset_tail:
        sta (_MEMSET_DST),y
        iny
        dex
        bne memset_tail
memset_done:
    end
end


/*
    Appends one string to the end of another
*/
proc strncat(byte^ dst, byte^ src, byte max=255)
    byte i, m, v
    byte^ ptr

    m = strlen(dst)
    dst += m

    m = strlen(src)

    for i = 0 to m
        v = src^
        dst^ = v        
        if v == 0                        
            return
        end
        dst += 1
        src += 1
    end   

end


/*
    Returns a pointer to the first occurrence of a character in a string
*/
func byte^ strnchr(byte^ ptr, const byte val, const byte max)
    byte i, v

    for i=0 to max
        v = ptr^ 
        if v == 0
            return NULL
        end
        if  v == val
            return ptr
        end
    end

    return NULL
end


/*
    Compares the ASCII values of a specified number of characters in two strings to determine which string has a higher value
*/
func byte strncmp(byte^ str1, byte^ str2, const byte max)
    byte a1, a2
    byte i

    for i = 0 to max
        a1 = str1^
        a2 = str2^
        if a1 > a2
            return 1
        elseif a1 < a2
            return 2
        end
        str1 += 1
        str2 += 1
    end

    return 0
end


/*
    Copies a number of characters from one string into the memory of another string
*/
proc strncpy(byte^ dst, byte^ src, const byte max)
    byte i, v

    for i = 0 to max
        v = src^
        dst^ = v
        if v == 0
            return
        end
        dst += 1
        src += 1
    end
end


/*
    Return the length of a string
*/
func byte strlen(byte^ ptr, const byte max=255)

    byte i, val

    for i=0 to max
        val = ptr^
        if val == 0
            return i
        end
        ptr += 1
    end

    return 0
end

; EOF
