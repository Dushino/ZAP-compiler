; Example: ref_02_data_types.zap
; Source: ZAP_LANGUAGE_REFERENCE.md, section "Data Types" (lines 91-175)
;
; Demonstrates: byte/word/long, hex/binary literals, character literals, escapes

; --- byte ---
byte bx              ; Uninitialized byte variable
byte by = 42         ; Byte with initializer
byte bz = $FF        ; Hex notation
byte bw = %10101010  ; Binary notation

; --- word ---
word address         ; Uninitialized word variable
word counter = 1000  ; Word with initializer
word value = $1234   ; Hex notation

; --- long ---
long big_num         ; Uninitialized long variable
long population = 1000000
long mask = $FFFFFFFF

; --- Character Literals ---
byte c = 'A'            ; Character literal (value 65)
byte newline = '\n'     ; Newline character (value 10)
byte tab = '\t'         ; Tab character (value 9)
byte quote = '\''       ; Single quote (value 39)
byte backslash = '\\'   ; Backslash (value 92)
byte null_ch = '\0'     ; Null terminator (value 0)
byte hex_255 = '\xFF'   ; Hex escape (value 255)
byte octal_65 = '\101'  ; Octal escape (value 65, same as 'A')

; --- String with escapes ---
byte arr2[] = "Hello\0World"   ; String with embedded null
byte data3[] = {$FF, $00, $42}  ; Binary data
byte mask2 = '\b11110000'      ; Mask value using binary

proc main()
    bx = 0
end
