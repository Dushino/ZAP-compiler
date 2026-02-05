; testing .warning and .info directives

.warning "This is a test warning"
.info "Some informational message"

word result @40000 = 0

proc main()

    .warning "This is another warning"
    .info "Info 2"
    result = $1234
    .warning "Warning #3"
    .info "Done"
end


