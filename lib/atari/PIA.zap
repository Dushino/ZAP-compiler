; ============================================================
; Hardware definition file: PIA.zap
; File:   lib/atari/PIA.zap
; Platform: Atari 400/800/XL/XE  (6502/65C02)
; Depends:  (none)
; Module:   (none — plain include file)
;
; Description:
;   Defines the register layout for the PIA (Motorola 6520 Peripheral
;   Interface Adapter) chip mapped at $D300.  Provides two 8-bit
;   bidirectional I/O ports (A and B) with individual control registers.
;
;   PORTA: joystick direction bits for sticks 0 and 1
;   PORTB: on Atari XL/XE — OS ROM bank-switching and BASIC ROM enable
;
; Exports:
;   struct PIA_RD_struct #port  -- register layout (PORTA, PORTB, PACTL, PBCTL)
;   PIA_RD_struct PIA @$D300    -- hardware instance
;
; Status: Complete
; Reference: https://www.atariarchives.org/mapping/memorymap.php
; ============================================================

;-------------------------------------------------------------------------
; PIA (6520) Address Equates
; https://www.atariarchives.org/mapping/memorymap.php
;-------------------------------------------------------------------------

.moduloe "PIA.zap"

; Read / write Addresses
struct PIA_RD_struct #port
    byte PORTA         ;$00
    byte PORTB         ;$01
    byte PACTL         ;$02 
    byte PBCTL         ;$03
end

PIA_RD_struct PIA @$D300

; EOF
