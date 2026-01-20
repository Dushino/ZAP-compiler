; Test: missing required parameters in procedure call
; This should fail because test1 requires 2 parameters but only 1 or is passed

proc test1(byte p1, byte p2)
end


proc main()
    test1(3)
end
