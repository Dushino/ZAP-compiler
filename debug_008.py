#!/usr/bin/env python3
"""Debug test 008 to trace the calculations"""

# Test setup:
# cube[2][3][4] of BYTE
# Dimensions: [2, 3, 4]
# Strides: [3*4*1, 4*1, 1] = [12, 4, 1]

# Expected assignments:
assignments = [
    # (index_tuple, value)
    ((0, 0, 0), 1),
    ((0, 0, 1), 2),
    ((0, 1, 0), 3),
    ((0, 1, 1), 4),
    ((1, 0, 0), 10),
    ((1, 0, 1), 20),
    ((1, 1, 0), 30),
    ((1, 1, 1), 40),
]

# Expected sum: cube[0][0][0] + cube[0][1][1] + cube[1][0][0] + cube[1][1][1]
# = 1 + 4 + 10 + 40 = 55 (0x37)

def calculate_offset(indices, dims):
    """Calculate linear offset for multidimensional array"""
    strides = []
    stride = 1
    for i in range(len(dims)-1, -1, -1):
        strides.insert(0, stride)
        stride *= dims[i]
    
    offset = 0
    for idx, s in zip(indices, strides):
        offset += idx * s
    return offset

dims = [2, 3, 4]

# Build memory
memory = {}

for indices, value in assignments:
    offset = calculate_offset(indices, dims)
    memory[offset] = value
    print(f"cube{indices} = {value:3d} (0x{value:02x}) at offset {offset:2d} (0x{offset:02x})")

print("\nMemory contents:")
for offset in sorted(memory.keys()):
    print(f"  offset {offset:2d}: {memory[offset]:3d} (0x{memory[offset]:02x})")

# Load the values
sum_val = 0
for indices in [(0,0,0), (0,1,1), (1,0,0), (1,1,1)]:
    offset = calculate_offset(indices, dims)
    val = memory.get(offset, 0)
    sum_val += val
    print(f"\ncube{indices} = value at offset {offset:2d} = {val}")

print(f"\nSum = {sum_val} (0x{sum_val:02x})")
print(f"Expected: 55 (0x37)")
print(f"Actual result according to user: 0x29 = {0x29}")
