; Example: ref_10_structs.zap
; Source: ZAP_LANGUAGE_REFERENCE.md, section "Structs" (lines 1898-2198)
;
; Demonstrates: struct def, init, fields, arrays, const, pointers, nested

; --- Struct Definition ---
struct Point
    byte x
    byte y
end

struct Player
    byte x
    byte y
    byte health
    word score
end

; --- Nested Struct ---
struct Rectangle
    Point top_left
    Point bottom_right
end

; --- Struct Initialization ---
Point p1 = { 10, 20 }
Point p2 = { 100 + 50, 200 - 50 }
Rectangle r = { { 0, 0 }, { 100, 100 } }

; --- Struct Arrays ---
struct Enemy
    byte x
    byte y
    byte health
end

Enemy enemies[10]
Enemy level_enemies[3] = {
    { 10, 20, 100 },
    { 30, 40, 80 },
    { 50, 60, 120 }
}

; --- Array Fields in Structs ---
struct Palette
    byte color[4]
end

struct Track
    word note[3]
end

; --- Const Structs ---
const Point origin = { 0, 0 }

struct Config
    byte mode
    byte flags
end

const Config default_config = { 1, 0 }

; --- Struct with pointer ---
struct Data
    byte value
    byte flag
end

; --- Field Access ---
proc struct_fields()
    Point p = { 15, 30 }
    byte x_value = p.x
    byte y_value = p.y
    Rectangle rr = { { 0, 0 }, { 100, 100 } }
    byte top_left_x = 0

    p.x = 20
    p.y = 40

    ; Nested field access
    top_left_x = rr.top_left.x
    rr.bottom_right.y = 50
end

; --- Update enemies ---
proc update_enemies()
    byte i = 0
    for i = 0 to 2
        enemies[i].x = enemies[i].x + 1
        enemies[i].health = enemies[i].health - 5
    end
end

; --- Array Fields ---
proc use_palette()
    Palette pal = {{ 1, 2, 3, 4 }}
    byte i = 2
    byte v = 0
    byte u = 0
    byte sum = 0
    byte j = 0
    Palette dst = {{0, 0, 0, 0}}

    pal.color[0] = 100
    v = pal.color[0]

    pal.color[i] = 55
    u = pal.color[i]

    for j = 0 to 4
        sum = sum + pal.color[j]
    end

    dst = pal
end

proc use_track()
    Track t = {{ 440, 880, 1760 }}
    word w = 0
    byte k = 1
    t.note[0] = 500
    t.note[k] = 1000
    w = t.note[k]
end

; --- Struct Address-Of ---
proc struct_addressing()
    Point p = { 50, 100 }

    word p_addr = @p
    word x_addr = @p.x
    word y_addr = @p.y

    word enemy_addr = @enemies[0]
    word health_addr = @enemies[0].health
end

; --- Struct Function Parameters ---
func byte distance(Point pp1, Point pp2)
    byte dx = pp1.x - pp2.x
    byte dy = pp1.y - pp2.y
    return dx + dy
end

; --- Struct Function Return ---
func Point add_points(Point pp1, Point pp2)
    Point result = { pp1.x + pp2.x, pp1.y + pp2.y }
    return result
end

; --- Pointers to Structs ---
proc struct_pointers()
    Data d = { 42, 1 }
    Data ^ptr = @d

    byte val = ptr^.value
    ptr^.flag = 0
end

; --- Const struct read ---
proc use_const_struct()
    byte mode = default_config.mode  ; OK - reading const field
end

proc main()
    Point a = { 10, 20 }
    Point b = { 30, 40 }
    byte dist = 0
    Point c = {0, 0}

    struct_fields()
    update_enemies()
    use_palette()
    use_track()
    struct_addressing()

    dist = distance(a, b)
    c = add_points(a, b)

    struct_pointers()
    use_const_struct()
end
