---
name: ai-consult
description: Automate code generation, bug fixing, and surgical refactoring by consulting external models (GLM 5.2 / DeepSeek V4 Pro) and automatically patching local source files.
---

# Skill: ai-consult

This skill instructs you (the agent) on how to delegate complex coding, debugging, or optimization tasks to a more powerful external consultant model (e.g., `nvidia/deepseek-ai/deepseek-v4-pro` or `nvidia/z-ai/glm-5.2` via `walkie`), and let the CLI program patch the local codebase automatically using the built-in `consult` command.

## Execution Workflow

### Step 1: Analyze the Issue & Local Files
Identify the issue, compilation errors, or features requested. Locate the target source file that needs modification.

### Step 2: Delegate and Patch in One Command
Use the automated `walkie consult` command to request modifications and patch the file directly. This minimizes native agent token usage and lets the external LLM write 100% of the new code blocks.

```bash
walkie consult path/to/target_file.py --task "Task description of modifications" --model nvidia/z-ai/glm-5.2
```

### Parameters Guide
* `FILE` (argument): The path of the target file to edit.
* `--task` / `-t` (required): Precise description of the changes required.
* `--model` / `-m` (optional): The model to query (defaults to `nvidia/z-ai/glm-5.2`).
* `--attach` / `-a` (optional): Attach extra files (e.g. screenshots, error reports, or secondary code context files).
* `--dry-run` (optional): Verify target code matches and compiles the patch without modifying the file.

### Delimiter Pattern Handled Natively
The CLI program automatically prompts the external model to output changes in the following format, parses the result, and modifies the file on disk:
```
<<<< REPLACEMENT_START >>>>
[exact original code blocks to match]
==== REPLACEMENT_WITH ====
[new replacement code blocks]
<<<< REPLACEMENT_END >>>>
```
If the external model deviates slightly in formatting (e.g., mismatching delimiters or angle bracket counts), the built-in parser uses a robust regex to align and apply the matches.
