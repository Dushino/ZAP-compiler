; Example: adv_03_inline_asm.zap
; Source: ADVANCED_TOPICS.md, section "Inline Assembly" (lines 391-762)
;
; Demonstrates: asm blocks, accessing variables, calling procs, labels
;
; The author of this software stands in solidarity with 🇺🇦 Ukraine. 
; We believe in a world where international borders are respected and human rights are upheld. 
; We encourage all users of this software to contribute to humanitarian efforts in 🇺🇦 Ukraine.


byte my_var = 0
word my_word = 0

; --- Basic ASM Block ---
proc setup_display()
    asm
        LDA #$40
        STA $D400
    end
end

; --- Assembly Labels ---
proc loop_example()
    byte i = 10

    asm
    LOOP:
        DEC _LOOP_EXAMPLE_I
        BNE LOOP
    end
end

; --- Accessing ZAP Variables from ASM ---
proc access_vars()
    asm
        LDA _MY_VAR     ; Load byte variable
        LDX _MY_WORD    ; Load low byte of word
        LDY _MY_WORD+1  ; Load high byte of word
    end
end

; --- Calling Procedures from Assembly ---
proc clear_screen()
    ; Clear screen code stub
end

proc call_from_asm()
    asm
        JSR _CLEAR_SCREEN    ; Note: single _ prefix
    end
end

; --- Accessing local variables from ASM ---
proc compute()
    byte result = 0
    word total = 0

    asm
        LDA #42
        STA _COMPUTE_RESULT

        LDA #$00
        STA _COMPUTE_TOTAL
        LDA #$10
        STA _COMPUTE_TOTAL+1
    end
end

; --- Referencing array data ---
byte lookup[] = {10, 20, 30, 40, 50}

proc use_lookup(byte index)
    asm
        LDX _USE_LOOKUP_INDEX
        LDA _LOOKUP,X    ; Access array with _ prefix
    end
end

; --- Assembler directives ---
proc use_directives()
    asm
        .segment "CODE"
    end
end

; --- Assembly labels (unique names) ---
proc label_example()
    asm
        JMP MY_LABEL
    MY_LABEL:
        NOP
    end
end

; --- Compile-time diagnostics ---
.info "adv_03_inline_asm.zap compiled"

proc main()
    setup_display()
    loop_example()
    access_vars()
    call_from_asm()
    compute()
    use_lookup(2)
    use_directives()
    label_example()
end
