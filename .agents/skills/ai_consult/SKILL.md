---
name: ai-consult
description: Automate code generation, bug fixing, and surgical refactoring by consulting external models (GLM 5.2 / DeepSeek V4 Pro / Qwen3 Coder) and automatically patching local source files while significantly reducing native agent context token consumption. Includes smart model discovery with cross-provider failover routing.
---

# Skill: ai-consult

This skill instructs you (the IDE agent) on how to delegate complex coding, debugging, or optimization tasks to a more powerful external consultant model via `walkie`. This lets the CLI program patch the local codebase automatically using the built-in `consult` command.

**CRITICAL ADVANTAGE**: Delegating tasks via this skill is proven to save significant internal context tokens by eliminating exponential context bloat and prevents cognitive context drift.

---

## Discovering Available Free Models (Run Once Per Session)

Before selecting a model, run discovery to get the **live** list of free coding models:
```bash
walkie discover --coding-only
```

This lists all free coding models with context lengths, provider routes, and tags. Pick the best model based on:
- **Context length**: Prefer ≥262K for large file refactoring
- **Tags**: Prefer models tagged `coding` + `reasoning`
- **Routes**: Models with 2+ routes have automatic failover

For JSON output (programmatic use): `walkie discover --coding-only --json-output`
To bypass 24h cache: `walkie discover --coding-only --force`

**All discovered free models** require only a free API key from their provider (no credit card).

*(Note: Free models are optimized for single-call 'consult' operations. To run a 'loop', ensure you use 3 distinct model vendors to satisfy the Start Guard.)*

---

## Pre-Flight: Ensuring Provider Connectivity

Before attempting any `walkie consult` or `walkie ask` command, check if at least one provider is configured:

```bash
walkie status
```

If ALL providers show `[GREY] No key`, guide the user through setup:

1. **Recommend the fastest path**: Tell the user:
   *"You need at least one free API key. The fastest option is OpenRouter — it gives you access to 50+ free models with no credit card required."*

2. **Run the quickstart wizard**:
   ```bash
   walkie quickstart
   ```

3. **If the user wants more providers**: Run the full setup:
   ```bash
   walkie setup --provider nvidia      # For NVIDIA NIM (40 RPM free tier)
   walkie setup --provider zenmux      # For ZenMux (GLM 5.2 access)
   walkie setup --provider groq        # For Groq (ultra-low latency)
   walkie setup --provider openrouter  # For OpenRouter (50+ free models)
   ```

4. **After setup succeeds**: Run discovery to confirm available models:
   ```bash
   walkie discover --coding-only
   ```

**IMPORTANT**: Never assume a provider is configured. Always check `walkie status` output before your first `consult` call in a session. If the status shows unconfigured providers, proactively inform the user which free options are available.

---

## Execution Workflow

### Step 0: Design Contract Setup (UI Tasks)
If the task involves modifying or building user interface (UI) components:
- Check if `theme.contract.yaml` exists.
- If it does not exist, force the creation of one, define the semantic color/spacing scales, and obtain user consent before proceeding.
- All subsequent `walkie consult` calls on UI files must adhere to the design tokens.

### Step 0.5: Health Check + Model Discovery (Run once per session)

Check all provider connections and see all available free models:
```bash
walkie health                      # Quick cached health check
walkie status                      # Full provider dashboard (uses cache)
walkie status --sweep              # Live probe all providers (slow, ~30s)
walkie discover --coding-only      # List all free coding models + failover routes
walkie discover --coding-only --force   # Force fresh scan (bypass 24h cache)
```

### Step 1: Map the Workspace (Optional but Recommended)

Before executing complex changes, generate a lightweight context index:
```bash
walkie map
```
This generates a highly compressed `llm_context.yaml` and `.walkie/symbols_index.json`.

### Step 2: Target the Issue

Identify the target source file that needs modification. If modifying a large file (>200 lines), identify the precise `start-end` line numbers for the change to drastically cut token costs.

### Step 3: Delegate and Patch

Use the automated `walkie consult` command to request modifications and patch the file directly.

```bash
# Example 1: Best free coder (Qwen3 Coder, 1M context)
walkie consult path/to/target.py --task "Add verify_checksum method" -L 100-150 \
  -m openrouter/qwen/qwen3-coder:free

# Example 2: GLM 5.2 on NVIDIA (existing default, 1M context)
walkie consult path/to/target.py --task "Add verify_checksum method" -L 100-150 \
  -m nvidia/z-ai/glm-5.2

# Example 3: Chain Qwen3 Coder → DeepSeek V4 Pro with verification
walkie consult path/to/target.py --task "Refactor route_model to handle fallback logic" \
  -m openrouter/qwen/qwen3-coder:free \
  -c nvidia/deepseek-ai/deepseek-v4-pro \
  -V zenmux/x-ai/grok-4.5-free

# Example 4: Use canonical short name (auto-resolves to best available route)
walkie consult path/to/target.py --task "Fix edge case in session handling" \
  -m nvidia/z-ai/glm-5.2

# Example 5: General ask query using top free model
walkie ask -m openrouter/qwen/qwen3-coder:free --prompt "Explain this function"
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

---

## Discovery & Failover System

LWT now includes a smart model discovery engine (`discovery.py`) that:

1. **Fetches** free model lists from OpenRouter and NVIDIA NIM APIs
2. **Groups** the same underlying model available from multiple providers into one logical entry
3. **Elects** a primary route by latency + reliability (EWMA after ≥5 samples, provider priority order before that)
4. **Fails over** automatically to backup routes on 429/5xx/timeout errors
5. **Caches** the registry for 24h in `~/.walkie/model_registry.json`

### Provider Priority Order (when no EWMA data yet)
`NVIDIA → ZENMUX → OPENROUTER → GROQ → GEMINI → OPENAI → ANTHROPIC`

### Key Registry Commands
```bash
walkie discover                    # Scan all providers for free models
walkie discover --coding-only      # Filter to coding/reasoning models only
walkie discover --provider nvidia  # Scan only NVIDIA
walkie discover --json-output      # JSON output for programmatic use
walkie discover --force            # Bypass 24h TTL cache
walkie status                      # Health dashboard for all providers
walkie status --sweep              # Live probe each provider
walkie setup                       # Configure API keys (includes NVIDIA wizard)
```

---

## Native LLM Evolution (Agent Self-Improvement)

The IDE agent can self-modify its customizations (global rules, workspace instructions, etc.) every time it learns something new. This is done by consulting an external LLM to critique its Chain of Thought (CoT) and inject a new, permanent rule.

### Workflow for the Native Agent:
When you (the agent) execute a complex task and realize you made an inefficiency, or you discover a new optimized workflow:
1. **Pre-summarize your CoT** into a tight JSON string describing: `{"task": "...", "tools_used": [...], "actions_taken": [...], "final_cot_summary": "...", "self_assessment": "..."}`
2. **Call `walkie evolve`**:
   ```bash
   walkie evolve --context '{"task": "Fix login bug", "self_assessment": "I wasted time reading the whole file instead of grepping for the login route."}'
   ```
   *Note: You can also write the JSON to a temporary file in `scratch/` and pass `--context scratch/my_cot.json` to avoid shell escaping issues.*
3. **Report to User**: Always notify the user that you have updated your rules via `walkie evolve`. Show them the output (the critique and the injected rule).

If a newly injected rule breaks your workflow in a future task, you can always rollback using the backup path provided in the output, or by listing backups:
```bash
walkie evolve-restore
```

---

## Self-Correcting Features

LWT handles delimiters cleanly. If a patch fails syntax compilation (`python -m py_compile`), fails regex parsing, or fails the auditor verify (`-V`), LWT executes a self-correcting retry loop entirely inside its subprocess, sparing you from wasting any internal context tokens on error logs!

## Security

All API key prefixes (`nvapi-`, `sk-`, `AIzaSy`, `sk-ant-`, `sk-or-`) are automatically masked before being written to any log file.
