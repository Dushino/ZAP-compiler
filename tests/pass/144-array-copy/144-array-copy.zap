; Test: array-to-array copy (arr1 = arr2) for all scalar element types
; and across small (≤8 bytes), medium (9–255 bytes), and large (≥256 bytes) sizes.
;
; Checks (result +1 each):
;  1-2.  BYTE small (4 bytes):      dst[0]==1, dst[3]==4
;  3-4.  BYTE medium (10 bytes):    dst[0]==10, dst[9]==100
;  5-6.  BYTE large (256 bytes):    dst[0]==1, dst[127]==128
;  7-8.  WORD (10 elements=20 B):   dst[0]==1000, dst[9]==10000
;  9-10. LONG (4 elements=16 B):    dst[0]==65536, dst[3]==262144
; 11-12. Multi-dim BYTE (2x5=10 B): dst[0][0]==11, dst[1][4]==20
;
; Expected result: 12 = $0C

byte result @40000 = 0

func byte Func1(byte a, byte b)
    return a + b
end


proc Proc1(word x, word y)

end


proc main()
    ; All declarations first
    byte src_b4[4] = {1, 2, 3, 4}
    byte dst_b4[4]
    byte src_b10[10] = {10, 20, 30, 40, 50, 60, 70, 80, 90, 100}
    byte dst_b10[10]
    byte src_b256[256] = {
        1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16,
        17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32,
        33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48,
        49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62, 63, 64,
        65, 66, 67, 68, 69, 70, 71, 72, 73, 74, 75, 76, 77, 78, 79, 80,
        81, 82, 83, 84, 85, 86, 87, 88, 89, 90, 91, 92, 93, 94, 95, 96,
        97, 98, 99, 100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112,
        113, 114, 115, 116, 117, 118, 119, 120, 121, 122, 123, 124, 125, 126, 127, 128,
        129, 130, 131, 132, 133, 134, 135, 136, 137, 138, 139, 140, 141, 142, 143, 144,
        145, 146, 147, 148, 149, 150, 151, 152, 153, 154, 155, 156, 157, 158, 159, 160,
        161, 162, 163, 164, 165, 166, 167, 168, 169, 170, 171, 172, 173, 174, 175, 176,
        177, 178, 179, 180, 181, 182, 183, 184, 185, 186, 187, 188, 189, 190, 191, 192,
        193, 194, 195, 196, 197, 198, 199, 200, 201, 202, 203, 204, 205, 206, 207, 208,
        209, 210, 211, 212, 213, 214, 215, 216, 217, 218, 219, 220, 221, 222, 223, 224,
        225, 226, 227, 228, 229, 230, 231, 232, 233, 234, 235, 236, 237, 238, 239, 240,
        241, 242, 243, 244, 245, 246, 247, 248, 249, 250, 251, 252, 253, 254, 255, 0
    }
    byte dst_b256[256]
    word src_w10[10] = {1000, 2000, 3000, 4000, 5000, 6000, 7000, 8000, 9000, 10000}
    word dst_w10[10]
    long src_l4[4] = {65536, 131072, 196608, 262144}
    long dst_l4[4]
    byte src_md[2][5] = {11, 12, 13, 14, 15, 16, 17, 18, 19, 20}
    byte dst_md[2][5]
    byte bbb

    ; --- 1-2. BYTE small (4 bytes) ---
    dst_b4 = src_b4
    if dst_b4[0] == 1
        result = result + 1     ; 1
    end
    if dst_b4[3] == 4
        result = result + 1     ; 2
    end

    ; --- 3-4. BYTE medium (10 bytes) ---
    dst_b10 = src_b10
    if dst_b10[0] == 10
        result = result + 1     ; 3
    end
    if dst_b10[9] == 100
        result = result + 1     ; 4
    end

    ; --- 5-6. BYTE large (256 bytes) ---
    dst_b256 = src_b256
    if dst_b256[0] == 1
        result = result + 1     ; 5
    end
    if dst_b256[127] == 128
        result = result + 1     ; 6
    end

    ; --- 7-8. WORD copy (10 elements = 20 bytes) ---
    dst_w10 = src_w10
    if dst_w10[0] == 1000
        result = result + 1     ; 7
    end
    if dst_w10[9] == 10000
        result = result + 1     ; 8
    end

    ; --- 9-10. LONG copy (4 elements = 16 bytes) ---
    dst_l4 = src_l4
    if dst_l4[0] == 65536
        result = result + 1     ; 9
    end
    if dst_l4[3] == 262144
        result = result + 1     ; 10
    end

    ; --- 11-12. Multi-dim BYTE copy (2x5 = 10 bytes) ---
    dst_md = src_md
    if dst_md[0][0] == 11
        result = result + 1     ; 11
    end
    if dst_md[1][4] == 20
        result = result + 1     ; 12
    end

    Func1(0, 0)     ; Call to ensure Func1 is included in the binary
    Proc1(0, 0)     ; Call to ensure Proc1 is included in
end
