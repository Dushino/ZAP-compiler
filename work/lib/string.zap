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
;   proc memmove (byte^ dst, byte^ src, const word len)
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
    word i

    for i = 0 to len
        dst^ = src^
        dst += 1
        src += 1
    end
end


/*
    Copies data from one block of memory to another accounting for the possibility that the blocks of memory overlap
*/
proc memmove(byte^ dst, byte^ src, const word len)
    word i

    if dst > src
        dst += len
        src += len
        for i = 0 to len
            dst -= 1
            src -= 1        
            dst^ = src^
        end
        return    
    end

    for i = 0 to len
        dst^ = src^
        dst += 1
        src += 1
    end

end


/*
    Fill memory with byte value
*/
proc memset(byte^ dst, const byte val, const word len)
    word i

    for i = 0 to len
        dst^ = val
        dst += 1
    end
end


/*
    Appends one string to the end of another
*/
proc strncat(byte^ dst, byte^ src, byte max=255)
    byte i, m, v

    
    m = strlen(dst)    
    putx(m)
    puts(dst)

    puts("\n")
    puts(src)
    m = strlen(src)
    putx(m)
    puts("-")
    return
    

    max -= m
    dst += m
    putx(m)

    m = strlen(src)  
    putx(m)      
    
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
func byte strlen(byte ^ptr, const byte max=255)

    byte i

    for i=0 to max
        if ptr^ == 0
            return i
        end
    end

    return 0
end

; EOF
