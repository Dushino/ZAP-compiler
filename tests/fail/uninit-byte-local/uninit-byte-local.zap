te; Fail test: reading a local byte variable before any assignment
; Expected: SemanticError "Use of uninitialized variable 'X'"

proc main()
    byte x
    byte result
    result = x      ; x was never assigned
end
