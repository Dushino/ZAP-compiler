word result @40000 = 0

proc main()
    byte matrix[3][4]
    byte sum
    
    ; Initialize 3x4 matrix
    matrix[0][0] = 1
    matrix[0][1] = 2
    matrix[0][2] = 3
    matrix[0][3] = 4
    
    matrix[1][0] = 5
    matrix[1][1] = 6
    matrix[1][2] = 7
    matrix[1][3] = 8
    
    matrix[2][0] = 9
    matrix[2][1] = 10
    matrix[2][2] = 11
    matrix[2][3] = 12
    
    ; Sum = 1+6+11 = 18 (0x12)
    sum = matrix[0][0] + matrix[1][1] + matrix[2][2]  ; 1 + 6 + 11 = 18 (0x12)
    result = sum
end
