byte result @40000 = 0

proc main()
    word w = 'a''b'                 ; $6261 two char literals: low='a', high='b' (implementation dependent but supported)
    byte low = w & 0xFF             ; $61
    byte high = (w >> 8) & 0xFF     ; $62
    result = low + high             ; 0x61 + 0x62 = 97 + 98 = 195 $C3
end
