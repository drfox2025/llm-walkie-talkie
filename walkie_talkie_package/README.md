# LLM Walkie-Talkie (IDE Agent Consultation CLI)

```ansi
[34m__      __  _ _   _         [31m_______    _ _   _ [0m
[34m\ \    / / | | | (_)       [31m|__   __|  | | | (_)[0m
[34m \ \  / /  | | |  _ ___       [31m| |     | | |  _ [0m
[34m  \ \/ /   | | | | / _ \      [31m| |     | | | | |[0m
[34m   \  /    | | | |  __/       [31m| |     | | | | |[0m
[34m    \/     |_|_| |_|___|      [31m|_|     |_|_| |_|[0m
```

LLM Walkie-Talkie is a secure, light-weight, and highly token-efficient CLI tool **fully vibe coded** and specifically designed for the **Antigravity IDE Agent**. 

It allows Antigravity and terminal users to pass entire codebases, multi-file contexts, images, and user conversation logs directly to high-performing external LLM providers (ZenMux, NVIDIA NIM, OpenRouter, Anthropic, OpenAI). By offloading 80%+ of the generation and surgical code modifications to these advanced external models, it dramatically minimizes the token costs of internal Antigravity models.

---

## 🚀 Key Features

1. **Automated Surgical Patching (`walkie consult`)**: 
   - A built-in command that automates local refactoring.
   - It reads target source files, submits modification tasks to external models, receives replacement blocks, and patches the file on disk.
   - Employs a resilient regex parser to handle bracket fluctuations or minor format deviations from the model response.

2. **Multimodal Base64 Image Support**:
   - Natively detects image file attachments (`.png`, `.jpg`, `.jpeg`, `.webp`, `.gif`).
   - Automatically base64-encodes them and builds standard multimodal payloads, making it fully compatible with visual reasoning models (Gemini, Claude-4-Fable).

3. **Agent Custom Skill Integration**:
   - Includes a pre-configured `.agents/skills/ai-consult/SKILL.md` file.
   - Allows agents to discover and trigger the `ai-consult` workflow automatically, delegating code modifications and reducing native token usage.

4. **Context-Aware Line-Aligned Truncation**:
   - Slices attachments to fit the selected model's context limit without breaking line boundaries or cutting code mid-line.
   - Logs detailed truncation metrics to `stderr`.

5. **Token Saving via Strip Comments**:
   - A robust, quote-safe lexical parser removes line and block comments (`#`, `//`, `/* */`) across Python, JS, TS, Rust, Go, SQL, HTML, and C-family languages while preserving string literals.

6. **Real-time Streaming (`--stream`)**:
   - Supports real-time token delivery to terminal outputs. If `--json-output` is requested, it accumulates the stream and outputs a final, clean JSON response.

7. **Centralized Safe Configuration**:
   - GUIDED interactive setup links to provider keys, masks inputs, checks structures, and enforces secure permissions (`0o600`).
   - Stores configuration globally in `~/.walkie/.env` to prevent credentials from being overwritten during package updates.

---

## 🔑 Fetching Free API Credentials

You do not need paid subscriptions to start consulting high-performing models. We recommend looking for free API keys from the following providers:

1. **ZenMux (GLM 5.2 / DeepSeek)**:
   - Visit [ZenMux](https://zenmux.ai) and sign up.
   - Under the developer section, generate a free API key which allows calling advanced models like GLM 5.2 and Claude-4-Fable.
   
2. **NVIDIA NIM Gateway**:
   - Visit [NVIDIA Build](https://build.nvidia.com).
   - Sign up to receive free NIM integration credits. You can generate an API key (`nvapi-...`) to access high-speed NIM gateway models like `z-ai/glm-5.2` or `deepseek-ai/deepseek-v4-pro`.

3. **OpenRouter (Free Tier Models)**:
   - Visit [OpenRouter API Keys](https://openrouter.ai/keys) and create a key.
   - You can query any OpenRouter model. Search for free models (those carrying the `:free` suffix) to run them at zero cost:
     - `openrouter/tencent/hy3:free`
     - `openrouter/google/gemini-2.5-flash:free`
     - `openrouter/meta-llama/llama-3-8b-instruct:free`

---

## 📦 Installation & Setup

### Option 1: Automated setup script (Recommended)
Run the automated installation script, which installs the package dependencies, boots setup prompts for API keys, and copies the custom Antigravity skill:
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

### Dry-run refactoring:
Verify matching blocks and inspect compiled changes side-by-side without modifying files on disk:
```bash
walkie consult main.py --task "Refactor login validation" --model zenmux/anthropic/claude-4-fable --dry-run
```
