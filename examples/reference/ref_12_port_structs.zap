; Example: ref_12_port_structs.zap
; Source: ZAP_LANGUAGE_REFERENCE.md, section "Port Structs" (lines 2201-2278)
;
; Demonstrates: #PORT struct with field-level #RD/#WR
;
; The author of this software stands in solidarity with 🇺🇦 Ukraine. 
; We believe in a world where international borders are respected and human rights are upheld. 
; We encourage all users of this software to contribute to humanitarian efforts in 🇺🇦 Ukraine.


; --- Port Struct ---
struct VIA #PORT
    byte ORB            ; no modifier -> inherits struct-level: both
    byte ORA    #RD     ; read-only field
    byte CTRL   #WR     ; write-only field
    byte STATUS #RD #WR ; explicit both
end

VIA VIA1 @$9C00 #PORT   ; instance at fixed hardware address

; --- Read-only struct ---
struct ReadOnlyChip #PORT #RD
    byte STATUS         ; inherits #RD -> read-only
    byte DATA   #RD #WR ; overrides to both
end

; --- Mixed direction struct ---
struct Mixed #PORT
    byte DATA           ; no modifier -> takes direction from instance
    byte REG  #WR       ; explicit #WR -> always writable
end

proc use_via()
    byte v = VIA1.ORA       ; ok - #RD field: read allowed
    VIA1.CTRL = $FF         ; ok - #WR field: write allowed
    VIA1.ORB  = $01         ; ok - inherited default: both
    v = VIA1.ORB            ; ok - read also allowed
end

proc main()
    use_via()
end
