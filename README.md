# Dotnet Code Review AI Agent (Lightweight Enhancements)

## Purpose
The **Dotnet Code Review AI Agent** is designed to review small-to-medium .NET enhancements (typically **< 20 person-days of effort**), with a common change size of **50–200 LOC** (but it can scale beyond that when needed). It focuses on practical, fast feedback that improves quality, maintainability, and safety without blocking delivery.

## What the agent can do
### 1. Code quality checks
- Flag common C# code smells (overly long methods, deep nesting, magic numbers, unused code).
- Recommend refactoring for readability and testability.
- Identify poor exception handling and missing null checks.

### 2. API & design review
- Verify public API changes follow consistent naming conventions and REST or gRPC patterns.
- Catch breaking changes in interfaces, DTOs, or contracts.
- Ensure dependency inversion and DI usage follow established project practices.

### 3. Performance and scalability
- Highlight inefficient LINQ usage, repeated enumerations, or unnecessary allocations.
- Identify potential async/await misuses and blocking calls.
- Point out hot paths that might need caching or batching.

### 4. Security & compliance checks
- Detect potential injection risks (SQL, logging, HTTP headers).
- Check for unsafe string handling or missing input validation.
- Verify secrets/configuration are not hard-coded.

### 5. Testing and coverage guidance
- Ensure new logic includes unit/integration tests.
- Suggest boundary and negative tests for new behavior.
- Flag brittle tests or gaps in coverage.

### 6. Style and consistency
- Ensure formatting aligns with .editorconfig and analyzer rules.
- Check consistency with existing project conventions.
- Highlight missing XML documentation for public APIs (if required).

## How the agent works
### Inputs
- Pull request or patch diff.
- Project conventions (README, coding standards, .editorconfig, analyzers).
- Optional: architecture notes, service-level objectives, or risk areas.

### Review process
1. **Scope detection**: Determine if change is within the “<20 person-days” enhancement bucket.
2. **Change classification**: Identify modified areas (e.g., controllers, services, DTOs, tests).
3. **Rule-based checks**: Run static rules for C# idioms and .NET best practices.
4. **Contextual review**: Compare against existing project patterns.
5. **Risk scoring**: Assign a risk level (Low/Medium/High) based on change size and area.
6. **Actionable feedback**: Provide targeted comments and fix suggestions.

## Output format (example)
**Summary**
- Scope: Small enhancement (<20 PD)
- Risk: Medium
- Files changed: 6 (approx. 140 LOC)

**Key Findings**
1. `OrderService.cs`: Consider extracting validation logic into a dedicated validator for reusability.
2. `OrderController.cs`: Avoid synchronous `.Result` on async calls; use `await`.
3. `OrderRepository.cs`: Repeated enumerations on LINQ query; cache results.

**Testing Guidance**
- Add unit tests for null/empty order requests.
- Add integration test for invalid order ID response.

## Example use cases
- **Feature tweak**: Review a new flag added to a controller and service.
- **Bug fix**: Validate a logic change in a repository query.
- **Refactor**: Ensure a refactor maintains behavior and test coverage.

## What it will not do
- It does not replace full architectural review for large initiatives.
- It will not approve changes that introduce security risks.
- It does not implement code changes by default; it focuses on feedback.

---
**Outcome:** The agent delivers fast, structured, and actionable feedback for small-to-medium .NET enhancements while keeping reviews lightweight and aligned with project standards.
