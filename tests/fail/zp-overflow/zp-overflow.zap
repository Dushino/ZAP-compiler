; Test: zero page overflow must be detected by ZAP compiler
; With -ZPSTART 254, only 2 bytes of ZP are available,
; but compiler temps and variables need more.
proc main()
    word a, b
    a = 1
    b = a * 2
end
