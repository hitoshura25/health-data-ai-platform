# Specification-Only Workflow

## Purpose
Create a detailed specification document without implementation.

## Steps

### 1. Gather Facts
Use `query_codebase_tool` to collect factual information:
- Existing patterns and conventions
- Related components and their interfaces
- Dependencies and integration points
- Current architecture decisions

### 2. Create Specification
Write a comprehensive specification including:
- Problem statement and goals
- Technical design and architecture
- API contracts and interfaces
- Data models and schemas
- Integration points
- Security considerations
- Testing strategy

### 3. Validate Specification
Use `validate_against_codebase_tool` with checks:
- missing_files
- undefined_dependencies
- pattern_violations
- completeness

### 4. Refine and Iterate
Address validation issues:
- Add missing details
- Resolve inconsistencies
- Clarify ambiguities
- Update based on codebase facts

### 5. Save Specification
Save to `specs/` directory with descriptive filename.
