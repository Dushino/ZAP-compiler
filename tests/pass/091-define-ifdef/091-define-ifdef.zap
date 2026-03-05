.define FEATURE
.define TEMP

byte result @40000 = 0

proc main()
    ; --- 1: .ifdef on defined symbol ---
    .ifdef FEATURE
    result = result + 1
    .endif

    ; --- 2: .ifndef on undefined symbol ---
    .ifndef MISSING
    result = result + 1
    .endif

    ; --- 3: .undef removes symbol, .ifdef should fail ---
    .undef TEMP
    .ifdef TEMP
    result = result + 100   ; should NOT execute
    .endif
    result = result + 1     ; 3

    ; --- 4: .ifndef on undef'd symbol should succeed ---
    .ifndef TEMP
    result = result + 1     ; 4
    .endif

    ; --- 5: .undef on never-defined symbol is harmless ---
    .undef NONEXISTENT
    result = result + 1     ; 5

    ; --- 6: .define after .undef re-enables symbol ---
    .define TEMP
    .ifdef TEMP
    result = result + 1     ; 6
    .endif
end
