;-------------------------------------------------------------------------
; CTIA/GTIA Address Equates
; https://www.atariarchives.org/mapping/memorymap.php
;-------------------------------------------------------------------------


; Read/Write Addresses
struct GTIA_RD_struct #port #RD
    byte M0PF           ;$00 missile 0 and playfield collision
    byte M1PF           ;$01 missile 1 and playfield collision
    byte M2PF           ;$02 missile 2 and playfield collision
    byte M3PF           ;$03 missile 3 and playfield collision

    byte P0PF           ;$04 player 0 and playfield collision
    byte P1PF           ;$05 player 1 and playfield collision
    byte P2PF           ;$06 player 2 and playfield collision
    byte P3PF           ;$07 player 3 and playfield collision

    byte M0PL           ;$08 missile 0 and player collision
    byte M1PL           ;$09 missile 1 and player collision
    byte M2PL           ;$0A missile 2 and player collision
    byte M3PL           ;$0B missile 3 and player collision

    byte P0PL           ;$0C player 0 and player collision
    byte P1PL           ;$0D player 1 and player collision
    byte P2PL           ;$0E player 2 and player collision
    byte P3PL           ;$0F player 3 and player collision

    byte TRIG0          ;$10 joystick trigger 0
    byte TRIG1          ;$11 joystick trigger 1
    byte TRIG2          ;$12 cartridge interlock
    byte TRIG3          ;$13 ACMI module interlock

    byte PAL            ;$14 PAL/NTSC indicator

    byte NA0            ;$15 none
    byte NA1            ;$16 none
    byte NA2            ;$17 none
    byte NA3            ;$18 none

    byte NA4            ;$19 none
    byte NA5            ;$1A none
    byte NA6            ;$1B none
    byte NA7            ;$1C none

    byte NA8            ;$1D 

    byte NA9            ;$1E none - write only (PRIOR in WR)
    byte NAA            ;$1F none - write only (VDELAY in WR)
    byte NAB            ;$20 none - write only (GRACTL in WR)
    byte NAC            ;$21 none - write only (HITCLR in WR)
    byte CONSOL         ;$22 console buttons state
end


struct GTIA_WR_struct #port #WR
    byte HPOSP0         ;$00 player 0 horizontal position
    byte HPOSP1         ;$01 player 1 horizontal position
    byte HPOSP2         ;$02 player 2 horizontal position
    byte HPOSP3         ;$03 player 3 horizontal position

    byte HPOSM0         ;$04 missile 0 horizontal position
    byte HPOSM1         ;$05 missile 1 horizontal position
    byte HPOSM2         ;$06 missile 2 horizontal position
    byte HPOSM3         ;$07 missile 3 horizontal position

    byte SIZEP0         ;$08 player 0 size
    byte SIZEP1         ;$09 player 1 size
    byte SIZEP2         ;$0A player 2 size
    byte SIZEP3         ;$0B player 3 size

    byte SIZEM          ;$0C missile sizes

    byte GRAFP0         ;$0D player 0 graphics
    byte GRAFP1         ;$0E player 1 graphics
    byte GRAFP2         ;$0F player 2 graphics
    byte GRAFP3         ;$10 player 3 graphics

    byte GRAFM          ;$11 missile graphics

    byte COLPM0         ;$12 player-missile 0 color/luminance
    byte COLPM1         ;$13 player-missile 1 color/luminance
    byte COLPM2         ;$14 player-missile 2 color/luminance
    byte COLPM3         ;$15 player-missile 3 color/luminance

    byte COLPF0         ;$16 playfield 0 color/luminance
    byte COLPF1         ;$17 playfield 1 color/luminance
    byte COLPF2         ;$18 playfield 2 color/luminance
    byte COLPF3         ;$19 playfield 3 color/luminance

    byte COLBK          ;$1A background color/luminance

    byte PRIOR          ;$1B priority select
    byte VDELAY         ;$1C vertical delay
    byte GRACTL         ;$1D graphic control
    byte HITCLR         ;$1E collision clear
    byte CONSOL         ;$1F console buttons read reset
end

; shadow registers
byte PCOLR0  @704 
byte PCOLR1  @705       
byte PCOLR2  @706       
byte PCOLR3  @707       
byte COLOR0  @708       
byte COLOR1  @709
byte COLOR2  @710
byte COLOR3  @711
byte COLOR4  @712

; PMG shadow registers
byte M0COLOR @713
byte M1COLOR @714
byte M2COLOR @715
byte M3COLOR @716   
byte GPRIOR  @717


; ATARI colors
const byte COLOR_BLACK          = $00
const byte COLOR_RUST           = $10
const byte COLOR_RED_ORANGE     = $20
const byte COLOR_DARK_ORANGE    = $30
const byte COLOR_RED            = $40
const byte COLOR_DARK_LAVENDER  = $50
const byte COLOR_COBALT_BLUE    = $60
const byte COLOR_ULTRAMARINE    = $70
const byte COLOR_MEDIUM_BLUE    = $80
const byte COLOR_DARK_BLUE      = $90
const byte COLOR_BLUE_GREY      = $A0
const byte COLOR_OLIVE_GREEN    = $B0
const byte COLOR_MEDIUM_GREEN   = $C0
const byte COLOR_DARK_GREEN     = $D0
const byte COLOR_ORANGE_GREEN   = $E0
const byte COLOR_ORANGE         = $F0


GTIA_RD_struct GTIA_RD = $D000
GTIA_WR_struct GTIA_WR = $D000

; EOF
