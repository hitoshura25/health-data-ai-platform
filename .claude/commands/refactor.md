# /refactor - Refactor existing code

## Usage
/refactor <refactoring_description>

## Description
Refactors existing code following best practices: analyze, plan, validate, execute, and verify.

## Steps
1. Analyze current implementation using `trace_feature_tool`
2. Create refactoring specification
3. Validate plan with `check_consistency_tool`
4. Execute refactoring incrementally
5. Verify with tests and validation

## Example
/refactor Extract authentication logic into separate service
