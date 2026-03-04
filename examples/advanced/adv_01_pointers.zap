; Example: adv_01_pointers.zap
; Source: ADVANCED_TOPICS.md, section "Pointer Operations" (lines 28-201)
;
; Demonstrates: pointer basics, address-of, dereferencing, pointer arithmetic

; --- Understanding Pointers ---
byte x = 42
byte ^ptr               ; Pointer type

; --- Alternative address-of syntax ---
byte data = 100

; --- Array element address ---
byte arr[] = {10, 20, 30}

; --- Struct field address ---
struct Point
    byte x
    byte y
end

Point p = {50, 100}

; --- Pointer Arithmetic ---
; BYTE pointer
byte arr2[] = {10, 20, 30}

; WORD pointer
word addresses[] = {$1000, $2000, $3000}

; --- Pointer Arrays ---
byte data1[] = "First"
byte data2[] = "Second"
byte ^ptrs[2]

; --- Pointer to Pointer (Limited) ---
byte xx = 100

; --- Linked List (simulated with arrays) ---
byte value[10]              ; Node values
byte next_index[10]         ; Next node index (255 = end)
byte list_start = 0         ; Start of list

proc traverse_list()
    byte current = list_start

    while current != 255
        current = next_index[current]
    end
end

proc main()
    ; All locals declared first (ZAP rule)
    byte ^ptr1 = @x
    byte val = 0
    byte ^ptr2 = @data
    word elem_addr = @arr[1]
    word field_addr = @p.x
    byte ^ptr3 = @x
    byte value2 = 0
    byte ^bptr = @arr2
    byte second = 0
    word ^wptr = @addresses
    word addr2 = 0
    word distance = 0
    byte char1 = 0
    byte char2 = 0
    byte ^pp1 = @xx
    byte ^pp2 = pp1

    ; Pointer basics
    val = ptr1^             ; val = 42
    ptr1^ = 99              ; x = 99

    ; Dereferencing
    value2 = ptr3^          ; Read through pointer
    ptr3^ = 50              ; Write through pointer

    ; BYTE pointer arithmetic
    bptr = bptr + 1         ; Points to second element
    second = bptr^          ; second = 20

    ; WORD pointer arithmetic
    wptr = wptr + 1         ; Points to second WORD (2 bytes later)
    addr2 = wptr^           ; addr2 = $2000

    ; Pointer difference
    distance = wptr - @addresses  ; Returns 1 (1 element apart)

    ; Pointer Arrays
    ptrs[0] = @data1
    ptrs[1] = @data2
    char1 = ptrs[0]^        ; 'F' from data1
    char2 = ptrs[1]^        ; 'S' from data2

    ; Linked list setup
    value[0] = 10
    value[1] = 20
    value[2] = 30
    next_index[0] = 1
    next_index[1] = 2
    next_index[2] = 255     ; End of list

    traverse_list()
end
