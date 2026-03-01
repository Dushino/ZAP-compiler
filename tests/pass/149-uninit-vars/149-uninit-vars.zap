; Test 149: uninitialized variable behavior — GAP-06
; Verifies:
;   - Global uninitialized scalars (byte, word) and composites (array, struct)
;     are zero-initialized via BSS segment at program startup.
;   - Local uninitialized arrays and structs are zero on first call (BSS);
;     sema does not check arrays or structs for definite assignment.
;   - Local uninitialized scalars are rejected at compile time (covered by fail
;     tests uninit-byte-local, uninit-word-local, uninit-long-local,
;     uninit-pointer-local).
;
; Checks (result +1 each):
;  1.  g_byte == 0              (global byte, no init — BSS zeroed at startup)
;  2.  g_word == 0              (global word, no init — BSS zeroed at startup)
;  3.  g_arr[0] == 0            (global byte[4], first element — BSS)
;  4.  g_arr[3] == 0            (global byte[4], last element — BSS)
;  5.  g_pair.x == 0            (global struct field — BSS)
;  6.  g_pair.y == 0            (global struct field — BSS)
;  7.  l_arr[0] == 0            (local byte[4], first element — BSS, first call)
;  8.  l_arr[3] == 0            (local byte[4], last element — BSS, first call)
;  9.  l_warr[0] == 0           (local word[2], first element — BSS, first call)
; 10.  l_warr[1] == 0           (local word[2], second element — BSS, first call)
; 11.  l_pair.x == 0            (local struct, first field — BSS, first call)
; 12.  l_pair.y == 0            (local struct, second field — BSS, first call)
;
; Expected result: 12 = $0C

byte result @40000 = 0

byte g_byte
word g_word
byte g_arr[4]

struct Pair
    byte x
    byte y
end

Pair g_pair

proc main()
    byte l_arr[4]
    word l_warr[2]
    Pair l_pair

    ; --- 1: global byte, no init ---
    if g_byte == 0
        result = result + 1     ; 1
    end

    ; --- 2: global word, no init ---
    if g_word == 0
        result = result + 1     ; 2
    end

    ; --- 3-4: global byte array, no init ---
    if g_arr[0] == 0
        result = result + 1     ; 3
    end
    if g_arr[3] == 0
        result = result + 1     ; 4
    end

    ; --- 5-6: global struct, no init ---
    if g_pair.x == 0
        result = result + 1     ; 5
    end
    if g_pair.y == 0
        result = result + 1     ; 6
    end

    ; --- 7-8: local byte array (first call, BSS = 0) ---
    if l_arr[0] == 0
        result = result + 1     ; 7
    end
    if l_arr[3] == 0
        result = result + 1     ; 8
    end

    ; --- 9-10: local word array (first call, BSS = 0) ---
    if l_warr[0] == 0
        result = result + 1     ; 9
    end
    if l_warr[1] == 0
        result = result + 1     ; 10
    end

    ; --- 11-12: local struct (first call, BSS = 0) ---
    if l_pair.x == 0
        result = result + 1     ; 11
    end
    if l_pair.y == 0
        result = result + 1     ; 12
    end
end
