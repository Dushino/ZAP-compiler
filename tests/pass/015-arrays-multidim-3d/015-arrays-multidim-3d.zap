word result @40000 = 0

proc main()
    byte cube[2][3][4]
    byte sum
    
    ; Initialize first layer (layer 0)
    cube[0][0][0] = 1
    cube[0][0][1] = 2
    cube[0][1][0] = 3
    cube[0][1][1] = 4
    
    ; Initialize second layer (layer 1)
    cube[1][0][0] = 10
    cube[1][0][1] = 20
    cube[1][1][0] = 30
    cube[1][1][1] = 40
    
    ; Sum diagonal elements from both layers
    ; 1 + 4 + 10 + 40 = 55 (0x37)
    sum = cube[0][0][0] + cube[0][1][1] + cube[1][0][0] + cube[1][1][1]
    result = sum
end
