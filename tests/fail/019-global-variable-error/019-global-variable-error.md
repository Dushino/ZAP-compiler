# Test 010 Error: Variable Scope

## Expected Error
Variable from one procedure scope used in another procedure scope.

## Error Details
- Variable x declared in main() procedure
- Variable x referenced in helper() procedure
- Should produce: "Variable x is not defined in this scope"
- Error clearly indicates variable is local to another scope
