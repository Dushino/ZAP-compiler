; Fail test: dereferencing a local pointer variable before any assignment
; Expected: SemanticError "Use of uninitialized variable 'PTR'"

proc main()
    byte^ ptr
    byte result
    result = ptr^   ; ptr was never assigned (dereference walks pointer identifier)
end
