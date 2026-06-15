; Regression test: byte target narrows word+word to byte arithmetic (low byte only).
; w1=$0180, w2=$0180 -> sum=$0300, byte low byte = $00.
; This checks the existing narrowing path still works after widening changes.

byte result @$0200

proc main()
    word w1
    word w2
    byte b
    w1 = $0180
    w2 = $0180
    b = w1 + w2     ; BYTE target -> low byte of $0300 = $00
    result = b
end
