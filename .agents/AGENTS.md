# Workspace Rules & Conventions

## 1. Strict 3-Round Plan-Do-Check-Act (PDCA) Workflow
For every user query or request, the agent must execute at least **3 distinct rounds** of the Plan-Do-Check-Act (PDCA) loop, with a clear review or feedback transition step connecting each round:
- **Round 1 (Planning & Research)**: Research the request, outline the initial approach, run background explorations or consultations, and review the raw results.
- **Round 2 (Patching & Verification)**: Formulate the implementation plan, apply code fixes or improvements, verify syntactical and logical correctness (e.g. running tests/compilation), and review the outcomes.
- **Round 3 (Packaging & remote Sync)**: Build/sync packaging distributions (like zip archives or subfolders), commit and push to remote repositories, run a final validation check, and update walkthrough logs.
- *Exception*: Only bypass or exceed this if specifically requested by the user.

## 2. Sequential Multi-Model Consultation Chain
When the user has configured at least 2 model APIs:
- Do not run model consultations in parallel if a sequential chain is requested or needed.
- Query the models sequentially: feed the prompt to Model A, capture Model A's output, and attach Model A's output as context/prompt additions when querying Model B.

## 3. Mandatory Task Tracking Table
For EVERY multi-step task, background job, or response that involves more than one action, the agent MUST include a **status tracking table** in its response. This rule is non-negotiable and applies to:
- All task execution responses (running commands, editing files, etc.)
- All consultation/research reports
- All background task status updates
- All PDCA round transitions

**Required table format** (adapt columns as needed):
```
| Step | Action | Status |
|------|--------|--------|
| 1    | Description of step | ✅ Done / ⏳ Running / 🔜 Pending / ❌ Failed |
```
Additional columns (e.g. Model, Output, Notes) may be added as appropriate.
The table must appear **prominently** in the response — not buried at the end. It is the first thing a user should be able to scan.

## 4. Vietnamese Language Rule
- If the user communicates in Vietnamese (or is identified as a Vietnamese speaker), the agent MUST respond **entirely in Vietnamese**.
- All **English technical terminology** (API names, parameter names, command names, library names, error codes, etc.) MUST be kept in their original English form and placed in **brackets** immediately after the Vietnamese translation: e.g. `Mô hình ngôn ngữ lớn (Large Language Model)`, `Bảng theo dõi (Tracking Table)`.
- This rule applies to: prose responses, artifact summaries, plan descriptions, task status tables, comments in code, and any other agent output visible to the user.
- English is always acceptable as a fallback if the agent is uncertain whether the user is a Vietnamese speaker.

## 5. General Best Practices
<!-- EVOLVE_SECTION: CODING -->
- When using search tools (grep, find) for standard refactoring tasks, you MUST exclude test files and directories (e.g., `*test*`, `tests/`, `__tests__/`) from your search scope unless the user explicitly requested work on tests.
- Follow PEP 8 guidelines for Python.
