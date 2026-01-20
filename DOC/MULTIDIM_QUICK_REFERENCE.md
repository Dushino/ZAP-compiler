# Multi-Dimensional Arrays - Quick Reference

## Syntax

```zap
; Declaration
[type] name[size1][size2][...][sizeN]

; Examples
byte grid[3][4]              ; 2D array of bytes (3×4 = 12 bytes)
word matrix[2][3]            ; 2D array of words (2×3×2 = 12 bytes)
struct Point map[5][10]      ; 2D array of structs
byte ^pointers[4][5]         ; 2D array of byte pointers (4×5×2 = 40 bytes)
```

## Memory Layout

Row-major (C-style) ordering:
- `arr[0][0], arr[0][1], arr[0][2], arr[1][0], arr[1][1], arr[1][2], ...`

Total memory = `size1 × size2 × ... × sizeN × element_width`

## Indexing

```zap
; Read element
value = arr[i][j]
value = arr[i][j][k]

; Write element
arr[i][j] = value
arr[i][j][k] = 42

; Partial subscripting (returns pointer)
ptr_to_row = arr[i]           ; Type: byte ^ (pointer to next dimension)
```

## Type Inference

```zap
byte grid[3][4]
byte x

x = grid[1]         ; ❌ Type error: grid[1] is byte^ (pointer), not byte
x = grid[1][2]      ; ✅ OK: grid[1][2] is byte (element)

byte ^p
p = grid[0]         ; ✅ OK: assign row pointer to byte^
p = grid            ; ❌ Type error: grid is byte^^ (2D array)
```

## Nested Loops

```zap
byte grid[3][4]

proc print_grid()
  byte i
  byte j
  
  i = 0
  while i < 3
    j = 0
    while j < 4
      ; Access grid[i][j]
      output grid[i][j]
      j = j + 1
    end
    i = i + 1
  end
end
```

## Initialization

```zap
; Nested initialization
byte grid[2][3] = {
  {1, 2, 3},
  {4, 5, 6}
}

; Flat initialization (auto-fills in row-major order)
byte grid[2][3] = {1, 2, 3, 4, 5, 6}

; With pointers
byte data[5] = {10, 20, 30, 40, 50}
byte ^ptrs[2][2] = {
  {@data[0], @data[1]},
  {@data[3], @data[4]}
}
```

## Common Patterns

### 2D Matrix Transpose
```zap
byte src[3][4]
byte dst[4][3]

proc transpose()
  byte i
  byte j
  
  i = 0
  while i < 3
    j = 0
    while j < 4
      dst[j][i] = src[i][j]
      j = j + 1
    end
    i = i + 1
  end
end
```

### 3D Grid Operations
```zap
byte cube[2][2][2]

proc fill_cube()
  byte x
  byte y
  byte z
  byte counter
  
  counter = 0
  x = 0
  while x < 2
    y = 0
    while y < 2
      z = 0
      while z < 2
        cube[x][y][z] = counter
        counter = counter + 1
        z = z + 1
      end
      y = y + 1
    end
    x = x + 1
  end
end
```

### Pointer Array Dereferencing
```zap
byte ^ptrs[3][4]
byte value

; Set pointer
ptrs[0][0] = @some_variable

; Dereference
value = *ptrs[0][0]

; Modify through pointer
*ptrs[0][0] = 42
```

## Performance Considerations

- **Dimensions must be constants**: `byte arr[n][m]` won't work (n, m must be literals)
- **Row-major layout**: Most cache-friendly access is row-wise
- **Stride multiplication**: Larger dimensions = more efficient strides

Example performance (stride calculation in assembly):
```
For arr[i][j] with dimensions [10, 20]:
- Stride for i = 20
- Calculate: offset = i*20 + j
```

## Limitations

| Feature | Supported | Notes |
|---------|-----------|-------|
| 2D arrays | ✅ | Fully supported |
| 3D arrays | ✅ | Fully supported |
| 4D+ arrays | ✅ | Any number of dimensions |
| Dynamic sizing | ❌ | Dimensions must be compile-time constants |
| Jagged arrays | ❌ | All rows same length required |
| Slice operations | ❌ | Can only access full elements or rows |
| Partial initialization | ⚠️ | Partial rows treated as separate elements |

## Troubleshooting

### "Cannot subscript non-array type"
```zap
byte x[3][4]
byte value = x[0][0][0]  ; ❌ Error: x[0][0] is byte (not array)
```
**Fix**: Remove extra subscript or adjust dimensions

### "Type mismatch: expected pointer, got byte"
```zap
byte x[3][4]
byte ^p
p = x[0][0]  ; ❌ Error: x[0][0] is byte, not pointer
p = x[0]     ; ✅ OK: x[0] is pointer to row
```
**Fix**: Use partial subscript to get pointer, not full subscript

### "Array dimensions must be compile-time constants"
```zap
byte n = 5
byte x[n][10]  ; ❌ Error: n is runtime value
```
**Fix**: Use literal constants for dimensions

---

**Last Updated**: January 20, 2026
