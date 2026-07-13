---
name: ai-consult
description: Automate code generation, bug fixing, and surgical refactoring by consulting external models (GLM 5.2 / DeepSeek V4 Pro / Qwen3 Coder) and automatically patching local source files while significantly reducing native agent context token consumption. Includes smart model discovery with cross-provider failover routing.
---

# Skill: ai-consult

This skill instructs you (the IDE agent) on how to delegate complex coding, debugging, or optimization tasks to a more powerful external consultant model via `walkie`. This lets the CLI program patch the local codebase automatically using the built-in `consult` command.

**CRITICAL ADVANTAGE**: Delegating tasks via this skill is proven to save significant internal context tokens by eliminating exponential context bloat and prevents cognitive context drift.

---

## Top 3 Free Coding Models (Live-Discovered, July 2026)

These are the best available models confirmed via `walkie discover --coding-only`:

| # | Canonical Name | Full Model ID | Context | Tags | Routes |
|---|---|---|---|---|---|
| 1 | `qwen3-coder` | `openrouter/qwen/qwen3-coder:free` | **1048K** | coding, reasoning | OpenRouter |
| 2 | `laguna-m.1` | `openrouter/poolside/laguna-m.1:free` | 262K | coding, reasoning | OpenRouter |
| 3 | `nemotron-3-ultra-550b-a55b` | `openrouter/nvidia/nemotron-3-ultra-550b-a55b:free` | **1000K** | reasoning | OpenRouter + NVIDIA |

**All 3 are FREE** — they require only an `OPENROUTER_API_KEY` (free at https://openrouter.ai/keys).

**Multi-route bonus**: `qwen3-next-80b-a3b` and `gpt-oss-120b` are also available on BOTH OpenRouter and NVIDIA NIM simultaneously — the failover system will automatically use both.

---

## Execution Workflow

### Step 0: Health Check + Model Discovery (Run once per session)

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

## Self-Correcting Features

LWT handles delimiters cleanly. If a patch fails syntax compilation (`python -m py_compile`), fails regex parsing, or fails the auditor verify (`-V`), LWT executes a self-correcting retry loop entirely inside its subprocess, sparing you from wasting any internal context tokens on error logs!

## Security

All API key prefixes (`nvapi-`, `sk-`, `AIzaSy`, `sk-ant-`, `sk-or-`) are automatically masked before being written to any log file.
