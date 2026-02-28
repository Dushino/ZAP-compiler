; Test: byte array initialized with a 255-char string.
; copy_len = (255 chars + 1 null) * 1 = 256 bytes → triggers COPY_BYTES16.
; str[0] == 65 ('A'), str[254] == 65, str[255] == 0 (null terminator).
; Each passing check increments result. Expected result: 3.

byte result @40000 = 0

proc main()
    byte str[256] = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"

    if str[0] == 65
        result = result + 1     ; 1  ('A' = 65)
    end

    if str[254] == 65
        result = result + 1     ; 2  (last 'A')
    end

    if str[255] == 0
        result = result + 1     ; 3  (null terminator)
    end
end
