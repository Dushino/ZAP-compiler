;-------------------------------------------------------------------------
; CTIA/GTIA Address Equates
; https://user.xmission.com/~trevin/atari/gtia_regs.html
;-------------------------------------------------------------------------
; TODO: Check all equates and comments against the official Atari documentation:
; https://www.atariarchives.org/2bml/chapter_4_gtia.php


; Read/Write Addresses
struct GTIA_RD_struct #port #RD

    byte M0PF          ;missile 0 and playfield collision
    byte M1PF          ;missile 1 and playfield collision
    byte M2PF          ;missile 2 and playfield collision
    byte M3PF          ;missile 3 and playfield collision

    byte P0PF          ;player 0 and playfield collision
    byte P1PF          ;player 1 and playfield collision
    byte P2PF          ;player 2 and playfield collision
    byte P3PF          ;player 3 and playfield collision

    byte M0PL          ;missile 0 and player collision
    byte M1PL          ;missile 1 and player collision
    byte M2PL          ;missile 2 and player collision
    byte M3PL          ;missile 3 and player collision

    byte P0PL          ;player 0 and player collision
    byte P1PL          ;player 1 and player collision
    byte P2PL          ;player 2 and player collision
    byte P3PL          ;player 3 and player collision

    byte TRIG0         ;joystick trigger 0
    byte TRIG1         ;joystick trigger 1

    byte TRIG2         ;cartridge interlock
    byte TRIG3         ;ACMI module interlock

    byte PAL           ;PAL/NTSC indicator
end


struct GTIA_WR_struct #port #WR

    byte HPOSP0         ;player 0 horizontal position
    byte HPOSP1         ;player 1 horizontal position
    byte HPOSP2         ;player 2 horizontal position
    byte HPOSP3         ;player 3 horizontal position

    byte HPOSM0         ;missile 0 horizontal position
    byte HPOSM1         ;missile 1 horizontal position
    byte HPOSM2         ;missile 2 horizontal position
    byte HPOSM3         ;missile 3 horizontal position

    byte SIZEP0         ;player 0 size
    byte SIZEP1         ;player 1 size
    byte SIZEP2         ;player 2 size
    byte SIZEP3         ;player 3 size

    byte SIZEM          ;missile sizes

    byte GRAFP0         ;player 0 graphics
    byte GRAFP1         ;player 1 graphics
    byte GRAFP2         ;player 2 graphics
    byte GRAFP3         ;player 3 graphics

    byte GRAFM          ;missile graphics

    byte COLPM0         ;player-missile 0 color/luminance
    byte COLPM1         ;player-missile 1 color/luminance
    byte COLPM2         ;player-missile 2 color/luminance
    byte COLPM3         ;player-missile 3 color/luminance

    byte COLPF0         ;playfield 0 color/luminance
    byte COLPF1         ;playfield 1 color/luminance
    byte COLPF2         ;playfield 2 color/luminance
    byte COLPF3         ;playfield 3 color/luminance

    byte COLBK          ;background color/luminance

    byte PRIOR          ;priority select
    byte VDELAY         ;vertical delay
    byte GRACTL         ;graphic control
    byte HITCLR         ;collision clear
end

; ATARI colors
const byte COLOR_BLACK   = $00
const byte COLOR_YELLOW1 = $10
const byte COLOR_ORANGE2 = $20
const byte COLOR_RED1    = $30
const byte COLOR_VIOLET1 = $40
const byte COLOR_VIOLET2 = $50
const byte COLOR_VIOLET3 = $60
const byte COLOR_BLUE1   = $70
const byte COLOR_BLUE2   = $80
const byte COLOR_BLUE3   = $90
const byte COLOR_GREEN1  = $A0
const byte COLOR_GREEN2  = $B0
const byte COLOR_GREEN3  = $C0
const byte COLOR_GREEN4  = $D0
const byte COLOR_YELLOW2 = $E0
const byte COLOR_BROWN   = $F0

; shadow registers
byte PCOLOR0 @704 
byte PCOLOR1 @705       
byte PCOLOR2 @706       
byte PCOLOR3 @707       
byte PLAYF0  @708       
byte PLAYF1  @709
byte PLAYF2  @710
byte PLAYF3  @711
byte PLAYF4  @712


GTIA_RD_struct GTIA_RD = $D000
GTIA_WR_struct GTIA_WR = $D000
