; Test string literals with high-byte escape sequences (\x80-\xFF).
; Verifies that \xHH works uniformly in all string contexts.

; Context 1: const byte array init (was already working)
const byte cname[] = "AB\x9B"   ; A B Atari-EOL NUL

; Context 2: non-const global byte array init (was broken for len <= 3 inline path)
byte gname[4] @40010 = "C\x9B"  ; C $9B NUL

; Context 3: string literal as function argument (was broken)
func byte byte_at(byte^ ptr, byte idx)
    return (ptr + idx)^
end

byte out0 @40000 = 0    ; cname[0] = 'A' = $41
byte out1 @40001 = 0    ; cname[1] = 'B' = $42
byte out2 @40002 = 0    ; cname[2] = $9B
byte out3 @40003 = 0    ; gname[0] = 'C' = $43
byte out4 @40004 = 0    ; gname[1] = $9B
byte out5 @40005 = 0    ; string-literal arg: byte 0 = 'X' = $58
byte out6 @40006 = 0    ; string-literal arg: byte 1 = $9B

proc main()
    ; Read const string bytes
    out0 = cname[0]     ; expect $41
    out1 = cname[1]     ; expect $42
    out2 = cname[2]     ; expect $9B

    ; Read non-const global string init
    out3 = gname[0]     ; expect $43
    out4 = gname[1]     ; expect $9B

    ; String literal as function argument (was crashing before fix)
    out5 = byte_at("X\x9B", 0)   ; expect $58 ('X')
    out6 = byte_at("X\x9B", 1)   ; expect $9B
end
