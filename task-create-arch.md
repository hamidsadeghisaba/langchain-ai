# Task: Analyze the Project and Create Architect.md

## Objective

Analyze the existing codebase thoroughly and create an `Architect.md` file in the project root.

The purpose of this document is to provide AI coding agents with a reliable understanding of the project's architecture, components, dependencies, design decisions, and implementation conventions before they start modifying the codebase.

The document must describe the **actual architecture implemented in the code**, not an idealized or proposed architecture.

## 1. Analyze Before Writing

Before creating `Architect.md`, inspect the project systematically.

Start by examining:
- Project directory structure.
- Existing documentation, including `README.md`, `AGENTS.md`, and other Markdown files.
- Build and dependency configuration files.
- Application entry points and bootstrap configuration.
- Main modules, packages, and their responsibilities.
- Core business logic and important workflows.
- Internal dependencies and relationships between modules.
- External services, databases, APIs, and messaging systems.
- Configuration management and environment-specific settings.
- Authentication, authorization, and security mechanisms.
- Error handling, logging, and exception management.
- Testing structure and testing conventions.
- Existing architectural patterns and coding conventions.

Follow references from entry points to the important components they invoke. Do not limit the analysis to filenames, directory names, or dependency declarations.

Use code search, symbol references, call hierarchies, and existing project-analysis tools when available and useful.

If a Graphify MCP server or another codebase knowledge tool is available, use it to understand relationships between components. Verify important conclusions against the actual source code.

## 2. Required Content of Architect.md

Organize the document into the following sections, adapting them to the technologies and architecture actually found in the repository.

### 2.1. Project Overview
- Project purpose and business domain.
- Main capabilities.
- Application type and architectural style.
- Primary technologies and frameworks.

### 2.2. High-Level Architecture
- Main architectural components.
- Responsibilities of each component.
- How the components interact.
- Architectural boundaries and dependency directions.

Include a Mermaid diagram if it meaningfully clarifies the architecture.

### 2.3. Project Structure
Explain the purpose of important directories, modules, and packages.

Focus on architectural responsibilities rather than listing every file.

### 2.4. Core Components
For each important component, document:
- Its responsibility.
- Its public interfaces or entry points.
- Its dependencies.
- The components that depend on it.
- Its role in important business workflows.

Reference actual class names, functions, modules, or files whenever possible.

### 2.5. Important Workflows
Describe the most important execution flows step by step.

For example:
- Application startup.
- Main business operations.
- API request processing.
- Database interactions.
- Background jobs and asynchronous processing.
- External service integration.

Include sequence diagrams where they provide meaningful architectural insight.

Only document workflows that actually exist in the project.

### 2.6. Data Architecture
Document:
- Main domain entities and data models.
- Database access patterns.
- Repository or persistence layers.
- Important relationships between entities.
- Transaction management.
- Data migration mechanisms, if present.

Do not reproduce the entire database schema. Focus on architectural relationships.

### 2.7. API and Integration Architecture
Describe:
- API structure and routing conventions.
- Important endpoints or interfaces.
- Request and response models.
- External integrations.
- Communication protocols.
- Integration boundaries and relevant constraints.

### 2.8. Configuration and Security
Document:
- Configuration sources and precedence, where verifiable.
- Environment-specific configuration.
- Secret-management mechanisms without exposing secret values.
- Authentication and authorization architecture.
- Security-related architectural constraints.

Never include credentials, access tokens, private keys, or other secrets in the document.

### 2.9. Error Handling and Observability
Describe:
- Exception-handling strategy.
- Error propagation and API error responses.
- Logging architecture.
- Monitoring, tracing, and metrics, if implemented.

### 2.10. Testing Architecture
Explain:
- Unit, integration, and end-to-end testing approaches.
- Test directory structure.
- Test fixtures and infrastructure.
- Important testing conventions.
- How the project isolates external dependencies during tests.

### 2.11. Architectural Patterns and Conventions
Identify patterns actually used in the codebase, such as:
- Layered architecture.
- Hexagonal architecture.
- Dependency injection.
- Repository pattern.
- Strategy pattern.
- Event-driven architecture.
- Other relevant patterns.

Do not claim that a pattern is used merely because its name appears in a dependency or class name.

### 2.12. Guidelines for Future Code Changes
Provide actionable instructions for future AI coding agents.

Explain:
- Where new functionality of different types should be implemented.
- Which existing components should be extended rather than duplicated.
- How dependencies between modules should be maintained.
- Which interfaces or contracts must remain compatible.
- Which project conventions must be followed.
- Which areas are particularly sensitive to changes.
- Which tests should be executed after changes to important components.

These guidelines must be derived from the existing implementation and established project conventions.

### 2.13. Known Limitations and Uncertainties
Document architectural limitations, inconsistencies, and unresolved questions discovered during analysis.

Clearly distinguish between:
- Verified facts.
- Reasonable inferences.
- Unknown or unverified behavior.

Do not invent missing information.

## 3. Evidence and Accuracy Requirements

Follow these rules strictly:

1. Base architectural statements on source code, configuration, or existing documentation.
2. Reference relevant source paths and important class or function names.
3. Prefer precise explanations over generic architectural descriptions.
4. Do not assume that a dependency is actively used just because it is declared.
5. Do not describe planned or intended functionality as implemented functionality.
6. Do not invent endpoints, components, database tables, integrations, or execution flows.
7. If a detail cannot be verified, explicitly mark it as unknown or unverified.
8. Resolve contradictory documentation against the implementation when possible, and document significant discrepancies.
9. Avoid excessive detail that will make the document difficult to maintain.
10. Never include secrets or sensitive runtime values.

## 4. Scope and Repository Safety

This is a documentation-only task.

- Create or update only `Architect.md` in the project root.
- Do not modify application source code.
- Do not modify tests, build files, dependencies, configuration files, database schemas, or migrations.
- Do not install packages or introduce new dependencies.
- Do not reformat or rewrite existing files.
- Do not create commits or push changes.
- Preserve all pre-existing user changes.

If `Architect.md` already exists, inspect it first and update it based on the current implementation. Preserve valid information and correct outdated or inaccurate statements.

## 5. Quality Requirements

The final document must be:
- Accurate and grounded in the codebase.
- Structured for easy navigation.
- Useful to AI coding agents working on future tasks.
- Specific to this project rather than a generic architecture template.
- Concise enough to remain maintainable while covering important architectural details.

Use Mermaid diagrams selectively. Ensure diagram relationships are supported by the implementation.

Do not fill sections with generic explanations merely to satisfy the outline. If a section is not applicable, omit it or briefly explain why.

## 6. Final Verification

After writing `Architect.md`:

1. Review every major architectural claim against the source code.
2. Verify referenced paths and important class or function names.
3. Check Mermaid syntax and internal consistency.
4. Ensure the document does not contain secrets.
5. Run `git diff --check`.
6. Inspect `git diff` and confirm that only `Architect.md` was changed by this task.
7. Do not discard, overwrite, or revert unrelated pre-existing changes.

## Final Response

When finished, report:
- The location of `Architect.md`.
- The major architectural areas documented.
- The most important source locations inspected.
- Any significant uncertainties or limitations.
- Confirmation that no application code or configuration was modified.
- Any verification checks that could not be completed.

Begin by inspecting the repository. Do not ask the user to manually describe the architecture when the information can be discovered from the codebase.
