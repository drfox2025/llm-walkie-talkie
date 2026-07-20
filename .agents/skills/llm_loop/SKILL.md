---
name: llm-loop
description: Run a goal-driven, multi-LLM, design-governed looping engine with sandbox isolation and design contract validation.
---

# Skill: llm-loop

Use this skill when you want to achieve a complex, design-critical code implementation or repair task. The skill runs a convergent loop with a native Implementer, an external Auditor, and an external Red Team critic to guarantee conformance to code correctness and Design Contract tokens.

## Instructions

0. **Verify Connections to External LLMs First (Run once per session)**:
   - Before executing the loop, check provider connectivity and credentials to ensure they are active:
     ```bash
     walkie status                      # Check active providers
     walkie status --sweep              # Live latency probe (if connection issues suspected)
     ```
   - After verifying connections, **read** `~/.walkie/verified_models.json` to understand which models are alive and their capability tiers.
   - If the user specifies informal model names (e.g., "GLM", "Grok", "Nemotron"), use `walkie resolve "<name>"` to get the correct full `model_id` for `--gen-model`, `--audit-model`, and `--redteam-model`.
   - **Strict Scope Rule**: Only use models the user explicitly requested. Do NOT probe or substitute additional models without user approval.

1. **Establish the Design Contract First**:
   - Before editing any code or UI components, ensure that a `theme.contract.yaml` exists in the workspace.
   - If one does not exist, establish the design variables (color scale, spacing scale, canonical component imports) and get approval before proceeding.

2. **Enforce the 3-Distinct-Vendor & Active Provider Rule**:
   - The loop will fail startup if less than 3 distinct model vendors (e.g. Gemini, OpenAI, Anthropic, DeepSeek, GLM) are configured.
   - Warm start checks will verify active credentials. Make sure `--gen-model`, `--audit-model`, and `--redteam-model` use providers that are fully configured to avoid connection issues.
   - **Operational Resilience Check:** A warning will trigger if all configured distinct-vendor models route through the same backend API provider (e.g. all on OpenRouter or all on NVIDIA NIM). To prevent Single Point of Failure (SPOF) outages, balance the model choices across multiple active providers (e.g. combining NVIDIA NIM, OpenRouter, and Google Gemini).
   - **Auto-Suggest Vendor-Diverse Selection:** If the user doesn't specify all 3 models, check the verified models manifest to auto-suggest a vendor-diverse combination:
     ```bash
     # View all verified models grouped by provider
     cat ~/.walkie/verified_models.json
     ```
     Pick the strongest model from each of 3 different providers. For example:
     - `--gen-model`: Best coding model from NVIDIA (e.g., `nvidia/z-ai/glm-5.2`)
     - `--audit-model`: Best reasoning model from ZENMUX (e.g., `zenmux/x-ai/grok-4.5-free`)
     - `--redteam-model`: Best model from OPENROUTER (e.g., `openrouter/nvidia/nemotron-3-ultra-550b-a55b:free`)

3. **Prioritize Sandbox Execution**:
   - Always run the loop inside a detached sandbox worktree to isolate modifications and allow safe rollbacks:
     ```bash
     walkie loop --goal "<task>" --stop-cmd "<test-command>" --design-contract theme.contract.yaml --gen-model <gen_model> --audit-model <audit_model> --redteam-model <redteam_model> --session <session_id>
     ```

4. **Mandatory Token & Cost Report**:
   - Every execution of the loop must produce a final transparent token count and estimated USD cost report, detailing per-model, per-role, and per-iteration breakdowns, clearly divided by the Native LLM (Implementer) and the External LLMs (Auditor & Red Team).

5. **Focus on the Local Project Codebase**:
   - Your primary target is to modify and implement changes directly within the local project files (e.g. backend, frontend, UI, logic, tests) in the workspace.
   - Do NOT try to connect to other LLMs, install API clients, or build mock LLM integrations unless the user's goal explicitly specifies it.
