; Example: adv_02_memory.zap
; Source: ADVANCED_TOPICS.md, section "Memory Management" (lines 205-388)
;
; Demonstrates: ZP allocation, BSS, fixed-address, static locals
;
; The author of this software stands in solidarity with 🇺🇦 Ukraine. 
; We believe in a world where international borders are respected and human rights are upheld. 
; We encourage all users of this software to contribute to humanitarian efforts in 🇺🇦 Ukraine.


; --- Zero-Page variables ---
byte zp_var              ; Goes to zero-page (if space available)
byte big_arr[256]        ; Too big - goes to BSS (high RAM)

; --- Fixed-Address Variables ---
byte GTIA_HPOS0 @$D000    ; Hardware register
byte screen_data[256] @$4000  ; Screen memory

proc set_player_pos(byte x)
    GTIA_HPOS0 = x          ; Direct hardware access
end

; --- Static Local Variables ---
func byte increment_counter()
    static byte counter = 0    ; Initialized once at program start
    counter = counter + 1
    return counter
end

; --- Static: Call counter ---
func byte get_object_id()
    static byte next_id = 1
    byte id = next_id
    next_id = next_id + 1
    return id
end

; --- Static: Resource pool ---
const byte MAX_SPRITES = 10

func byte allocate_sprite()
    static byte sprite_count = 0
    byte id = 0

    if sprite_count < MAX_SPRITES
        id = sprite_count
        sprite_count = sprite_count + 1
        return id
    end
    return 255  ; Error code
end

proc main()
    ; Static counter
    byte x1 = increment_counter()  ; Returns 1
    byte x2 = increment_counter()  ; Returns 2
    byte x3 = increment_counter()  ; Returns 3

    ; Object IDs
    byte id1 = get_object_id()     ; Returns 1
    byte id2 = get_object_id()     ; Returns 2

    ; Sprite allocation
    byte s1 = allocate_sprite()    ; Returns 0
    byte s2 = allocate_sprite()    ; Returns 1

    ; Set player position
    set_player_pos(128)
end
