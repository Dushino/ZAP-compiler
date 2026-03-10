; Test compile-time constant folding of array indices.
; When the index is a const expression, the offset is computed at compile time.

const byte FIRST = 0
const byte LAST  = 4
const byte MID   = 2

byte arr[5] @50000
word warr[4] @50010

struct S3
    byte a
    byte b
    byte c
end

S3 sarr[4] @50100

byte out0 @40000 = 0
byte out1 @40001 = 0
byte out2 @40002 = 0
byte out3 @40003 = 0
byte out4 @40004 = 0
byte out5 @40005 = 0
byte out6 @40006 = 0
byte out7 @40007 = 0

proc main()
    ; Fill byte array
    arr[0] = $10
    arr[1] = $20
    arr[2] = $30
    arr[3] = $40
    arr[4] = $50

    ; Read using compile-time constant indices
    out0 = arr[FIRST]       ; expect $10
    out1 = arr[LAST]        ; expect $50
    out2 = arr[MID]         ; expect $30
    out3 = arr[LAST - 1]    ; expect $40  (constant expression)

    ; Fill struct array
    sarr[0].a = $AA
    sarr[1].a = $BB
    sarr[2].a = $CC
    sarr[3].a = $DD

    ; Read struct array with const indices
    out4 = sarr[FIRST].a    ; expect $AA
    out5 = sarr[LAST - 1].a ; expect $DD  (LAST-1=3)
    out6 = sarr[MID].a      ; expect $CC

    ; Word array with const index
    warr[0] = $1234
    warr[1] = $5678
    warr[2] = $9ABC
    out7 = low(warr[MID])   ; expect low($9ABC) = $BC
end
