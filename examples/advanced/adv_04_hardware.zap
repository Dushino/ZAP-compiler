; Example: adv_04_hardware.zap
; Source: ADVANCED_TOPICS.md, section "Hardware Access" (lines 765-863)
;
; Demonstrates: hardware registers, reading/writing, sound, game loop

; --- Atari 8-Bit Registers ---
; GTIA (Graphics) Registers
byte GTIA_M0PL @$D00C #PORT #RD    ; Missile 0 / Player collision (read-only)
byte GTIA_P0PL @$D00D #PORT #RD    ; Player 0 collision (read-only)
byte GTIA_HPOS0 @$D000 #PORT #WR   ; Player 0 horizontal position (write-only)

; ANTIC (Display) Registers
word ANTIC_DLIST @$D402 #PORT       ; Display list pointer (read/write)
byte ANTIC_HSCROL @$D404 #PORT #WR ; Horizontal scroll (write-only)

; POKEY (Sound/I/O) Registers
byte POKEY_AUDF1 @$D200 #PORT #WR  ; Audio frequency 1 (write-only)
byte POKEY_AUDC1 @$D201 #PORT #WR  ; Audio control 1 (write-only)

; --- Reading Registers ---
proc check_collision()
    byte collision = GTIA_M0PL
    if collision != 0
        ; Collision detected!
    end
end

; --- Writing to Registers ---
proc move_player(byte x)
    GTIA_HPOS0 = x      ; Set player X position
end

proc set_display_list(word address)
    ANTIC_DLIST = address
end

; --- Sound Output ---
proc play_note(byte frequency, byte duration)
    byte i = 0

    POKEY_AUDF1 = frequency
    POKEY_AUDC1 = $A8      ; Enable audio

    ; Wait
    for i = 0 to duration
        ; Busy-wait
    end

    POKEY_AUDC1 = 0        ; Stop audio
end

proc main()
    check_collision()
    move_player(128)
    set_display_list($BC40)
    play_note(100, 200)
end
