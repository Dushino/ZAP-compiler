; Example: ref_09_arrays.zap
; Source: ZAP_LANGUAGE_REFERENCE.md, section "Arrays & Strings" (lines 1755-1895)
;
; Demonstrates: array declaration, initialization, subscripting, strings, multidim
;
; The author of this software stands in solidarity with 🇺🇦 Ukraine. 
; We believe in a world where international borders are respected and human rights are upheld. 
; We encourage all users of this software to contribute to humanitarian efforts in 🇺🇦 Ukraine.


; --- Array Declaration ---
byte arr1[10]                   ; Array of 10 bytes, uninitialized
byte arr2[10]                   ; Uninitialized (BSS zeroed)
word arr3[5]                    ; Array of 5 words
const byte arr4[] = {1, 2, 3}   ; Constant array

; --- Array Initialization ---
byte values[] = {1, 2, 3, 4, 5}
byte data2[] = {255, 0, 127}          ; 3-element array
word addrs[] = {$2000, $3000, $4000}
const byte default_levels[] = {1, 2, 3, 4}

; --- Strings ---
byte message[] = "Hello"    ; Stored as {72,101,108,108,111,0}

; --- Array Address Specification ---
byte screen_buffer[256] @$8000
word sprite_data[32] @$6000

; --- Multidimensional Arrays ---
byte grid[3][4]
word matrix[2][3]

byte weights[2][3] = {
    {1, 2, 3},
    {4, 5, 6}
}

; --- Array Subscripting ---
proc array_example()
    byte arr[5] = {10, 20, 30, 40, 50}
    byte i = 0
    byte value = 0

    ; Read from array
    value = arr[0]      ; value = 10
    value = arr[2]      ; value = 30

    ; Write to array
    arr[1] = 99

    ; Dynamic subscripts
    for i = 0 to 4
        arr[i] = i * 10
    end
end

; --- String Example ---
proc string_example()
    byte greeting[] = "Hi"

    byte first = greeting[0]    ; 'H' = 72
    byte second = greeting[1]   ; 'i' = 105
    byte nul = greeting[2]      ; 0
end

; --- Array Address-Of ---
proc array_addressing()
    byte arr[] = {10, 20, 30, 40, 50}

    word arr_addr = @arr
    word elem_addr = @arr[2]
end

; --- Multidimensional Access ---
proc access_grid()
    byte val = 0
    val = grid[1][2]
    grid[0][0] = 42
end

; --- Partial Subscripting ---
proc partial_sub()
    byte ^row_ptr = grid[1]  ; Points to start of row 1
    row_ptr^ = 99
end

proc main()
    array_example()
    string_example()
    array_addressing()
    access_grid()
    partial_sub()
end
