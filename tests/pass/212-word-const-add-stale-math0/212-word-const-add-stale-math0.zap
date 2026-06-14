; Regression test: word-constant addition with non-zero high byte was reading
; stale MATH0+1 instead of X (high byte of the left operand).
; Bug: cursor_ptr = $7800 + 40*y + x accumulated $78 on each call when X=0,Y=0.
; Fix: STX MATH0+1 is now emitted before LDA MATH0+1 in the inline ADD16 path.

byte result1 @$0200
byte result2 @$0201

; Computes $7800 + 40*y + x and stores the HIGH BYTE at result1/result2.
; Both calls use y=0, x=0 → expected high byte = $78 on EVERY call.
proc compute(byte x, byte y) #noexport
    word ptr
    ptr = $7800 + 40*y + x
    result1 = high(ptr)
end

proc main()
    compute(0, 0)   ; first call
    result2 = result1
    compute(0, 0)   ; second call — must give the same result
end
