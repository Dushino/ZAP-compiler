;-------------------------------------------------------------------------
; POKEY Address Equates
; https://www.atariarchives.org/mapping/memorymap.php
;-------------------------------------------------------------------------


; Read Addresses
struct POKEY_RD_struct #port #RD
    byte POT0          ;$00 potentiometer 0
    byte POT1          ;$01 potentiometer 1
    byte POT2          ;$02 potentiometer 2
    byte POT3          ;$03 potentiometer 3
    byte POT4          ;$04 potentiometer 4
    byte POT5          ;$05 potentiometer 5
    byte POT6          ;$06 potentiometer 6
    byte POT7          ;$07 potentiometer 7
    byte ALLPOT        ;$08 potentiometer port status

    byte KBCODE        ;$09 keyboard code
    byte RANDOM        ;$0A random number generator
    byte NA0           ;$0B none
    byte NA1           ;$0C none - 
    byte SERIN         ;$0D serial port input
    byte IRQST         ;$0E IRQ interrupt status
    byte SKSTAT        ;$0F serial port and keyboard status
end


; Write Addresses
struct POKEY_WR_struct #port #WR
    byte AUDF1         ;$00 channel 1 audio frequency
    byte AUDC1         ;$01 channel 1 audio control
    byte AUDF2         ;$02 channel 2 audio frequency
    byte AUDC2         ;$03 channel 2 audio control
    byte AUDF3         ;$04 channel 3 audio frequency
    byte AUDC3         ;$05 channel 3 audio control
    byte AUDF4         ;$06 channel 4 audio frequency
    byte AUDC4         ;$07 channel 4 audio control
    byte AUDCTL        ;$08 audio control
    byte STIMER        ;$09 start timers
    byte SKRES         ;$0A reset SKSTAT status
    byte POTGO         ;$0B start potentiometer scan sequence
    byte SEROUT        ;$0C serial port output
    byte IRQEN         ;$0D IRQ interrupt enable
    byte SKCTL         ;$0E serial port and keyboard control
end

; Shadow registers
byte PADDL0 @624
byte PADDL1 @625
byte PADDL2 @626
byte PADDL3 @627
byte PADDL4 @628
byte PADDL5 @629
byte PADDL6 @630
byte PADDL7 @631

byte STICK0 @632
byte STICK1 @633
byte STICK2 @634
byte STICK3 @635

byte PTRIG0 @636
byte PTRIG1 @637
byte PTRIG2 @638
byte PTRIG3 @639
byte PTRIG4 @640
byte PTRIG5 @641
byte PTRIG6 @642
byte PTRIG7 @643

byte STRIG0 @644
byte STRIG1 @645
byte STRIG2 @646
byte STRIG3 @647


POKEY_WR_struct POKEY_WR @$D200
POKEY_RD_struct POKEY_RD @$D200

; EOF
