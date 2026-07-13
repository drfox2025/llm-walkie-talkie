---
name: llm-loop
description: Run a goal-driven, multi-LLM, design-governed looping engine with sandbox isolation and design contract validation.
---

# Skill: llm-loop

Use this skill when you want to achieve a complex, design-critical code implementation or repair task. The skill runs a convergent loop with a native Implementer, an external Auditor, and an external Red Team critic to guarantee conformance to code correctness and Design Contract tokens.

## Instructions

1. **Establish the Design Contract First**:
   - Before editing any code or UI components, ensure that a `theme.contract.yaml` exists in the workspace.
   - If one does not exist, establish the design variables (color scale, spacing scale, canonical component imports) and get approval before proceeding.

2. **Enforce the 3-Distinct-Vendor & Active Provider Rule**:
   - The loop will fail startup if less than 3 distinct model vendors (e.g. Gemini, OpenAI, Anthropic, DeepSeek, GLM) are configured.
   - Warm start checks will verify active credentials. Make sure `--gen-model`, `--audit-model`, and `--redteam-model` use providers that are fully configured to avoid connection issues.

3. **Prioritize Sandbox Execution**:
   - Always run the loop inside a detached sandbox worktree to isolate modifications and allow safe rollbacks:
     ```bash
     walkie loop --goal "<task>" --stop-cmd "<test-command>" --design-contract theme.contract.yaml --gen-model <gen_model> --audit-model <audit_model> --redteam-model <redteam_model> --session <session_id>
     ```

4. **Mandatory Token & Cost Report**:
   - Every execution of the loop must produce a final transparent token count and estimated USD cost report, detailing per-model, per-role, and per-iteration breakdowns, clearly divided by the Native LLM (Implementer) and the External LLMs (Auditor & Red Team).

