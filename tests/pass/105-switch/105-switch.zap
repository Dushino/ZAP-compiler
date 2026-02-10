word result @40000 = 42

proc main()
    byte i 

    for i = 0 to 10
        switch i
            case 1
                result = result - 10
                break

            case 5
            case 4
                result = result + 2
                break

            case 9
                result = result + 3
                break       

            default
                result = result + 1
                break
        end
    end

end
