# LLM Walkie-Talkie (IDE Agent Consultation CLI)

**Tóm tắt tiếng Việt:**
LLM Walkie-Talkie (LWT) là một giao diện dòng lệnh bảo mật và tối ưu hóa token dành riêng cho Antigravity IDE Agent và các lập trình viên. LWT đóng vai trò là cầu nối giao tiếp thông minh, giúp mô hình ngôn ngữ nội bộ của IDE Agent dễ dàng tham vấn các mô hình bên ngoài mạnh mẽ hơn. Bằng cách ủy thác việc biên soạn mã nguồn và vá lỗi tự động cho các mô hình ngoài, công cụ giúp giảm đáng kể chi phí tiêu thụ token nội bộ của Agent mà vẫn bảo vệ an toàn mã khóa API toàn cục.

Điểm nổi bật của chương trình là khả năng tự động quét các cổng API để phát hiện và báo cáo các mô hình miễn phí đang hoạt động, đồng thời kiểm tra trực tiếp độ trễ kết nối thông qua các gói thăm dò để tự cập nhật bộ nhớ đệm trạng thái hệ thống. Bên cạnh đó, LWT tích hợp một quy trình vòng lặp tự sửa lỗi khép kín, phân chia nhiệm vụ đồng thời cho ba vai trò độc lập gồm mô hình triển khai mã nguồn, mô hình kiểm toán thiết kế giao diện và mô hình kiểm thử tìm lỗi xung đột. Toàn bộ quá trình chạy thử được cô lập hoàn toàn trên một phân nhánh Git Worktree độc lập để tránh ảnh hưởng đến thư mục làm việc hiện tại, đi kèm cơ chế sao lưu tự động ngăn ngừa mất mát dữ liệu trước khi cập nhật mã nguồn làm việc chính.

**Cách sử dụng kết hợp với Gọi Kỹ năng (Skill Calling) & Tiến hóa Mô hình Nội bộ (Internal LLM Evolution):**
1. **Khởi tạo và Ủy thác Nhiệm vụ qua Kỹ năng (Skills)**: IDE Agent tự động phát hiện và kích hoạt kỹ năng `ai-consult` (trong `.agents/skills/ai_consult/SKILL.md`) để giảm thiểu tiêu thụ token bằng cách ủy thác các tác vụ lập trình phức tạp cho mô hình bên ngoài qua lệnh `walkie consult`. Đối với các nhiệm vụ giao diện phức tạp đòi hỏi kiểm thử liên tục, Agent sẽ dùng kỹ năng `llm-loop` (trong `.agents/skills/llm_loop/SKILL.md`) để thực thi quy trình sửa lỗi tự động:
   ```bash
   walkie loop --goal "Xây dựng nút bấm đăng nhập" --stop-cmd "npm test" --design-contract theme.contract.yaml --session sess_1
   ```
2. **Kích hoạt Tiến hóa Mô hình Nội bộ (Internal LLM Evolution)**: LWT cung cấp cơ chế giúp mô hình IDE Agent nội bộ tự học hỏi và tối ưu hóa hệ thống luật của chính nó (như trong tệp `.agents/AGENTS.md`). Khi Agent phát hiện điểm chưa tối ưu trong quá trình lập luận hoặc giải quyết tác vụ, nó sẽ đóng gói ngữ cảnh thành JSON và gọi lệnh `walkie evolve`:
   ```bash
   walkie evolve --context '{"task": "Sửa lỗi đăng nhập", "self_assessment": "Tôi đã tốn nhiều thời gian đọc toàn bộ tệp thay vì sử dụng grep để tìm tuyến đường đăng nhập."}'
   ```
   Hệ thống sẽ tự động tham vấn một mô hình chuyên gia lớn hơn để phân tích chuỗi suy nghĩ (CoT), đề xuất quy tắc mới và tự động tiêm quy tắc đó vào phân đoạn chỉ định (ví dụ: `<!-- EVOLVE_SECTION: CODING -->`) trong hệ thống luật của Agent. Bạn hoặc Agent có thể khôi phục lại bất kỳ lúc nào bằng lệnh:
   ```bash
   walkie evolve-restore
   ```

*(English version is below)*

---
<div align="center">
  <img src="https://raw.githubusercontent.com/drfox2025/llm-walkie-talkie/main/assets/banner.png" alt="LLM Walkie-Talkie Banner" width="100%">
</div>

LLM Walkie-Talkie (LWT) is a secure, token-efficient command-line interface and integration bridge designed specifically for the Antigravity IDE Agent and developers. It serves as a communication channel, enabling local IDE models to query and consult highly capable external large language models (LLMs). By offloading expensive code generation and automated patching tasks to external services, LWT significantly lowers token consumption for the native IDE models while keeping API credentials isolated and protected.

Among its technical capabilities, LWT scans provider endpoints on-demand to identify and notify developers of available free-tier models, automatically probing connection health and latencies to update local cache files. It also orchestrates an autonomous, goal-driven patching loop that coordinates three separate LLM roles—an Implementer, a Design Contract Auditor, and an adversarial Red Team critic—to systematically refine code quality and prevent developer self-justification bias. To ensure security, all validation testing runs in isolated Git Worktree sandboxes, complete with automatic file backup histories that prevent host directory data loss upon copy-back.

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


