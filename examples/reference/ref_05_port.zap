; Example: ref_05_port.zap
; Source: ZAP_LANGUAGE_REFERENCE.md, section "port" (lines 232-263)
;
; Demonstrates: #PORT, #RD, #WR modifiers

; --- Port Variables ---
byte POKEY_AUDF1 @$D200 #PORT       ; standard read/write
byte JOYSTICK @$D300 #PORT #RD      ; reading joystick status
byte SOUND_OUT @$D400 #PORT #WR     ; writing audio registers

proc main()
    byte joy = JOYSTICK     ; OK - read from #RD port
    byte freq = POKEY_AUDF1 ; OK - read from read/write port

    SOUND_OUT = $A8         ; OK - write to #WR port
    POKEY_AUDF1 = 100       ; OK - read/write port
end
