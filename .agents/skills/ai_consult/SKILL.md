---
name: ai-consult
description: Automate code generation, bug fixing, and surgical refactoring by consulting external models (GLM 5.2 / DeepSeek V4 Pro) and automatically patching local source files while significantly reducing native agent context token consumption.
---

# Skill: ai-consult

This skill instructs you (the IDE agent) on how to delegate complex coding, debugging, or optimization tasks to a more powerful external consultant model (e.g., `nvidia/deepseek-ai/deepseek-v4-pro` or `nvidia/z-ai/glm-5.2` via `walkie`). This lets the CLI program patch the local codebase automatically using the built-in `consult` command.

**CRITICAL ADVANTAGE**: Delegating tasks via this skill is proven to save significant internal context tokens by eliminating exponential context bloat and prevents cognitive context drift. 

## Execution Workflow

### Step 1: Health Check (Optional)
Before starting, ensure your API connection is valid using the cached health check. This prevents wasting time on timeouts:
`ash
walkie health
`

### Step 2: Map the Workspace (Optional but Recommended)
Before executing complex changes, generate a lightweight context index of the project to understand dependencies instantly without reading massive files:
```bash
walkie map
```
This generates a highly compressed `llm_context.yaml` and `.walkie/symbols_index.json`.

### Step 3: Target the Issue
Identify the target source file that needs modification. If modifying a large file (>200 lines), identify the precise `start-end` line numbers for the change to drastically cut token costs.

### Step 4: Delegate and Patch
Use the automated `walkie consult` command to request modifications and patch the file directly.

```bash
# Example 1: Localized Edit (Maximum Token Efficiency)
walkie consult path/to/target.py --task "Add verify_checksum method" -L 100-150 -m nvidia/z-ai/glm-5.2

# Example 2: Critical Refactoring with Verification & Chaining
walkie consult path/to/target.py --task "Refactor route_model to handle fallback logic" -c nvidia/deepseek-ai/deepseek-v4-pro -V zenmux/x-ai/grok-4.5-free
```

### Parameters Guide
* `FILE` (argument): The path of the target file to edit.
* `--task` / `-t` (required): Precise description of the changes required.
* `--model` / `-m` (optional): The primary coder model (defaults to `nvidia/z-ai/glm-5.2`).
* `--line-range` / `-L` (optional): Line range (`start-end`). Slicing extracts *only* that section (plus a buffer) and automatically injects a `ContextPacket` via the AST indexer, ensuring the model knows global scope context without paying for full file tokens.
* `--chain-model` / `-c` (optional): Pass the result to another model sequentially for refinements.
* `--verify-model` / `-V` (optional): An independent auditor model to double-check the final patch for logic bugs or hallucinated variables before writing to disk.
* `--no-experience` (optional): Disable the automatic caching and injection of lessons from past errors.
* `--attach` / `-a` (optional): Attach extra files (e.g. screenshots or stack traces).

### Self-Correcting Features
LWT handles delimiters cleanly. If a patch fails syntax compilation (`python -m py_compile`), fails regex parsing, or fails the auditor verify (`-V`), LWT executes a self-correcting retry loop entirely inside its subprocess, sparing you from wasting any internal context tokens on error logs!
