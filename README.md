# LLM Walkie-Talkie (IDE Agent Consultation CLI)

<div align="center">
  <img src="https://raw.githubusercontent.com/drfox2025/llm-walkie-talkie/main/assets/banner.png" alt="LLM Walkie-Talkie Banner" width="100%">
</div>

LLM Walkie-Talkie (LWT) is a secure, token-efficient command-line interface and integration bridge designed specifically for the Antigravity IDE Agent and developers. It serves as a communication channel, enabling local IDE models to query and consult highly capable external large language models (LLMs). By offloading expensive code generation and automated patching tasks to external services, LWT significantly lowers token consumption for the native IDE models while keeping API credentials isolated and protected.

## 🌟 Key Advantages & Features

1. **Token Cost Efficiency**: IDE agents share a limited context. LWT allows you to delegate massive refactoring, debugging, or research tasks to external endpoints (OpenRouter, Gemini, Groq, Cerebras), preserving your primary agent's token budget.
2. **Multi-LLM Autonomous Loop (PDCA)**: Orchestrates a self-correcting loop using 3 distinct LLM personas to prevent self-justification bias:
   - **Implementer**: Writes the code patches.
   - **Auditor**: Validates against the strict Design Contract YAML.
   - **Red Team**: Adversarial critic that aggressively hunts for flaws and edge cases.
3. **Isolated Sandbox Environments (Git Worktrees)**: All experimental changes and test executions (`walkie loop`) occur in an isolated temporary sandbox. This guarantees that your host project remains pristine until changes are fully validated. Includes ultra-fast sandbox creation using OS-level hard links (`os.link`).
4. **Smart Model Discovery**: Dynamically scans configured providers to identify available free-tier models on-demand (`walkie discover`), checking latency and probing connection health.
5. **Cross-Provider Failover Routing**: Groups identical models across different providers. Employs EWMA latency tracking to dynamically route queries to the fastest active provider and falls back instantly during rate limits (429) or outages.
6. **Auto-Oracle Test Generation**: Automatically writes and executes verification scripts (Oracles) to validate the functional correctness of patches before merging them back to the workspace.
7. **Strict Security Guardrails**: Integrates command blocklists (`curl`, `wget`, `nc`, `ping`, `ftp`, `ssh`) to block hallucinating agents from executing unsafe network requests or malicious payloads during the test phase.
8. **Token-Saving Lexical Comment Stripper**: A robust, quote-safe lexical parser strips single-line and multi-line comments (`#`, `//`, `/* */`) across Python, JS, TS, Rust, Go, SQL, HTML, and C-family languages while preserving string literals to save up to 40% of prompt tokens.
9. **Context-Aware Line-Aligned Truncation**: Intelligently slices attachments to fit model context limits, ensuring code is cut cleanly at line boundaries rather than mid-statement, logging metrics to `stderr`.
10. **Multimodal Visual Reasoning**: Automatically detects image file attachments (`.png`, `.jpg`, `.jpeg`, `.webp`), encodes them into Base64, and constructs multimodal payloads for vision-capable models.
11. **Native LLM Rule Evolution**: Provides the `walkie evolve` suite, allowing internal agents to critique their own work and inject updated behavioral rules into `.agents/AGENTS.md` automatically, with robust timestamped backups for rollbacks.
12. **Audit Trails & Ledger Management**: Logs all events, token usage, and costs securely to a local ledger. Provides commands (`walkie ledger`) to review agent actions and costs by time range.

## 🛠️ How to use with IDE Skills (Slash Commands)

LWT natively extends the IDE Agent through embedded skill prompts. You can trigger these powerful workflows directly in the chat interface:

1. **AI Consultation (`/ai-consult`)**: Triggers the `ai-consult` skill to offload complex coding questions or surgical file modifications to external models (via `walkie consult`), drastically saving the native IDE agent's context tokens.
2. **Native Goal Orchestrator (`/lwt-goal`)**: Triggers the `lwt-goal` skill. The native agent will act as a system orchestrator, automatically generating an Oracle test script and running a sandboxed Native Agent PDCA loop to iteratively achieve your goal while validating against design constraints.
3. **Multi-LLM Engine (`/llm-loop`)**: Triggers the `llm-loop` skill, invoking the external Multi-LLM engine (`walkie loop`) where 3 distinct external models (Implementer, Auditor, Red Team) automatically debate and patch your code in a Git Worktree sandbox.

---

## 🇻🇳 Tính năng và Ưu điểm vượt trội

1. **Tiết kiệm Chi phí & Token**: Tránh làm quá tải context của IDE Agent nội bộ (vốn đắt đỏ) bằng cách ủy thác các tác vụ lập trình, gỡ lỗi hoặc nghiên cứu lớn cho các mô hình ngoài giá rẻ hoặc miễn phí (OpenRouter, Gemini, Groq...).
2. **Vòng lặp Đa Mô hình Tự chỉnh sửa (PDCA)**: Phân phối và kiểm thử chéo thông qua 3 vai trò LLM độc lập để loại bỏ thiên kiến tự biện hộ:
   - **Implementer**: Thực hiện chỉnh sửa mã nguồn.
   - **Auditor**: Kiểm tra sự phù hợp với Hợp đồng Thiết kế (Design Contract).
   - **Red Team**: Đóng vai trò hacker săn lỗi, thử nghiệm các tình huống biên phức tạp.
3. **Không gian Cách ly Sandbox (Git Worktree)**: Mọi thử nghiệm và chạy lệnh test đều diễn ra trong thư mục Sandbox tạm thời. Đảm bảo mã nguồn gốc không bị lỗi hoặc ghi đè ngoài ý muốn. Sử dụng cơ chế sao chép liên kết cứng Hard Link (`os.link`) giúp tạo Sandbox gần như tức thì.
4. **Tự động quét và phát hiện mô hình**: Tự động rà soát hệ thống API của các nhà cung cấp (`walkie discover`) để tìm ra các mô hình miễn phí mới nhất, tự động đo đạc độ trễ và lập bản đồ trạng thái kết nối.
5. **Định tuyến & Dự phòng Liên nhà cung cấp**: Tự động gom nhóm các mô hình giống nhau giữa các nhà cung cấp. Đo đạc độ trễ EWMA để chuyển hướng sang kênh nhanh nhất, và tự động đổi nhà cung cấp nếu gặp lỗi quá tải (429) hoặc mất kết nối.
6. **Auto-Oracle (Tự sinh bộ kiểm thử)**: Tự động viết và khởi chạy các kịch bản kiểm tra (Oracle) tương ứng với ngữ cảnh công việc của bạn, đảm bảo code thực sự vượt qua kiểm thử trước khi bàn giao.
7. **Lớp bảo mật an toàn nghiêm ngặt**: Chặn đứng các lệnh gọi mạng trái phép như `curl`, `wget`, `nc`, `ping`... ngăn ngừa các lỗi ảo giác của LLM làm rò rỉ dữ liệu hoặc tải mã độc về máy.
8. **Bộ loại bỏ chú thích tiết kiệm token**: Sử dụng bộ phân tích từ vựng an toàn (lexical parser) để bóc tách toàn bộ chú thích dòng/khối (`#`, `//`, `/* */`) của nhiều ngôn ngữ lập trình mà không ảnh hưởng tới chuỗi ký tự, tiết kiệm tới 40% lượng token.
9. **Cắt nhỏ ngữ cảnh theo dòng**: Tự động tính toán giới hạn context của từng mô hình để cắt gọn tệp đính kèm một cách sạch sẽ theo ranh giới dòng, tránh việc cắt đứt dòng code ở giữa chừng gây lỗi cú pháp.
10. **Hỗ trợ Thị giác Đa phương thức**: Tự động nhận diện và mã hóa các tệp ảnh (`.png`, `.jpg`, `.jpeg`...) sang định dạng Base64 để gửi payload dạng thị giác cho các mô hình như Gemini, GPT-4o phân tích thiết kế giao diện UI.
11. **Tiến hóa Luật Agent Nội bộ**: Cung cấp bộ công cụ `walkie evolve` giúp Agent tự phê bình hành vi làm việc của mình, rút kinh nghiệm qua LLM ngoài và tự cập nhật luật mới vào `.agents/AGENTS.md` (kèm sao lưu thời gian thực để rollback nếu cần).
12. **Báo cáo và Quản lý Nhật ký Ledger**: Ghi lại chi tiết mọi giao dịch gọi API, số token tiêu thụ và chi phí ước tính vào file nhật ký bảo mật. Cung cấp lệnh `walkie ledger` để truy vấn thống kê chi tiết theo mốc thời gian.

## 🛠️ Hướng dẫn sử dụng kết hợp Kỹ năng (Skills)

LWT mở rộng sức mạnh cho IDE Agent thông qua hệ thống Kỹ năng (Skills). Bạn có thể gõ các lệnh Slash (/) sau trực tiếp vào khung chat:

1. **Tham vấn mô hình ngoại (`/ai-consult`)**: Kích hoạt kỹ năng `ai-consult`. Thay vì tự viết code, IDE Agent sẽ gọi `walkie consult` để đóng gói ngữ cảnh, gửi cho các mô hình lớn bên ngoài giải quyết rồi lấy kết quả vá ngược lại vào file. Giúp tiết kiệm lượng lớn token nội bộ.
2. **Tự động hóa Mục tiêu Nội bộ (`/lwt-goal`)**: Kích hoạt kỹ năng `lwt-goal`. IDE Agent sẽ tự động phân tích yêu cầu, viết script kiểm thử (Oracle), và tạo ra Sandbox độc lập để chạy vòng lặp PDCA bằng chính Native LLM cho đến khi code thực sự chạy đúng yêu cầu.
3. **Vòng lặp Đa Mô hình Ngoại (`/llm-loop`)**: Kích hoạt kỹ năng `llm-loop`, khởi chạy công cụ `walkie loop` để 3 LLM chuyên gia bên ngoài (Implementer, Auditor, Red Team) tự động tranh luận, viết code và kiểm thử chéo trong môi trường Sandbox.

---

## 🚀 Quick Start (30 seconds)

The fastest way to start is with **OpenRouter** — no credit card, instant access to 50+ free models:

1. Run the quick start wizard:
   ```bash
   walkie quickstart
   ```
2. Follow the 3-step guide that appears (sign in → create key → paste).
3. Start coding:
   ```bash
   walkie ask -m openrouter/qwen/qwen3-coder:free --prompt "Hello, world!"
   ```

### Want More Providers?

You do not need paid subscriptions to consult high-performing models. All providers below offer free tiers:

| Provider | Free Tier | Setup Command | What You Get |
|---|---|---|---|
| **OpenRouter** | ✅ No credit card | `walkie setup -p openrouter` | 50+ free models (Qwen3 Coder, Laguna, Nemotron) |
| **NVIDIA NIM** | ✅ 40 RPM free | `walkie setup -p nvidia` | GLM 5.2, DeepSeek V4 Pro on GPU |
| **ZenMux** | ✅ Free tier | `walkie setup -p zenmux` | GLM 5.2, Fable |
| **Groq** | ✅ Free tier | `walkie setup -p groq` | Llama 3, Mixtral (ultra-low latency) |

Or configure all providers at once with the full wizard:
```bash
walkie setup
```

After setup, discover all available models:
```bash
walkie discover --coding-only
```

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
