# Test 007: 2D Multidimensional Arrays

## Feature
Tests two-dimensional (2D) arrays with BYTE elements.

## Description
3x4 matrix (3 rows, 4 columns) of BYTE type with initialization and element access.

## Test Code
```zap
word result @40000 = 0

proc main()
    byte matrix[3][4]
    byte sum
    
    ' Initialize 3x4 matrix
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
    
    ' Diagonal sum: 1 + 6 + 11 = 18
    sum = matrix[0][0] + matrix[1][1] + matrix[2][2]
    result = sum
end
```

## Expected Behavior
- 2D array matrix[3][4] allocated (12 bytes)
- Matrix layout in memory (row-major):
  - Row 0: [1, 2, 3, 4]
  - Row 1: [5, 6, 7, 8]
  - Row 2: [9, 10, 11, 12]
- Diagonal sum: matrix[0][0] + matrix[1][1] + matrix[2][2] = 1 + 6 + 11 = 18 (0x12)

## Memory Validation
- Expected memory at $9C40: 0x12 (18 decimal)
