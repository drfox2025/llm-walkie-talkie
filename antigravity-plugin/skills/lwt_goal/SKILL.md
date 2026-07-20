---
name: lwt-goal
description: Goal-oriented Native Agent utilizing the LLM Walkie-Talkie sandbox and auto-generated oracle validation.
---

# Skill: lwt-goal

Use this skill to execute a task using the advanced LLM Walkie-Talkie (LWT) concepts: sandbox isolation and oracle-based stopping, but driven entirely by YOU (the Native Agent) instead of an external LLM API caller.

## Instructions for Native Agent

When the user triggers this skill (e.g., via `/lwt-goal <task>` or mentioning the skill), you **MUST STRICTLY** follow these steps in a Plan-Do-Check-Act (PDCA) loop.

1. **Auto-Oracle Generation (Plan)**:
   - Analyze the user's task.
   - If the user explicitly provided a `--stop-cmd` (e.g., `npm run test`), note it.
   - If NOT, you must **automatically write a validation script** (e.g., `oracle_test.py` or `oracle_test.sh`) tailored to the user's context that will return an exit code of `0` when the task is successfully completed, and `1` otherwise.
   - Example: If the task is to audit a program in 10 perspectives into `audit_report.md`, write a python script that reads the file and ensures it is > 500 words and contains 10 distinct sections.

2. **Sandbox Provisioning (Plan)**:
   - Run the command to create an isolated workspace:
     ```bash
     python walkie.py sandbox --create
     ```
   - Capture the output path (this is your sandbox directory).

3. **Native Looping (Do & Check)**:
   - From this point forward, perform all file edits and test executions INSIDE the sandbox directory (by passing `cwd=<sandbox_path>` to all your terminal commands and using the absolute paths to the sandbox files).
   - Do NOT edit the main host directory files yet!
   - Make your code changes in the sandbox.
   - Run the Oracle command (or your auto-generated script) in the sandbox.
   - If the Oracle fails (exit code != 0), read the error, patch the code in the sandbox again, and repeat until the Oracle passes.

   **CRITICAL — Sandbox CWD Fix**: When generating scripts to run inside the sandbox, ALL Python scripts MUST begin with:
   ```python
   import os
   os.chdir(os.path.dirname(os.path.abspath(__file__)))
   ```
   This ensures correct CWD regardless of how the host shell invokes the script. The `run_command` tool's `Cwd` parameter may not apply to paths outside the workspace root.

   **CRITICAL — Syntax Validation Gate**: Before executing any auto-generated script for the first time, validate it:
   ```bash
   python -m py_compile <script_path>
   ```
   If compilation fails, fix the syntax error before proceeding. Never run unvalidated generated code.

   **Smart Model Resolution**: If the user requests consultation with external models by informal name (e.g., "GLM", "Grok"), use `walkie resolve "<name>"` to determine the correct full model_id before making any API calls. See the `ai-consult` skill for detailed resolution rules.

4. **Final Commit & Teardown (Act)**:
   - Once the Oracle script returns an exit code of `0` (Success!), you must merge the changes back to the live workspace.
   - Run the commit command:
     ```bash
     python walkie.py sandbox --commit <sandbox_path>
     ```
   - This command will safely sync your changes back to the root directory and destroy the temporary sandbox.
   - **CRITICAL**: The `sandbox --commit` command MUST be the **absolute last action**. After commit, the sandbox is destroyed — you cannot re-run tests in it. Never commit before the oracle passes.

5. **Post-Mortem Reporting**:
   - Provide a final summary to the user detailing what you changed in the sandbox, how many attempts it took for the Oracle to pass, and confirming that the changes have been committed.

