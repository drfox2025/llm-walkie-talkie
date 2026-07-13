# LLM Walkie-Talkie (IDE Agent Consultation CLI)

```text
 _      __      __  _______ 
| |     \ \    / / |__   __|
| |      \ \  / /     | |   
| |____   \ \/ /      | |   
|______|   \__/       |_|   
```

LLM Walkie-Talkie is a **secure**, lightweight, and token-efficient CLI tool **fully vibe coded** and specifically designed for the **Antigravity IDE Agent** and terminal users. 

It allows Antigravity to pass entire codebases, multi-file contexts, base64 multimodal attachments, and conversation logs securely to high-performing external LLM providers (ZenMux, NVIDIA NIM, OpenRouter, Anthropic, OpenAI) with **real-time streaming** and **automated surgical patching**. By offloading 80%+ of code generation and patching to these advanced external models, it dramatically minimizes the token costs of internal Antigravity models while keeping API keys isolated and protected.



---

## 🚀 Key Features

1. **Automated Surgical Patching (`walkie consult`)**: 
   - A built-in command that automates local refactoring.
   - It reads target source files, submits modification tasks to external models, receives replacement blocks, and patches the file on disk.
   - Employs a resilient regex parser to handle bracket fluctuations or minor format deviations from the model response.

2. **Real-time Streaming (`--stream`)**:
   - Supports real-time token delivery to terminal outputs. If `--json-output` is requested, it accumulates the stream and outputs a final, clean JSON response.

3. **Multimodal Base64 Image Support**:
   - Natively detects image file attachments (`.png`, `.jpg`, `.jpeg`, `.webp`, `.gif`).
   - Automatically base64-encodes them and builds standard multimodal payloads, making it fully compatible with visual reasoning models (Gemini, Fable).

4. **Agent Custom Skill Integration**:
   - Includes a pre-configured `.agents/skills/ai_consult/SKILL.md` file.
   - Allows agents to discover and trigger the `ai_consult` workflow automatically, delegating code modifications and reducing native token usage.

5. **Context-Aware Line-Aligned Truncation**:
   - Slices attachments to fit the selected model's context limit without breaking line boundaries or cutting code mid-line.
   - Logs detailed truncation metrics to `stderr`.

6. **Token Saving via Strip Comments**:
   - A robust, quote-safe lexical parser removes line and block comments (`#`, `//`, `/* */`) across Python, JS, TS, Rust, Go, SQL, HTML, and C-family languages while preserving string literals.

7. **Centralized & Secure Configuration**:
   - GUIDED interactive setup links to provider keys, masks inputs, checks structures, and enforces secure permissions (`0o600`).
   - Stores configuration globally in `~/.walkie/.env` to prevent credentials from being overwritten during package updates.

---

## 🔑 Fetching Free API Credentials

You do not need paid subscriptions to start consulting high-performing models. We recommend looking for free API keys from the following providers:

1. **ZenMux (GLM 5.2 / DeepSeek)**:
   - Visit [ZenMux](https://zenmux.ai) and sign up.
   - Under the developer section, generate a free API key which allows calling advanced models like GLM 5.2 and Fable.
   
2. **NVIDIA NIM Gateway**:
   - Visit [NVIDIA Build](https://build.nvidia.com).
   - Sign up to receive free NIM integration credits. You can generate an API key (`nvapi-...`) to access high-speed NIM gateway models like `z-ai/glm-5.2` or `deepseek-ai/deepseek-v4-pro`.

3. **OpenRouter (Free Tier Models)**:
   - Visit [OpenRouter API Keys](https://openrouter.ai/keys) and create a key.
   - You can query any OpenRouter model. Search for free models (those carrying the `:free` suffix) to run them at zero cost:
     - `openrouter/google/gemma-2-9b-it:free`
     - `openrouter/google/gemini-2.5-flash:free`
     - `openrouter/meta-llama/llama-3-8b-instruct:free`

---

## 📦 Installation & Setup

### Option 1: Automated setup script (Recommended)
Run the automated installation script, which installs the package dependencies, boots setup prompts for API keys, and copies the LWT Antigravity Plugin to your global config directory:
```bash
python install.py
```

### Option 2: Manual Installation & Setup

1. **Install standard package (globally or within your virtual environment)**:
   ```bash
   pip install .
   ```
   *For development/editable mode, use:*
   ```bash
   pip install -e .
   ```

2. **Configure API Keys**:
   Run the secure, guided installer:
   ```bash
   walkie setup
   ```

---

## 🔧 Usage

### Ask a prompt using the default model (`nvidia/z-ai/glm-5.2`):
```bash
walkie ask --prompt "Explain the concept of quantum computing."
```

### Stream response, attach code, and strip comments to save tokens:
```bash
walkie ask --model nvidia/anthropic/claude-opus-4.8 --prompt "Audit this code" --attach walkie.py --strip-comments --stream
```

### Automate surgical refactoring:
```bash
walkie consult walkie.py --task "Add a docstring to the main entry point" --model nvidia/z-ai/glm-5.2
```

### dry-run refactoring:
Verify matching blocks and inspect compiled changes side-by-side without modifying files on disk:
```bash
walkie consult main.py --task "Refactor login validation" --model zenmux/anthropic/claude-4-fable --dry-run
```

---

## 🛠️ Advanced Features & Commands

### 1. Dynamic Model Discovery (`walkie discover`)
Scans all configured providers (OpenRouter, NVIDIA NIM) to identify available free models on-demand.
```bash
walkie discover --coding-only      # List all free coding/reasoning models
walkie discover --provider nvidia  # List models from a specific provider
walkie status                      # Status dashboard of all connections
walkie status --sweep              # Live sweep latency and probe connectivity
```

* **Use Case:** Instantly query the system to find newly released free-tier models (e.g. `qwen3-coder:free` with 1M context or `laguna-m.1` built by poolside) to connect them as your primary coder.

### 2. Cross-Provider Failover Routing
LWT groups identical underlying models hosted across different providers. It automatically routes your requests to the best available route:
* **EWMA Metrics:** Elects routes based on Exponentially Weighted Moving Average (EWMA) latency and reliability (after 5 sample queries).
* **Automatic Failovers:** If OpenRouter returns `429 RateLimitError` or fails, the routing system instantly falls back to NVIDIA NIM or another provider hosting the model.

### 3. Native LLM Evolution (`walkie evolve` / `walkie evolve-restore`)
Enables the native IDE agent to self-modify its rulebooks (like `.agents/AGENTS.md`) and improve its behavior over time.
```bash
walkie evolve --context scratch/cot.json -m nvidia/z-ai/glm-5.2
```
* **The Critique Loop:** You feed a JSON abstract describing a recent task, your actions, and your self-assessment to an advanced external LLM.
* **Surgical Rule Insertion:** The external LLM returns a machine-readable JSON critique and suggested rule. LWT parses this, saves a timestamped backup of the rule file, and injects the new rule under target HTML comments (e.g., `<!-- EVOLVE_SECTION: CODING -->`).
* **Rollbacks:** If a rule causes unexpected behavior, instantly restore it:
  ```bash
  walkie evolve-restore                          # List all backups
  walkie evolve-restore AGENTS.md.20260713.bak   # Restore specific backup
  ```
* **Use Case:** Permanently correct bad agent behaviors (such as searching test directories during a standard refactoring task or forgetting to verify imports) on-the-fly.

---

## 🌐 Open VSX Marketplace Publishing Guide

To publish the packaged extension (`llm-walkie-talkie-1.0.0.vsix`) to the Open VSX Registry (used by Antigravity and VSCodium):

### Option A: Command Line Interface (CLI)
1. **Get an Access Token:**
   - Sign in to the [Open VSX Registry](https://open-vsx.org/).
   - Go to your profile settings and generate a Personal Access Token (PAT).
2. **Claim the Namespace:**
   - Ensure you have registered the namespace `drfox2025` (matching the `"publisher"` field in `package.json`).
3. **Publish:**
   - Execute the following command inside the `antigravity-plugin/` directory:
     ```bash
     npx ovsx publish llm-walkie-talkie-1.0.0.vsix -p <YOUR_OPEN_VSX_TOKEN>
     ```

### Option B: Manual Web Upload
1. Sign in to the [Open VSX Registry](https://open-vsx.org/).
2. Navigate to your publisher namespace page.
3. Click the **Upload Extension** button.
4. Select the compiled `llm-walkie-talkie-1.0.0.vsix` file from the `antigravity-plugin/` directory and upload it directly.

