; Regression test: shift-add (byte * small_constant) that overflows a byte was
; losing the high byte when the result was used in a subsequent addition.
; Bug: eval_stack.append(("MATH0", node.width)) used node.width=1 (byte, from
; type system) even though the shift-add had widened the result to 2 on the
; eval_stack.  The ADD/SUB routine path now uses max(node.width, left_width,
; right_width) so the full 16-bit result is kept.

byte result_lo @$0200
byte result_hi @$0201

proc test(byte x, byte y) #noexport
    word p1
    p1 = 40*y + x       ; 40*7 + 3 = 283 = $011B
    result_lo = low(p1)
    result_hi = high(p1)
end

proc main()
    test(3, 7)
end
