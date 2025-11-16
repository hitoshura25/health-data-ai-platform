# /spec-only - Create specification document only (no implementation)

## Usage
/spec-only <feature_description>

## Description
Creates a detailed specification document for a feature without implementing it. Uses the Gemini MCP Server to gather facts about the codebase and validate the specification for completeness.

## Steps
1. Use `query_codebase_tool` to gather facts about relevant codebase areas
2. Create detailed specification document using the facts
3. Use `validate_against_codebase_tool` to check completeness
4. Address any validation issues
5. Save specification to specs/ directory

## Example
/spec-only Add user authentication with OAuth2 support
