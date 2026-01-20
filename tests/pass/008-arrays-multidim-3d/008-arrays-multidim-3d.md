# Test 008: 3D Multidimensional Arrays

## Feature
Tests three-dimensional (3D) arrays with BYTE elements.

## Description
2x3x4 cube (2 layers, 3 rows, 4 columns) of BYTE type with initialization and element access.

## Test Code
```zap
word result @40000 = 0

proc main()
    byte cube[2][3][4]
    byte sum
    
    ' Initialize first layer (layer 0)
    cube[0][0][0] = 1
    cube[0][0][1] = 2
    cube[0][1][0] = 3
    cube[0][1][1] = 4
    
    ' Initialize second layer (layer 1)
    cube[1][0][0] = 10
    cube[1][0][1] = 20
    cube[1][1][0] = 30
    cube[1][1][1] = 40
    
    ' Sum diagonal elements from both layers
    sum = cube[0][0][0] + cube[0][1][1] + cube[1][0][0] + cube[1][1][1]
    result = sum
end
```

## Expected Behavior
- 3D array cube[2][3][4] allocated (24 bytes)
- Memory layout (layer-major order):
  - Layer 0: 12 bytes (3 rows × 4 columns)
  - Layer 1: 12 bytes (3 rows × 4 columns)
- Diagonal sum: 1 + 4 + 10 + 40 = 55 (0x37)

## Memory Validation
- Expected memory at $9C40: 0x37 (55 decimal)
