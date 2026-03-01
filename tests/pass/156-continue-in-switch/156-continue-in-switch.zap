byte result @40000 = 0

proc main()
    byte i = 0
    byte k = 0
    byte cnt = 0

    ; --- checks 1,2: continue inside switch inside while targets the while ---
    ; while runs i=1..5; on i==3 the switch fires continue, which skips cnt++
    ; and jumps back to the while condition (not out of the while)
    i = 0
    cnt = 0
    while i < 5
        i = i + 1
        switch i
        case 3
            continue    ; jumps to while condition check, skipping cnt++
        end
        cnt = cnt + 1   ; runs for i=1,2,4,5 but NOT i=3
    end
    if cnt == 4
        result = result + 1     ; 1: continue skipped cnt++ on i=3 iteration
    end
    if i == 5
        result = result + 1     ; 2: while ran to completion (continue didn't exit it)
    end

    ; --- checks 3,4: continue inside switch inside repeat targets the repeat condition ---
    ; repeat runs k=1..5; on k==2 the switch fires continue which goes to until k==5
    k = 0
    cnt = 0
    repeat
        k = k + 1
        switch k
        case 2
            continue    ; jumps to [until k==5], skipping cnt++
        end
        cnt = cnt + 1   ; runs for k=1,3,4,5 but NOT k=2
    until k == 5
    if cnt == 4
        result = result + 1     ; 3: continue skipped cnt++ on k=2 iteration
    end
    if k == 5
        result = result + 1     ; 4: repeat ran to its until-condition
    end
end
