; Test: overflow zero page - many pointer variables (must go in ZP)
proc main()
    byte^ p1, p2, p3, p4, p5, p6, p7, p8, p9, p10
    byte^ p11, p12, p13, p14, p15, p16, p17, p18, p19, p20
    byte^ p21, p22, p23, p24, p25, p26, p27, p28, p29, p30
    p1 = 0
end
