;-------------------------------------------------------------------------
; PIA (6520) Address Equates
; https://www.atariarchives.org/mapping/memorymap.php
;-------------------------------------------------------------------------


; Read / write Addresses
struct PIA_RD_struct #port
    byte PORTA         ;$00
    byte PORTB         ;$01
    byte PACTL         ;$02 
    byte PBCTL         ;$03
end

PIA_RD_struct PIA @$D300

; EOF
