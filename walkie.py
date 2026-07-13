
import os
import sys
import json
import datetime
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import click
from dotenv import load_dotenv, set_key

# Centralized Configuration & Logging Directory
try:
    CONFIG_DIR = Path.home() / '.walkie'
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR = CONFIG_DIR / 'logs'
    LOG_DIR.mkdir(parents=True, exist_ok=True)
except Exception:
    CONFIG_DIR = Path(__file__).resolve().parent
    LOG_DIR = CONFIG_DIR / 'logs'
    LOG_DIR.mkdir(parents=True, exist_ok=True)


SESSION_DIR = CONFIG_DIR / 'sessions'
SESSION_MAX_TURNS = 20          # hard cap stored on disk
SESSION_INJECT_TURNS = 6        # how many recent turns to inject into prompt
SESSION_DIFF_CHAR_CAP = 400     # reuse your chain-diff cap

def _session_path(session_id: str) -> Path:
    safe = re.sub(r'[^\w.\-]+', '-', session_id)[:80]
    return SESSION_DIR / f"{safe}.json"

def load_session(session_id: str) -> Optional[Dict[str, Any]]:
    p = _session_path(session_id)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding='utf-8'))
    except Exception as e:
        click.secho(f"Warning: Could not read session: {safe_error_handler(e)}", fg="yellow", err=True)
        return None

def save_session(session_id: str, data: dict) -> None:
    try:
        SESSION_DIR.mkdir(parents=True, exist_ok=True)
        data['updated'] = datetime.datetime.now().isoformat()
        # LRU trim
        if 'turns' in data:
            data['turns'] = data['turns'][-SESSION_MAX_TURNS:]
        if 'messages' in data:
            # Note: SESSION_MAX_TURNS represents individual message entries here,
            # so an exchange (user+assistant) consumes 2 turns. This means
            # a cap of 20 equates to ~10 conversational exchanges.
            if data['messages'] and data['messages'][0].get('role') == 'system':
                data['messages'] = [data['messages'][0]] + data['messages'][-(SESSION_MAX_TURNS-1):]
            else:
                data['messages'] = data['messages'][-SESSION_MAX_TURNS:]
        p = _session_path(session_id)
        tmp = p.with_suffix('.json.tmp')
        tmp.write_text(json.dumps(data, indent=2), encoding='utf-8')
        if os.name != 'nt':
            os.chmod(tmp, 0o600)
        tmp.replace(p)   # atomic
    except Exception as e:
        click.secho(f"Warning: Could not save session: {safe_error_handler(e)}", fg="yellow", err=True)

env_path = CONFIG_DIR / '.env'
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
else:
    local_env = Path(__file__).resolve().parent / '.env'
    if local_env.exists():
        env_path = local_env
        load_dotenv(dotenv_path=env_path)
    else:
        example_path = Path(__file__).resolve().parent / '.env.example'
        if example_path.exists():
            import shutil
            try:
                shutil.copy(example_path, env_path)
                if os.name != 'nt':
                    os.chmod(env_path, 0o600)
                load_dotenv(dotenv_path=env_path)
                click.secho(f"Bootstrapped global .env at {env_path}", fg="yellow", err=True)
            except Exception as e:
                click.secho(f"Warning: Failed to bootstrap .env: {str(e)}", fg="yellow", err=True)

# Harden existing .env permissions if wider than 0o600 on non-Windows platforms
if env_path.exists() and os.name != 'nt':
    try:
        current_mode = env_path.stat().st_mode & 0o777
        if (current_mode & 0o077) != 0:
            os.chmod(env_path, 0o600)
            click.secho(f"Hardened permissions on {env_path} to 0o600", fg="yellow", err=True)
    except Exception:
        pass

PROVIDERS = {
    "ZENMUX": {
        "env_var": "ZENMUX_API_KEY",
        "description": "ZenMux API Key (provides free GLM 5.2 and others)",
        "test_model": "zenmux/glm-4",
        "api_base": "https://zenmux.ai/api/v1"
    },
    "NVIDIA": {
        "env_var": "NVIDIA_API_KEY",
        "description": "NVIDIA API Key (NIM integration gateway)",
        "test_model": "nvidia/z-ai/glm-5.2",
        "api_base": "https://integrate.api.nvidia.com/v1"
    },
    "GROQ": {
        "env_var": "GROQ_API_KEY",
        "description": "Groq API Key (fast Llama 3 / Mixtral)",
        "test_model": "groq/llama3-8b-8192",
    },
    "OPENROUTER": {
        "env_var": "OPENROUTER_API_KEY",
        "description": (
            "OpenRouter API Key (unified free gateway). "
            "Top 3 free coding models (as of July 2026): "
            "1) qwen/qwen3-coder:free (1M ctx, coding+reasoning), "
            "2) poolside/laguna-m.1:free (262K ctx, coding+reasoning), "
            "3) nvidia/nemotron-3-ultra-550b-a55b:free (1M ctx, reasoning). "
            "Get key at: https://openrouter.ai/keys"
        ),
        "test_model": "openrouter/qwen/qwen3-coder:free",
        "api_base": "https://openrouter.ai/api/v1"
    },
    "GEMINI": {
        "env_var": "GEMINI_API_KEY",
        "description": "Google Gemini API Key",
        "test_model": "gemini/gemini-1.5-flash",
    },
    "OPENAI": {
        "env_var": "OPENAI_API_KEY",
        "description": "OpenAI API Key",
        "test_model": "openai/gpt-3.5-turbo",
    },
    "ANTHROPIC": {
        "env_var": "ANTHROPIC_API_KEY",
        "description": "Anthropic API Key",
        "test_model": "anthropic/claude-3-haiku-20240307",
    }
}

PROVIDER_CONFIG = {
    "ZENMUX": {
        "pattern": r"^sk-ai-v1-[a-zA-Z0-9_-]{20,}$",
        "url": "Visit https://zenmux.ai and navigate to API Keys section."
    },
    "NVIDIA": {
        "pattern": r"^nvapi-[a-zA-Z0-9_-]{40,}$",
        "url": "Visit https://build.nvidia.com and generate an API key."
    },
    "GROQ": {
        "pattern": r"^gsk_[a-zA-Z0-9_-]{40,}$",
        "url": "Visit https://console.groq.com/keys to create a key."
    },
    "OPENROUTER": {
        "pattern": r"^sk-or-[a-zA-Z0-9-_]{40,}$",
        "url": "Visit https://openrouter.ai/keys to create a key."
    },
    "GEMINI": {
        "pattern": r"^AIzaSy[a-zA-Z0-9_-]{33}$",
        "url": "Visit https://aistudio.google.com/app/apikey to create a key."
    },
    "OPENAI": {
        "pattern": r"^sk-[a-zA-Z0-9_-]{20,}$",
        "url": "Visit https://platform.openai.com/api-keys to create a key."
    },
    "ANTHROPIC": {
        "pattern": r"^sk-ant-[a-zA-Z0-9-_]{40,}$",
        "url": "Visit https://console.anthropic.com/settings/keys to create a key."
    }
}

@click.group()
def cli():
    """LLM Walkie-Talkie: Consult external LLMs from your IDE."""
    active_provs = []
    for provider, info in PROVIDERS.items():
        if os.getenv(info["env_var"]):
            active_provs.append(provider)
    if active_provs:
        click.secho(f"[WARM START] Identified active providers: {', '.join(active_provs)}", fg="green", err=True)
    else:
        click.secho("[WARM START] No active providers identified. Please run `walkie setup`.", fg="yellow", err=True)


def health_ok(model: str, ttl=3600):
    p = CONFIG_DIR / "health.json"
    try:
        data = json.loads(p.read_text())
        if "models" in data and model in data["models"]:
            d = data["models"][model]
            if time.time() - d["ts"] < ttl and d["ok"]:
                return True
    except Exception:
        pass
    return None

def write_health(model: str, ok: bool):
    p = CONFIG_DIR / "health.json"
    try:
        data = json.loads(p.read_text()) if p.exists() else {"models": {}}
        if "models" not in data:
            data["models"] = {}
        data["models"][model] = {"ts": time.time(), "ok": ok}
        p.write_text(json.dumps(data))
    except Exception:
        pass

@cli.command()
@click.option('--model', '-m', default="nvidia/z-ai/glm-5.2", help="Model to probe.")
def health(model):
    """Check connection health with TTL caching."""
    if health_ok(model, 3600):
        click.secho("[OK] Connection cached (fresh).", fg="green")
        sys.exit(0)

    # Needs real probe
    try:
        call_llm(model=model, messages=[{"role": "user", "content": "Hi"}], max_tokens=5, no_log=True)
        write_health(model, True)
        click.secho(f"[OK] Connection verified via real probe ({model}).", fg="green")
    except Exception as e:
        write_health(model, False)
        click.secho(f"[FAIL] Connection test failed for {model}: {e}", fg="red", err=True)
        sys.exit(1)

@cli.command()
def setup():
    """Interactive wizard to configure Walkie-Talkie API keys."""
    click.secho("LLM Walkie-Talkie Setup", fg="cyan", bold=True)
    click.echo("API Keys will be masked as you type them and validated against expected formats.\n")

    if not env_path.exists():
        env_path.touch()
        if os.name != 'nt':
            os.chmod(env_path, 0o600)

    for provider, info in PROVIDERS.items():
        env_var = info["env_var"]
        current_val = os.getenv(env_var)
        cfg = PROVIDER_CONFIG.get(provider, {})

        click.secho(f"--- Configure {provider} ---", fg="blue", bold=True)

        # NVIDIA: offer step-by-step wizard before prompting for key
        if provider == "NVIDIA" and not current_val:
            click.echo("NVIDIA NIM provides free GPU-hosted models (40 RPM free tier).")
            click.echo("To get your free nvapi- key:")
            if click.confirm("  Open the NVIDIA developer portal in your browser now?", default=True):
                import webbrowser
                webbrowser.open("https://build.nvidia.com")
            click.echo("")
            click.echo("  Step 1: Sign in or create a free NVIDIA Developer account.")
            click.echo("  Step 2: Browse to 'Models' > choose any model (e.g., GLM-5.2).")
            click.echo("  Step 3: Click 'Get API Key' — select a model endpoint if prompted.")
            click.echo("  Step 4: Copy your key (starts with nvapi-). It is valid for 90 days.")
            click.echo("")
        elif cfg.get("url"):
            click.echo(f"Help URL: {cfg['url']}")

        if current_val:
            click.echo(f"Current key is set (starts with {current_val[:6]}...)")
            update = click.confirm("Do you want to update this key?", default=False)
            if not update:
                continue

        new_key = click.prompt(f"Enter {env_var}", default="", show_default=False, hide_input=True)
        new_key = new_key.strip()
        if new_key:
            pattern = cfg.get("pattern")
            if pattern and not re.match(pattern, new_key):
                click.secho(f"Note: The entered key does not match the typical pattern for {provider}.", fg="yellow")
                if not click.confirm("Do you want to save it anyway?", default=False):
                    click.echo("Skipping key saving.")
                    continue

            try:
                set_key(env_path, env_var, new_key)
                os.environ[env_var] = new_key
            except Exception as e:
                click.secho(f"Error saving key for {provider}: {str(e)}", fg="red", err=True)
                continue

            click.echo(f"Verifying {provider} connection...")
            try:
                model = info["test_model"]
                call_llm(model=model, messages=[{"role": "user", "content": "Hi"}], max_tokens=5, no_log=True)
                click.secho(f"[OK] Success! {provider} is working.", fg="green")

                # Auto-discover models for this provider after successful setup
                click.secho(f"[SCAN] Discovering available models on {provider}...", fg="cyan")
                try:
                    import discovery as disc
                    registry, _ = disc.run_discovery(force=True)
                    prov_upper = provider.upper()
                    prov_models = [
                        (c, e) for c, e in disc.rank_free_models(registry, use_case="coding")
                        if any(r["provider"] == prov_upper for r in e.get("routes", []))
                    ][:5]
                    if prov_models:
                        click.echo(f"  Top models available on {provider}:")
                        for canonical, entry in prov_models:
                            tags = ", ".join(entry.get("tags", [])[:2])
                            routes = [r for r in entry["routes"] if r["provider"] == prov_upper]
                            ctx = max((r.get("context_length") or 0) for r in routes)
                            ctx_str = f"{ctx // 1000}K" if ctx >= 1000 else "-"
                            click.echo(f"    • {canonical:<22} ctx={ctx_str:<6} [{tags}]")
                    else:
                        click.echo("  No free models found for this provider yet.")
                except Exception:
                    pass  # discovery failure is non-fatal

            except Exception as e:
                click.secho(f"[NO] Failed to verify {provider}: {str(e)}", fg="red")

    if os.name != 'nt' and env_path.exists():
        os.chmod(env_path, 0o600)
    click.secho("\nSetup complete!", fg="green")
    click.secho("Tip: Run `walkie discover --coding-only` to see all available free models.", fg="cyan")
    click.secho("Tip: Run `walkie status` to see connection status for all providers.", fg="cyan")

def _strip_comments(code: str, file_ext: str) -> str:
    """
    Safely strips comments from source code based on the file extension.
    Preserves string literals to prevent accidental code removal.
    """
    file_ext = file_ext.lower().lstrip(".")

    # Define comment syntax per language family
    single_line_tokens = []
    multi_line_pairs = []

    if file_ext in ("py", "dockerfile", "sh", "bash", "zsh", "r", "makefile", "cmake", "rb"):
        single_line_tokens.append("#")
    elif file_ext in ("js", "ts", "tsx", "jsx", "java", "c", "cc", "cpp", "cxx", "h",
                      "hpp", "hxx", "cs", "go", "rs", "swift", "kt", "scala", "php", "css", "less", "scss"):
        single_line_tokens.extend(["//"])
        multi_line_pairs.append(("/*", "*/"))
    elif file_ext in ("html", "xml", "svg", "vue", "svelte"):
        multi_line_pairs.append(("<!--", "-->"))
    elif file_ext in ("sql",):
        single_line_tokens.append("--")
        multi_line_pairs.append(("/*", "*/"))
    elif file_ext in ("lua",):
        single_line_tokens.extend(["--"])
        multi_line_pairs.append(("--[[", "]]"))
    elif file_ext in ("vim", "vimrc"):
        single_line_tokens.append('"')
    elif file_ext in ("lisp", "el", "clj", "edn", "rkt", "scm"):
        single_line_tokens.append(";")
    elif file_ext in ("asm", "s"):
        single_line_tokens.extend([";", "//"])
        multi_line_pairs.append(("/*", "*/"))
    else:
        return code

    # Simple state machine to protect string literals
    result: List[str] = []
    i = 0
    n = len(code)
    in_single_str = None
    in_line_comment = False
    in_block_comment = False

    while i < n:
        if in_line_comment:
            if code[i] == "\n":
                result.append("\n")
                in_line_comment = False
            i += 1
            continue

        if in_block_comment:
            for end_token in [p[1] for p in multi_line_pairs]:
                if code.startswith(end_token, i):
                    i += len(end_token)
                    in_block_comment = False
                    break
            else:
                i += 1
            continue

        if file_ext == "py" and not in_single_str:
            matched_triple = False
            for triple in ['"""', "'''"]:
                if code.startswith(triple, i):
                    idx = code.find(triple, i + 3)
                    if idx == -1:
                        result.append(code[i:])
                        i = n
                    else:
                        result.append(code[i:idx + 3])
                        i = idx + 3
                    matched_triple = True
                    break
            if matched_triple:
                continue
            if i >= n:
                continue

        if not in_single_str:
            matched_block = False
            for start_token, end_token in multi_line_pairs:
                if code.startswith(start_token, i):
                    in_block_comment = True
                    i += len(start_token)
                    matched_block = True
                    break
            if matched_block:
                continue

            matched_line = False
            for token in single_line_tokens:
                if code.startswith(token, i):
                    in_line_comment = True
                    i += len(token)
                    matched_line = True
                    break
            if matched_line:
                continue

        if not in_single_str and code[i] in ('"', "'"):
            in_single_str = code[i]
        elif in_single_str and code[i] == in_single_str:
            # Count preceding backslashes to check for true escape
            backslash_count = 0
            j = i - 1
            while j >= 0 and code[j] == '\\':
                backslash_count += 1
                j -= 1
            if backslash_count % 2 == 0:
                in_single_str = None

        result.append(code[i])
        i += 1

    # Strip trailing whitespaces and remove excessive empty lines
    lines = [line.rstrip() for line in "".join(result).splitlines()]
    non_empty_lines = []
    for line in lines:
        if line:
            non_empty_lines.append(line)
        elif len(non_empty_lines) > 0 and non_empty_lines[-1] != "":
            non_empty_lines.append("")
    return "\n".join(non_empty_lines).strip()
_KEY_PATTERNS = [
    re.compile(r"sk-ai-v1-[a-zA-Z0-9_-]{10,}"),
    re.compile(r"nvapi-[a-zA-Z0-9_-]{10,}"),
    re.compile(r"gsk_[a-zA-Z0-9_-]{10,}"),
    re.compile(r"sk-or-[a-zA-Z0-9_-]{10,}"),
    re.compile(r"sk-ant-[a-zA-Z0-9_-]{10,}"),
    re.compile(r"AIzaSy[a-zA-Z0-9_-]{20,}"),
    re.compile(r"sk-[a-zA-Z0-9_-]{20,}"),
]

EXPERIENCE_PATH = CONFIG_DIR / "llm_experience.yaml"
EXPERIENCE_VERSION = 1
EXPERIENCE_MAX_ENTRIES = 20
EXPERIENCE_MAX_LESSONS = 3
EXPERIENCE_MIN_CONFIDENCE = 0.6
EXPERIENCE_SAVE_MIN_CONFIDENCE = 0.7
EXPERIENCE_LESSON_MAX_LEN = 120

_ERROR_CATEGORIES = {
    "whitespace_mismatch": re.compile(
        r"(?i)(original block not found|whitespace|indentation|tab|spaces?)"
    ),
    "syntax_violation": re.compile(
        r"(?i)(syntax\s*error|invalid syntax|unexpected indent|expected )"
    ),
    "format_violation": re.compile(
        r"(?i)(no valid replacement|expected format|REPLACEMENT_)"
    ),
    "scope_error": re.compile(
        r"(?i)(undefined|not defined|nameerror|import missing|out of scope)"
    ),
    "logic_hallucination": re.compile(
        r"(?i)(hallucin|auditor.*fail|incorrect logic|wrong assumption)"
    ),
}

_LESSON_TEMPLATES = {
    "whitespace_mismatch": "Preserve exact original whitespace (spaces/tabs/trailing) in REPLACEMENT_START.",
    "syntax_violation": "REPLACEMENT_WITH must be syntactically valid for the language before emit.",
    "format_violation": "Emit only REPLACEMENT_START / WITH / END blocks; no prose outside them.",
    "scope_error": "Do not invent symbols; only use names present in the provided file segment.",
    "logic_hallucination": "Match task literally; do not change unrelated logic or invent APIs.",
}

def abstract_lesson(error_feedback: str, attempts_needed: int, file_ext: str) -> Optional[Dict[str, Any]]:
    """Map error text to category lesson. No raw strings persisted."""
    if not error_feedback or attempts_needed < 1:
        return None
    ext = file_ext.lower().lstrip(".")
    for category, pat in _ERROR_CATEGORIES.items():
        if pat.search(error_feedback):
            base = _LESSON_TEMPLATES[category]
            if ext and ext not in base:
                lesson = f"{ext}: {base}"
            else:
                lesson = base
            lesson = lesson[:EXPERIENCE_LESSON_MAX_LEN]
            confidence = min(1.0, 0.5 + 0.1 * attempts_needed)
            return {
                "category": category,
                "lesson": lesson,
                "confidence": confidence,
                "attempts_needed": attempts_needed,
            }
    return None

def load_experience_prompt(file_ext: str, max_lessons: int = EXPERIENCE_MAX_LESSONS, min_confidence: float = EXPERIENCE_MIN_CONFIDENCE) -> str:
    """Top-N lessons by score = count * confidence. Empty string if none."""
    if not EXPERIENCE_PATH.exists():
        return ""
    try:
        import yaml
        data = yaml.safe_load(EXPERIENCE_PATH.read_text(encoding="utf-8")) or {}
        if data.get("version") != EXPERIENCE_VERSION:
            return ""
        patterns = (data.get("patterns") or {}).get(file_ext.lower().lstrip("."), {})
        if not patterns:
            return ""
        scored = []
        for _cat, details in patterns.items():
            conf = float(details.get("confidence", 0))
            if conf < min_confidence:
                continue
            lesson = str(details.get("lesson", "")).strip()
            if not lesson or len(lesson) > EXPERIENCE_LESSON_MAX_LEN + 20:
                continue
            score = int(details.get("count", 1)) * conf
            scored.append((score, lesson))
        scored.sort(key=lambda x: x[0], reverse=True)
        selected = [L for _, L in scored[:max_lessons]]
        if not selected:
            return ""
        return (
            "\n\n### Critical Patterns (past failures - avoid):\n"
            + "\n".join(f"- {L}" for L in selected)
        )
    except Exception:
        return ""

def save_experience(file_ext: str, lesson_data: Dict[str, Any]) -> None:
    """Upsert category; LRU-evict lowest confidence if over max_entries."""
    if not lesson_data or lesson_data.get("confidence", 0) < EXPERIENCE_SAVE_MIN_CONFIDENCE:
        return
    ext = file_ext.lower().lstrip(".")
    category = lesson_data.get("category")
    if category not in _LESSON_TEMPLATES:
        return
    try:
        import yaml
        data = {
            "version": EXPERIENCE_VERSION,
            "max_entries": EXPERIENCE_MAX_ENTRIES,
            "patterns": {},
        }
        if EXPERIENCE_PATH.exists():
            loaded = yaml.safe_load(EXPERIENCE_PATH.read_text(encoding="utf-8"))
            if isinstance(loaded, dict) and loaded.get("version") == EXPERIENCE_VERSION:
                data = loaded
        data.setdefault("patterns", {})
        data["patterns"].setdefault(ext, {})
        bucket = data["patterns"][ext]
        today = datetime.date.today().isoformat()

        if category in bucket:
            existing = bucket[category]
            existing["count"] = int(existing.get("count", 0)) + 1
            existing["confidence"] = max(
                float(existing.get("confidence", 0)),
                float(lesson_data.get("confidence", 0.5)),
            )
            existing["last_seen"] = today
            existing["lesson"] = str(existing.get("lesson") or lesson_data["lesson"])[:EXPERIENCE_LESSON_MAX_LEN]
        else:
            total = sum(len(p) for p in data["patterns"].values())
            if total >= int(data.get("max_entries", EXPERIENCE_MAX_ENTRIES)):
                worst = None
                for e, pats in data["patterns"].items():
                    for c, d in pats.items():
                        key = (
                            float(d.get("confidence", 0)),
                            str(d.get("last_seen", "")),
                            e,
                            c,
                        )
                        if worst is None or key < worst:
                            worst = key
                if worst:
                    _, _, we, wc = worst
                    del data["patterns"][we][wc]
                    if not data["patterns"][we]:
                        del data["patterns"][we]
            bucket[category] = {
                "lesson": str(lesson_data["lesson"])[:EXPERIENCE_LESSON_MAX_LEN],
                "count": 1,
                "confidence": float(lesson_data.get("confidence", 0.5)),
                "last_seen": today,
            }

        data["version"] = EXPERIENCE_VERSION
        data["max_entries"] = EXPERIENCE_MAX_ENTRIES
        data["updated"] = today

        tmp = EXPERIENCE_PATH.with_suffix(".yaml.tmp")
        tmp.write_text(
            yaml.dump(data, default_flow_style=False, allow_unicode=True),
            encoding="utf-8",
        )
        if os.name != "nt":
            os.chmod(tmp, 0o600)
        tmp.replace(EXPERIENCE_PATH)
        if os.name != "nt" and EXPERIENCE_PATH.exists():
            os.chmod(EXPERIENCE_PATH, 0o600)
    except Exception as e:
        click.secho(
            f"Warning: Could not save experience: {safe_error_handler(e)}",
            fg="yellow",
            err=True,
        )

def safe_error_handler(e: Exception) -> str:
    """Regex-scrub API keys from errors to prevent accidental credential leakage in logs or console."""
    msg = str(e)
    for pat in _KEY_PATTERNS:
        msg = pat.sub("[REDACTED_KEY]", msg)
    return msg

def sanitize_path(user_path: str, root: Optional[Path] = None) -> Path:
    """Verify paths reside inside workspace to block path traversal attempts."""
    if os.environ.get("WALKIE_ALLOW_ABSOLUTE") == "1":
        return Path(user_path).expanduser().resolve()
    root = (root or Path.cwd()).resolve()
    resolved = Path(user_path).expanduser().resolve()
    try:
        resolved.relative_to(root)
    except ValueError:
        click.secho(f"Security Error: path outside workspace blocked: {user_path}", fg="red", err=True)
        sys.exit(1)
    return resolved
def safe_print(text: str, fg: Optional[str] = None, nl: bool = True, err: bool = False):
    """Safely print text to stdout/stderr replacing characters not supported by the console encoding."""
    stream = sys.stderr if err else sys.stdout
    encoding = getattr(stream, 'encoding', None) or 'utf-8'
    encoded = text.encode(encoding, errors='replace')
    decoded = encoded.decode(encoding)
    click.secho(decoded, fg=fg, nl=nl, err=err)

def route_model(model: str) -> Tuple[str, Optional[str], Optional[str]]:
    """Dynamically route model based on global PROVIDERS config mapping keys."""
    api_base = None
    api_key = None
    routed_model = model

    for provider, info in PROVIDERS.items():
        prefix = f"{provider.lower()}/"
        if model.startswith(prefix):
            env_var = info["env_var"]
            if provider == "NVIDIA" and "deepseek" in model.lower():
                api_key = os.getenv("NVIDIA_DEEPSEEK_API_KEY") or os.getenv(env_var)
            else:
                api_key = os.getenv(env_var)

            if not api_key:
                raise ValueError(f"Provider {provider} is not configured. Please set {env_var} environment variable or run `walkie setup`.")

            if info.get("api_base"):
                routed_model = "openai/" + model.split("/", 1)[1]
                api_base = info.get("api_base")
            else:
                routed_model = model
            break

    return routed_model, api_base, api_key

def build_prompt(
    prompt: str,
    prompt_file: Optional[str],
    attach: List[str],
    strip_comments: bool,
    model: str
) -> Tuple[str, List[str], str]:
    """Compiles prompt, reads files, handles newline-aligned context-aware chunking limits, and extracts base64 images."""
    import base64
    max_chars = 300000  # Default ~100k tokens
    lower_model = model.lower()
    if "glm-5.2" in lower_model or "gemini" in lower_model:
        max_chars = 2000000
    elif "haiku" in lower_model or "sonnet" in lower_model or "opus" in lower_model:
        max_chars = 600000
    elif "groq" in lower_model:
        max_chars = 20000
    elif "gpt-3.5" in lower_model:
        max_chars = 40000

    stdin_content = ""
    if not prompt and not prompt_file and not sys.stdin.isatty():
        stdin_content = sys.stdin.read().strip()

    if not prompt and not prompt_file and not stdin_content:
        click.secho("Error: Must provide either --prompt, --prompt-file, or pipe input via stdin", fg="red", err=True)
        sys.exit(1)

    full_prompt = prompt
    if prompt_file:
        s_prompt_file = sanitize_path(prompt_file)
        with open(s_prompt_file, 'r', encoding='utf-8') as f:
            file_content = f.read()
            if full_prompt:
                full_prompt += "\n\n" + file_content
            else:
                full_prompt = file_content

    if stdin_content:
        if full_prompt:
            full_prompt += "\n\n" + stdin_content
        else:
            full_prompt = stdin_content

    raw_prompt = full_prompt
    images_list = []
    if attach:
        attachment_blocks = []
        for file_path in attach:
            path_obj = sanitize_path(file_path)
            # Detect images
            if path_obj.suffix.lower() in ('.png', '.jpg', '.jpeg', '.webp', '.gif'):
                try:
                    with open(path_obj, 'rb') as f:
                        img_bytes = f.read()
                    img_base64 = base64.b64encode(img_bytes).decode('utf-8')
                    mime_type = f"image/{path_obj.suffix.lower().lstrip('.')}"
                    if mime_type == "image/jpg":
                        mime_type = "image/jpeg"
                    images_list.append(f"data:{mime_type};base64,{img_base64}")
                    click.secho(f"Attached image: {path_obj.name} (encoded in base64)", fg="cyan", err=True)
                except Exception as e:
                    click.secho(f"Warning: Could not read image {file_path}: {str(e)}", fg="yellow", err=True)
                continue

            try:
                with open(path_obj, 'r', encoding='utf-8', errors='ignore') as f:
                    file_content = f.read()
                if strip_comments:
                    file_content = _strip_comments(file_content, path_obj.suffix)

                if len(file_content) > max_chars:
                    original_len = len(file_content)
                    original_lines = file_content.splitlines()

                    # Find nearest newline boundary strictly under max_chars to keep lines complete
                    trunc_idx = file_content.rfind('\n', 0, max_chars)
                    if trunc_idx == -1:
                        trunc_idx = file_content.find('\n', max_chars)
                    if trunc_idx == -1:
                        trunc_idx = max_chars

                    truncated_block = file_content[:trunc_idx]
                    kept_lines = len(truncated_block.splitlines())
                    dropped_lines = len(original_lines) - kept_lines
                    dropped_chars = original_len - len(truncated_block)

                    file_content = truncated_block
                    warning_msg = (
                        f"\n\n... [NOTICE] Truncated {dropped_lines} lines and {dropped_chars} characters "
                        f"to fit {model}'s context window limit. No lines were cut mid-line."
                    )
                    file_content += warning_msg

                    click.secho(
                        f"Warning: Attachment {file_path} is too large for model {model}'s context window. "
                        f"Truncated {dropped_lines} lines / {dropped_chars} characters (aligned to newline).",
                        fg="yellow", err=True
                    )

                attachment_blocks.append(
                    f"\n---\nFile: {path_obj.name}\n```"
                    f"{path_obj.suffix.lstrip('.')}\n"
                    f"{file_content}\n```"
                )
            except Exception as e:
                click.secho(f"Warning: Could not read attachment {file_path}: {str(e)}", fg="yellow", err=True)
        if attachment_blocks:
            full_prompt += "\n\n### Attached Files Context:\n" + "\n".join(attachment_blocks)

    return full_prompt, images_list, raw_prompt

def log_interaction(
    model: str,
    routed_model: str,
    system: str,
    full_prompt: str,
    reply: str,
    usage_data: dict,
    no_log: bool
) -> Tuple[Optional[Path], Optional[Path]]:
    """Log the interaction into JSON and Markdown log files, unless no_log is requested."""
    if no_log:
        return None, None

    # Scrub any API key values that may appear in prompts or errors
    try:
        from discovery import mask_keys as _mask_keys
        full_prompt_safe = _mask_keys(full_prompt)
        system_safe = _mask_keys(system or "")
        reply_safe = _mask_keys(reply or "")
    except Exception:
        full_prompt_safe, system_safe, reply_safe = full_prompt, system or "", reply or ""

    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S_%f")
    safe_model = re.sub(r'[^\w.\-]+', '-', model)[:80]

    log_data = {
        "timestamp": timestamp,
        "model": model,
        "routed_model": routed_model,
        "system_prompt": system_safe,
        "user_prompt": full_prompt_safe,
        "response": reply_safe,
        "usage": usage_data
    }
    json_path = LOG_DIR / f"{timestamp}_{safe_model}.json"
    md_path = LOG_DIR / f"{timestamp}_{safe_model}.md"

    try:
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(log_data, f, indent=2)
    except Exception as e:
        click.secho(f"Warning: Could not write JSON log: {str(e)}", fg="yellow", err=True)
        json_path = None

    try:
        with open(md_path, 'w', encoding='utf-8') as f:
            f.write(f"# Walkie-Talkie Log\n\n")
            f.write(f"**Date:** {timestamp}\n")
            f.write(f"**Model:** {model}\n\n")

            # Determine dynamic fence length to avoid breaking markdown code blocks if contents contain backticks
            contents_combined = full_prompt + "\n" + (system or "") + "\n" + reply
            max_backticks = 0
            for match in re.finditer(r'`+', contents_combined):
                if len(match.group()) > max_backticks:
                    max_backticks = len(match.group())
            fence_len = max(3, max_backticks + 1)
            fence_str = "`" * fence_len

            if system:
                f.write(f"## System Prompt\n{fence_str}\n{system}\n{fence_str}\n\n")
            f.write(f"## User Prompt\n{fence_str}\n{full_prompt}\n{fence_str}\n\n")
            f.write(f"## Response\n{fence_str}\n{reply}\n{fence_str}\n")
    except Exception as e:
        click.secho(f"Warning: Could not write Markdown log: {str(e)}", fg="yellow", err=True)
        md_path = None

    return json_path, md_path

@cli.command()
@click.option('--model', '-m', default="nvidia/z-ai/glm-5.2", help="Model name (defaults to nvidia/z-ai/glm-5.2)")
@click.option('--prompt', '-p', default="", help="Text prompt to send to the model.")
@click.option('--prompt-file', '-f', type=click.Path(exists=True), help="Read prompt from a file (appended to --prompt if both provided).")
@click.option('--system', '-s', default="", help="Optional system prompt.")
@click.option('--max-tokens', '-t', type=int, default=None, help="Maximum number of tokens to generate.")
@click.option('--temperature', type=float, default=None, help="Sampling temperature.")
@click.option('--top-p', type=float, default=None, help="Top-p sampling.")
@click.option('--extra-body', type=str, default="", help="JSON string for extra_body parameters.")
@click.option('--attach', '-a', multiple=True, type=click.Path(exists=True), help="Attach files to the prompt context.")
@click.option('--strip-comments', is_flag=True, help="Strip comments and empty lines from attached files to save tokens.")
@click.option('--json-output', is_flag=True, help="Format CLI output as JSON.")
@click.option('--stream', is_flag=True, help="Stream response in real-time.")
@click.option('--no-log', is_flag=True, help="Disable logging to disk.")
@click.option('--session', help="Continue a conversational session (full history replay).")
def ask(model, prompt, prompt_file, system, max_tokens, temperature, top_p, extra_body, attach, strip_comments, json_output, stream, no_log, session):
    """Ask a question to an LLM."""
    import litellm
    full_prompt, images_list, raw_prompt = build_prompt(prompt, prompt_file, attach, strip_comments, model)
    routed_model, api_base, api_key = route_model(model)

    if session and (attach or images_list):
        click.secho("Notice: Attachments are point-in-time context and will not be saved into the session history.", fg="cyan", err=True)

    session_data = load_session(session) if session else None
    history = session_data.get("messages", []) if session_data else []

    messages = []
    if system and not history:
        messages.append({"role": "system", "content": system})

    messages.extend(history)

    if images_list:
        user_content = [{"type": "text", "text": full_prompt}]
        for img_url in images_list:
            user_content.append({
                "type": "image_url",
                "image_url": {"url": img_url}
            })
        messages.append({"role": "user", "content": user_content})
    else:
        messages.append({"role": "user", "content": full_prompt})

    click.secho(f"Calling {model}...", fg="yellow", err=True)

    kwargs = {"model": routed_model, "messages": messages}
    if api_base:
        kwargs["api_base"] = api_base
    if api_key:
        kwargs["api_key"] = api_key
    if max_tokens is not None:
        kwargs["max_tokens"] = max_tokens
    if temperature is not None:
        kwargs["temperature"] = temperature
    if top_p is not None:
        kwargs["top_p"] = top_p
    if extra_body:
        try:
            kwargs["extra_body"] = json.loads(extra_body)
        except Exception as e:
            click.secho(f"Error parsing --extra-body JSON: {str(e)}", fg="red", err=True)
            sys.exit(1)

    try:
        reply = ""
        usage_data = {}

        if not stream:
            try:
                response = litellm.completion(**kwargs)
            except Exception as le:
                raise RuntimeError(safe_error_handler(le)) from None
            reply = response.choices[0].message.content

            if hasattr(response, 'usage') and response.usage:
                if hasattr(response.usage, 'model_dump'):
                    usage_data = response.usage.model_dump()
                elif hasattr(response.usage, 'dict'):
                    usage_data = response.usage.dict()
                else:
                    try:
                        usage_data = dict(response.usage)
                    except Exception:
                        usage_data = {k: str(v) for k, v in vars(response.usage).items()} if hasattr(response.usage, '__dict__') else str(response.usage)
        else:
            try:
                response_stream = litellm.completion(**kwargs, stream=True)
            except Exception as le:
                raise RuntimeError(safe_error_handler(le)) from None
            click.secho(f"Streaming {model}...", fg="yellow", err=True)

            if not json_output and sys.stdout.isatty():
                click.echo("-" * 40)

            chunks = []
            for chunk in response_stream:
                try:
                    if hasattr(chunk, 'choices') and len(chunk.choices) > 0:
                        delta = chunk.choices[0].delta
                        content_chunk = getattr(delta, 'content', None)
                        if content_chunk:
                            chunks.append(content_chunk)
                            if not json_output:
                                safe_print(content_chunk, nl=False)
                except Exception:
                    pass

                if hasattr(chunk, 'usage') and chunk.usage:
                    if hasattr(chunk.usage, 'model_dump'):
                        usage_data = chunk.usage.model_dump()
                    elif hasattr(chunk.usage, 'dict'):
                        usage_data = chunk.usage.dict()
                    else:
                        try:
                            usage_data = dict(chunk.usage)
                        except Exception:
                            pass
            reply = "".join(chunks)
            if not json_output and sys.stdout.isatty():
                click.echo("\n" + "-" * 40)

        if session:
            sd = session_data or {"id": session, "created": datetime.datetime.now().isoformat(), "messages": []}
            if system and not sd["messages"]:
                sd["messages"].append({"role": "system", "content": system})

            # Save only the raw text prompt (no point-in-time attachments/images) to prevent ballooning context
            sd["messages"].append({"role": "user", "content": raw_prompt})
            sd["messages"].append({"role": "assistant", "content": reply})
            save_session(session, sd)

        json_path, md_path = log_interaction(
            model=model,
            routed_model=routed_model,
            system=system,
            full_prompt=full_prompt,
            reply=reply,
            usage_data=usage_data,
            no_log=no_log
        )

        if not no_log:
            click.secho(f"Logged to {json_path} and {md_path}", fg="cyan", err=True)

        if not json_output:
            if not stream:
                if sys.stdout.isatty():
                    click.echo("-" * 40)
                safe_print(reply)
                if sys.stdout.isatty():
                    click.echo("-" * 40)
        else:
            json_res = {
                "model": model,
                "response": reply,
                "usage": usage_data,
                "timestamp": datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S"),
                "log_json": str(json_path) if json_path else None,
                "log_md": str(md_path) if md_path else None
            }
            click.echo(json.dumps(json_res, indent=2))

    except Exception as e:
        click.secho(f"API Error: {str(e)}", fg="red", err=True)
        sys.exit(1)

def call_llm(model: str, messages: List[Dict[str, str]], **opts) -> Tuple[str, dict]:
    """Single entry for litellm.completion. Returns (reply, usage_dict)."""
    import litellm
    routed, api_base, api_key = route_model(model)
    kwargs = {"model": routed, "messages": messages, "timeout": opts.get("timeout", float(os.environ.get("WALKIE_TIMEOUT", 120.0)))}
    if api_base: kwargs["api_base"] = api_base
    if api_key: kwargs["api_key"] = api_key
    for k in ("max_tokens", "temperature", "top_p", "stream", "extra_body", "response_format"):
        if opts.get(k) is not None:
            kwargs[k] = opts[k]
    try:
        resp = litellm.completion(**kwargs)
        reply = resp.choices[0].message.content or ""
        usage_data = {}
        if hasattr(resp, 'usage') and resp.usage:
            if hasattr(resp.usage, 'model_dump'):
                usage_data = resp.usage.model_dump()
            elif hasattr(resp.usage, 'dict'):
                usage_data = resp.usage.dict()
            else:
                try:
                    usage_data = dict(resp.usage)
                except Exception:
                    pass
        return reply, usage_data
    except Exception as e:
        raise RuntimeError(safe_error_handler(e)) from None

def extract_patches(reply: str) -> List[Tuple[str, str]]:
    """Extract REPLACEMENT_START / WITH / END blocks from text."""
    pattern = r"(?:<+|=+)\s*REPLACEMENT_START\s*(?:>+|=+)\n?(.*?)\n?(?:<+|=+)\s*REPLACEMENT_WITH\s*(?:>+|=+)\n?(.*?)\n?(?:<+|=+)\s*REPLACEMENT_END\s*(?:>+|=+)"
    return re.findall(pattern, reply, re.DOTALL)

def apply_patches(content: str, patches: List[Tuple[str, str]], *, normalize: bool = True) -> Tuple[str, Optional[str]]:
    """Apply replacement patches to content with normalized indentation fallback matching."""
    working = content
    for orig, rep in patches:
        if orig in working:
            if working.count(orig) > 1:
                return working, f"Ambiguous patch block: original block matches {working.count(orig)} times. Please provide more context."
            working = working.replace(orig, rep, 1)
            continue
        if normalize:
            orig_lines = [line.strip().replace("\t", " ") for line in orig.splitlines() if line.strip()]
            working_lines = working.splitlines()
            matched_starts = []

            for idx in range(len(working_lines) - len(orig_lines) + 1):
                window = [working_lines[idx+i].strip().replace("\t", " ") for i in range(len(orig_lines))]
                if window == orig_lines:
                    matched_starts.append(idx)

            if matched_starts:
                if len(matched_starts) > 1:
                    return working, f"Ambiguous patch block: normalized original block matches {len(matched_starts)} times. Please provide more context."

                matched_start = matched_starts[0]
                candidate_lines = working_lines[matched_start : matched_start + len(orig_lines)]
                candidate = "\n".join(candidate_lines)
                if candidate in working:
                    # Dynamically re-indent `rep`
                    leading_ws = ""
                    if candidate_lines:
                        leading_ws = candidate_lines[0][:len(candidate_lines[0]) - len(candidate_lines[0].lstrip())]

                    rep_lines = rep.splitlines()
                    if rep_lines:
                        non_blank = [line for line in rep_lines if line.strip()]
                        if non_blank:
                            rep_leading_ws = min((line[:len(line) - len(line.lstrip())] for line in non_blank), key=len)
                        else:
                            rep_leading_ws = ""

                        adjusted_rep_lines = []
                        for r_line in rep_lines:
                            if r_line.strip() == "":
                                adjusted_rep_lines.append("")
                            elif r_line.startswith(rep_leading_ws):
                                adjusted_rep_lines.append(leading_ws + r_line[len(rep_leading_ws):])
                            else:
                                adjusted_rep_lines.append(leading_ws + r_line.lstrip())
                        rep = "\n".join(adjusted_rep_lines)

                    working = working.replace(candidate, rep, 1)
                    continue
        return working, f"Original block not found:\n```\n{orig}\n```"
    return working, None

@cli.command()
@click.argument('file', type=click.Path(exists=True))
@click.option('--task', '-t', required=True, help="Description of the task/changes required.")
@click.option('--model', '-m', default="nvidia/z-ai/glm-5.2", help="Model to query (defaults to nvidia/z-ai/glm-5.2).")
@click.option('--system', '-s', default="", help="Optional system prompt.")
@click.option('--attach', '-a', multiple=True, type=click.Path(exists=True), help="Optional multiple attached files.")
@click.option('--dry-run', is_flag=True, help="Compile changes and show them without saving to disk.")
@click.option('--no-log', is_flag=True, help="Disable interaction logging.")
@click.option('--retries', '-r', type=int, default=3, help="Number of automatic self-correction retries if patching fails.")
@click.option('--line-range', '-L', help="Line range in format start-end (e.g. 100-150) to target, saving tokens by omitting the rest of the file context.")
@click.option('--verify-model', '-V', help="Secondary model name to use as an independent code auditor to cross-check patches for hallucinations.")
@click.option('--chain-model', '-c', multiple=True, help="Sequential models after the primary model to refine changes.")
@click.option('--keep-comments', is_flag=True, help="Disable comment stripping (comments are stripped by default).")
@click.option('--no-experience', is_flag=True, help="Disable experience learning and loading lessons from past sessions.")
@click.option('--no-context-packet', is_flag=True, help="Disable injection of target-scoped ContextPacket.")
@click.option('--session', help="Persist/continue a compact session (task + diffs) across invocations.")
def consult(file, task, model, system, attach, dry_run, no_log, retries, line_range, verify_model, chain_model, keep_comments, no_experience, no_context_packet, session):
    """Automate surgical patching of files with a self-correcting model feedback harness."""
    if line_range:
        keep_comments = True

    # Sanitize inputs to prevent path traversal
    s_file = sanitize_path(file)
    try:
        with open(s_file, 'r', encoding='utf-8') as f:
            file_content = f.read()
    except Exception as e:
        click.secho(f"Error reading target file {file}: {str(e)}", fg="red", err=True)
        sys.exit(1)

    lines = file_content.splitlines()
    start_line = None
    end_line = None
    targeted_content = file_content
    file_ext = Path(s_file).suffix.lower().lstrip(".")

    if line_range:
        try:
            start_str, end_str = line_range.split('-')
            start_line = int(start_str.strip())
            end_line = int(end_str.strip())
            if start_line < 1 or end_line < start_line:
                raise ValueError("Line numbers must be positive and start_line <= end_line.")
            end_line = min(end_line, len(lines))
            start_idx = max(0, start_line - 1 - 5)
            end_idx = min(len(lines), end_line + 5)
            targeted_content = "\n".join(lines[start_idx:end_idx])
            click.secho(f"Targeting line range {start_line}-{end_line} (context window size: {end_idx - start_idx} lines)", fg="cyan", err=True)
        except Exception as e:
            click.secho(f"Error parsing --line-range '{line_range}': {str(e)}. Using entire file.", fg="yellow", err=True)
            line_range = None

    system_prompt = system or (
        "You are a coding assistant designed to automatically apply surgical patches to source code files. "
        "When modifying provided code, you MUST output STRICTLY the replacement blocks in the following format. "
        "Do not add any conversational fluff, markdown formatting, or explanations outside of these blocks.\n\n"
        "<<<< REPLACEMENT_START >>>>\n"
        "[exact original code blocks to match]\n"
        "==== REPLACEMENT_WITH ====\n"
        "[new replacement code blocks]\n"
        "<<<< REPLACEMENT_END >>>>\n\n"
        "Provide one block per intended change. Ensure the exact original code block matches the source file perfectly, "
        "including all whitespaces, tabs, and newlines."
    )
    if line_range:
        system_prompt += (
            f"\n\nCRITICAL: You are viewing a localized segment (lines {start_line}-{end_line}) of the larger file '{Path(s_file).name}'. "
            "Do not add new imports or redeclare classes/functions that are defined globally. Focus ONLY on modifying this segment in place. "
            "Assume all global imports and variables are already available."
        )

    if not no_context_packet:
        try:
            import indexer
            idx = indexer.build_or_update_symbols_index(Path.cwd(), force_walk=True)
            packet = indexer.compile_context_packet(Path(s_file), Path.cwd(), idx)
            if packet:
                system_prompt += f"\n\n{packet}"
        except Exception as e:
            click.secho(f"Warning: Failed to compile ContextPacket: {str(e)}", fg="yellow", err=True)


    if not no_experience:
        system_prompt += load_experience_prompt(file_ext)

    if session and attach:
        click.secho("Notice: Attachments are point-in-time context and will not be saved into the session history.", fg="cyan", err=True)

    session_data = load_session(session) if session else None

    base_user_prompt = f"Task: {task}\n\nTarget File: {s_file}\n"

    if session_data:
        turns = session_data.get('turns', [])[-SESSION_INJECT_TURNS:]
        if turns:
            block = ["\n### Prior work in THIS session (oldest → newest):"]
            for t in turns:
                block.append(f"- [{t.get('file')}] {t.get('task')}")
                for d in t.get('diffs', []):
                    block.append(d)
            base_user_prompt += "\n" + "\n".join(block) + "\n"
        click.secho(f"Continuing session '{session}' ({len(session_data.get('turns', []))} prior turns).", fg="cyan", err=True)
    elif session:
        click.secho(f"Starting new session '{session}'.", fg="cyan", err=True)
    if line_range:
        base_user_prompt += f"Target Line Range: {start_line}-{end_line}\n"
    base_user_prompt += f"```\n{targeted_content}\n```\n"

    if attach:
        attachment_blocks = []
        for file_path in attach:
            s_attach_file = sanitize_path(file_path)
            try:
                with open(s_attach_file, 'r', encoding='utf-8', errors='ignore') as f:
                    attach_content = f.read()
                if not keep_comments:
                    attach_content = _strip_comments(attach_content, s_attach_file.suffix)
                attachment_blocks.append(
                    f"\n---\nAttached File: {s_attach_file.name}\n```\n{attach_content}\n```"
                )
            except Exception as e:
                click.secho(f"Warning: Could not read attachment {file_path}: {str(e)}", fg="yellow", err=True)
        if attachment_blocks:
            base_user_prompt += "\n\n### Attached Files Context:\n" + "\n".join(attachment_blocks)

    models_chain = [model] + list(chain_model)
    working_content = file_content
    prior_diffs = []
    final_patches = []
    usage_by_model = {}

    for step_idx, chain_m in enumerate(models_chain):
        is_final = (step_idx == len(models_chain) - 1)
        if step_idx > 0:
            click.secho(f"Chaining to next model ({chain_m})...", fg="yellow", err=True)

        user_prompt = base_user_prompt
        # For chained steps, use working content and attach compact diffs of prior steps
        if step_idx > 0:
            current_segment = working_content
            if line_range:
                w_lines = working_content.splitlines()
                start_idx = max(0, start_line - 1 - 5)
                end_idx = min(len(w_lines), end_line + 5)
                current_segment = "\n".join(w_lines[start_idx:end_idx])

            user_prompt = f"Task: {task}\n\nTarget File (Current state after prior chain steps):\n"
            if line_range:
                user_prompt += f"Target Line Range: {start_line}-{end_line}\n"
            user_prompt += f"```\n{current_segment}\n```\n"
            if prior_diffs:
                user_prompt += "\n### Diffs applied by earlier models in this chain:\n" + "\n".join(prior_diffs)

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        attempt = 0
        last_error_for_learning = None
        while attempt <= retries:
            if attempt > 0:
                click.secho(f"Retrying chain step {chain_m} (Attempt {attempt}/{retries})...", fg="yellow", err=True)
            else:
                click.secho(f"Consulting model: {chain_m}...", fg="yellow", err=True)

            try:
                reply, usage = call_llm(chain_m, messages)
                usage_by_model[f"{chain_m}#step{step_idx}_attempt{attempt}"] = usage

                # Log the interaction
                json_path, md_path = log_interaction(
                    model=chain_m,
                    routed_model=route_model(chain_m)[0],
                    system=system_prompt,
                    full_prompt=user_prompt,
                    reply=reply,
                    usage_data=usage,
                    no_log=no_log
                )
                if not no_log:
                    click.secho(f"Logged to {json_path} and {md_path}", fg="cyan", err=True)

            except Exception as e:
                click.secho(f"Error during LLM call: {safe_error_handler(e)}", fg="red", err=True)
                sys.exit(1)

            patches = extract_patches(reply)
            error_feedback = None

            if not patches:
                error_feedback = (
                    "Error: No valid replacement blocks found. Expected format:\n"
                    "<<<< REPLACEMENT_START >>>>\n"
                    "[exact original code blocks to match]\n"
                    "==== REPLACEMENT_WITH ====\n"
                    "[new replacement code blocks]\n"
                    "<<<< REPLACEMENT_END >>>>"
                )
            else:
                # If we are in line range, only apply inside slice
                if line_range:
                    w_lines = working_content.splitlines()
                    start_idx = max(0, start_line - 1 - 5)
                    end_idx = min(len(w_lines), end_line + 5)
                    segment_content = "\n".join(w_lines[start_idx:end_idx])

                    candidate_segment, err = apply_patches(segment_content, patches)
                    if err:
                        error_feedback = err
                    else:
                        header = "\n".join(w_lines[:start_idx])
                        footer = "\n".join(w_lines[end_idx:])
                        candidate_content = ""
                        if header:
                            candidate_content += header + "\n"
                        candidate_content += candidate_segment
                        if footer:
                            candidate_content += "\n" + footer
                else:
                    candidate_content, err = apply_patches(working_content, patches)
                    if err:
                        error_feedback = err

            if error_feedback:
                click.secho(f"Patch verification failed on attempt: {error_feedback}", fg="red", err=True)
                last_error_for_learning = error_feedback
                if attempt < retries:
                    messages.append({"role": "assistant", "content": reply})
                    messages.append({
                        "role": "user",
                        "content": f"The patch application failed with the following error:\n{error_feedback}\n\nPlease analyze the code and generate a corrected patch block."
                    })
                    attempt += 1
                    continue
                else:
                    click.secho("Error: Self-correction limit reached. Unable to generate a valid patch.", fg="red", err=True)
                    sys.exit(1)

            # Success at this step
            if attempt > 0 and last_error_for_learning and not no_experience:
                lesson = abstract_lesson(last_error_for_learning, attempt, file_ext)
                if lesson:
                    save_experience(file_ext, lesson)

            if not is_final:
                working_content = candidate_content
                # Save compact diff log for the next model
                for o, n in patches:
                    prior_diffs.append(f"--- Original Block ---\n{o[:400]}\n=== Replaced With ===\n{n[:400]}")
            else:
                final_patches = patches
                working_content = candidate_content
            break

    # Final Syntax and Auditor validations
    error_feedback = None
    file_ext = Path(s_file).suffix.lower()
    if file_ext == '.py':
        try:
            compile(working_content, s_file, 'exec')
        except SyntaxError as se:
            error_feedback = f"Syntax Error check failed for Python file:\n{str(se)}"

    if not error_feedback and verify_model:
        click.secho(f"Cross-checking final patches with auditor model {verify_model}...", fg="yellow", err=True)
        verify_system = "You are an independent, strict code auditor. Review patches for correctness and hallucinations.\n"
        if line_range:
            verify_system += f"NOTE: Patch targets localized lines {start_line}-{end_line} of {Path(s_file).name}.\n"

        verify_prompt = f"Task: {task}\nTarget: {Path(s_file).name}\nProposed Changes:\n"
        for idx, (orig, rep) in enumerate(final_patches, 1):
            verify_prompt += f"Block #{idx}:\nOriginal:\n```\n{orig}\n```\nReplacement:\n```\n{rep}\n```\n"
        verify_prompt += (
            "\nRespond strictly in JSON format matching this schema:\n"
            "{\n  \"verdict\": \"PASS\" or \"FAIL\",\n  \"reason\": \"Description of issues if FAIL, or empty string if PASS\"\n}\n"
        )

        try:
            reply_verify, v_usage = call_llm(verify_model, [
                {"role": "system", "content": verify_system},
                {"role": "user", "content": verify_prompt}
            ], max_tokens=500)
            usage_by_model[f"{verify_model}#verify"] = v_usage

            # JSON Parse verification
            json_content = reply_verify
            if "```json" in json_content:
                json_content = json_content.split("```json", 1)[1].split("```", 1)[0]
            elif "```" in json_content:
                json_content = json_content.split("```", 1)[1].split("```", 1)[0]

            import json as json_lib
            verify_data = json_lib.loads(json_content.strip())
            verdict = verify_data.get("verdict", "").strip().upper()
            reason = verify_data.get("reason", "").strip()

            if verdict == "FAIL":
                error_feedback = f"Auditor Review Failed (Hallucination Check): {reason}"
                click.secho(f"Auditor flagged failure: {reason}", fg="red", err=True)
            elif verdict == "PASS":
                click.secho("Auditor verification passed successfully!", fg="green", err=True)
        except Exception as ve:
            click.secho(f"Warning: Verification call to {verify_model} failed: {str(ve)}. Proceeding anyway.", fg="yellow", err=True)

    if error_feedback:
        click.secho(f"Validation loop flagged critical failure: {error_feedback}", fg="red", err=True)
        if not no_experience:
            try:
                lesson = abstract_lesson(error_feedback, 3, file_ext)
                if lesson:
                    save_experience(file_ext, lesson)
            except Exception:
                pass
        sys.exit(1)

    total_replacements = len(final_patches)
    if dry_run:
        click.secho("--- Dry Run Results ---", fg="cyan", bold=True)
        click.secho("Changes were successfully matched and parsed but not saved to disk.", fg="yellow")
        click.secho(f"Total patches applied: {total_replacements}", fg="cyan")
        click.echo("\n" + "="*40 + " Proposed File Content " + "="*40 + "\n")
        safe_print(working_content)
        click.echo("\n" + "="*40 + " End of Proposed Content " + "="*40)
    else:
        try:
            with open(s_file, 'w', encoding='utf-8') as f:
                f.write(working_content)
            click.secho(f"Success! Applied {total_replacements} patch(es) to {file}.", fg="green")
            if session:
                sd = session_data or {"id": session, "created": datetime.datetime.now().isoformat(), "turns": []}
                sd["turns"].append({
                    "ts": datetime.datetime.now().isoformat(),
                    "file": str(s_file),
                    "task": task,
                    "diffs": [f"--- Original ---\n{o[:SESSION_DIFF_CHAR_CAP]}\n=== With ===\n{n[:SESSION_DIFF_CHAR_CAP]}" for o, n in final_patches],
                })
                save_session(session, sd)
        except Exception as e:
            click.secho(f"Error saving file {file}: {str(e)}", fg="red", err=True)
            sys.exit(1)
@cli.command()
@click.option('--output', '-o', default="llm_context.yaml", help="Path to write the generated project map.")
@click.option('--exclude', '-e', multiple=True, help="Glob patterns of files/directories to exclude.")
def map(output, exclude):
    """Generate a highly compressed, token-efficient YAML map of the codebase for LLMs."""
    try:
        import indexer
        import yaml as yaml_lib
    except ImportError as e:
        click.secho(f"Missing dependency: {str(e)}", fg="red", err=True)
        sys.exit(1)

    click.secho("Scanning workspace and updating symbols index...", fg="yellow", err=True)
    idx = indexer.build_or_update_symbols_index(Path.cwd(), force_walk=True)

    # Project indexer data to legacy map format
    root_path = Path.cwd()
    project_map = {
        "project_name": root_path.name,
        "directory_structure": [],
        "python_modules": {},
        "config_files": {},
        "dependencies": [],
        "mermaid_dependencies": ""
    }

    files = idx.get('files', {})
    for rel_path, data in files.items():
        if data.get('language') == 'python':
            project_map["python_modules"][rel_path] = {
                "classes": data.get('classes', []),
                "functions": data.get('functions', [])
            }
            project_map["directory_structure"].append(rel_path)

    # Simple mermaid graph from reverse_deps
    mermaid_lines = ["graph TD"]
    has_edges = False
    reverse_deps = idx.get('reverse_deps', {})
    modules_list = [Path(p).stem for p in files.keys()]

    for mod, importers in reverse_deps.items():
        for imp_file in importers:
            imp_stem = Path(imp_file).stem
            if mod in modules_list and mod != imp_stem:
                mermaid_lines.append(f"    {imp_stem} --> {mod}")
                has_edges = True

    if has_edges:
        project_map["mermaid_dependencies"] = "\n".join(mermaid_lines)
    else:
        project_map["mermaid_dependencies"] = "graph TD\n    NoLocalDependencies"

    try:
        with open(output, 'w', encoding='utf-8') as f:
            yaml_lib.dump(project_map, f, sort_keys=False)
        click.secho(f"Success! Codebase map saved to {output}", fg="green")
    except Exception as e:
        click.secho(f"Error saving project map: {str(e)}", fg="red", err=True)
        sys.exit(1)


@cli.command(name='session')
@click.argument('action', type=click.Choice(['list', 'show', 'clear']))
@click.argument('session_id', required=False)
def session_cmd(action, session_id):
    """Manage saved sessions."""
    SESSION_DIR.mkdir(parents=True, exist_ok=True)
    if action == 'list':
        for p in sorted(SESSION_DIR.glob("*.json")):
            try:
                d = json.loads(p.read_text(encoding='utf-8'))
                n = len(d.get('turns', d.get('messages', [])))
                click.echo(f"{p.stem:30} turns/msgs={n:<4} updated={d.get('updated','?')}")
            except Exception:
                click.echo(f"{p.stem:30} [unreadable]")
    elif action == 'show' and session_id:
        d = load_session(session_id)
        click.echo(json.dumps(d, indent=2) if d else "Not found.")
    elif action == 'clear' and session_id:
        p = _session_path(session_id)
        if p.exists():
            p.unlink()
            click.secho(f"Cleared session '{session_id}'.", fg="green")
        else:
            click.secho("Not found.", fg="yellow")

# ── Discovery commands ─────────────────────────────────────────────────────────

@cli.command("discover")
@click.option("--provider", "-p", default="all",
              type=click.Choice(["all", "openrouter", "nvidia"], case_sensitive=False),
              help="Limit scan to a specific provider.")
@click.option("--coding-only", is_flag=True, help="Show only models tagged for coding/reasoning.")
@click.option("--force", is_flag=True, help="Bypass 24h cache and force fresh scan.")
@click.option("--json-output", is_flag=True, help="Output as JSON.")
def discover(provider, coding_only, force, json_output):
    """Scan providers for free LLM models and update the local model registry."""
    import discovery as disc

    click.secho("[SCAN] Scanning for free models...", fg="cyan", err=True)

    registry, diff = disc.run_discovery(force=force)
    logical = registry.get("logical_models", {})

    if coding_only:
        logical = {k: v for k, v in logical.items()
                   if any(t in v.get("tags", []) for t in ("coding", "reasoning"))}

    if provider != "all":
        prov_upper = provider.upper()
        logical = {
            k: {**v, "routes": [r for r in v["routes"] if r["provider"] == prov_upper]}
            for k, v in logical.items()
        }
        logical = {k: v for k, v in logical.items() if v["routes"]}

    if json_output:
        click.echo(json.dumps({"models": logical, "diff": diff}, indent=2))
        return

    if not logical:
        click.secho("No free models found matching the criteria.", fg="yellow")
        return

    priority = registry.get("provider_priority", disc.PROVIDER_PRIORITY)
    rows = disc.rank_free_models(registry, use_case="coding")
    filtered_rows = [(c, e) for c, e in rows if c in logical]

    click.echo("")
    # Table header
    click.echo(f"  {'Canonical':<22} {'Providers':<26} {'Context':>8}  {'Tags':<22} {'Routes':>6}")
    click.echo("  " + "-" * 88)

    for canonical, entry in filtered_rows:
        routes = [r for r in entry["routes"] if r["provider"] in
                  {k for k in disc.PROVIDER_PRIORITY}]
        if not routes:
            continue
        pri_idx = disc.elect_primary_idx(routes, priority)
        provider_str = ", ".join(
            (r["provider"] + " *" if i == pri_idx else r["provider"])
            for i, r in enumerate(routes)
        )
        max_ctx = max((r.get("context_length") or 0) for r in routes)
        ctx_str = f"{max_ctx // 1000}K" if max_ctx >= 1000 else (str(max_ctx) if max_ctx else "-")
        tags_str = ", ".join(entry.get("tags", [])[:3])
        route_count = len(routes)
        click.echo(f"  {canonical:<22} {provider_str:<26} {ctx_str:>8}  {tags_str:<22} {route_count:>6}")

    if diff["added"]:
        click.echo("")
        click.secho("[NEW] since last scan: " + ', '.join(diff['added']), fg="green")
    if diff["removed"]:
        click.secho("[REMOVED] since last scan: " + ', '.join(diff['removed']), fg="yellow")

    click.echo("")
    click.secho(f"  Total: {len(filtered_rows)} model(s). To connect: walkie setup", fg="cyan")


@cli.command("status")
@click.option("--sweep", is_flag=True,
              help="Live-probe each provider with a real API call (slow but accurate).")
@click.option("--json-output", is_flag=True, help="Output as JSON.")
def status(sweep, json_output):
    """Show health status for all configured LLM providers."""
    import discovery as disc

    registry = disc.load_registry()

    # Count fallback routes per provider
    provider_route_counts: Dict[str, int] = {}
    for entry in registry.get("logical_models", {}).values():
        for route in entry.get("routes", []):
            p = route["provider"]
            provider_route_counts[p] = provider_route_counts.get(p, 0) + 1

    def _probe(model_id: str, api_base: Optional[str], api_key: str):
        import time as _time
        t0 = _time.monotonic()
        try:
            reply, _ = call_llm(
                model=model_id,
                messages=[{"role": "user", "content": "Hi"}],
                max_tokens=3,
                no_log=True,
            )
            latency = (_time.monotonic() - t0) * 1000
            return True, latency, None
        except Exception as e:
            return False, None, str(e)

    if sweep:
        click.secho("[WAIT] Running live probes (this may take ~30s)...", fg="yellow", err=True)
        results = disc.sweep_configured_providers(_probe)
        try:
            p = CONFIG_DIR / "health.json"
            health_cache = {}
            if p.exists():
                try:
                    health_cache = json.loads(p.read_text()).get("models", {})
                except Exception:
                    pass
            for res in results:
                health_cache[res["model"]] = {
                    "ok": res["status"] == "ok",
                    "timestamp": datetime.datetime.utcnow().isoformat() + "Z"
                }
            p.parent.mkdir(parents=True, exist_ok=True)
            if p.exists():
                try:
                    p.unlink()
                except Exception:
                    pass
            fd = os.open(str(p), os.O_CREAT | os.O_WRONLY, 0o600)
            with os.fdopen(fd, "w") as f:
                json.dump({"models": health_cache}, f)
        except Exception:
            pass
    else:
        # Use cached health data
        health_cache = {}
        try:
            p = CONFIG_DIR / "health.json"
            if p.exists():
                health_cache = json.loads(p.read_text()).get("models", {})
        except Exception:
            pass

        results = []
        for name, info in PROVIDERS.items():
            env_val = os.getenv(info["env_var"])
            test_model = info["test_model"]
            cached = health_cache.get(test_model, {})
            if not env_val:
                status_str = "no_key"
                latency = None
            elif cached.get("ok"):
                status_str = "ok"
                latency = None
            elif cached and not cached.get("ok"):
                status_str = "dead"
                latency = None
            else:
                status_str = "unknown"
                latency = None
            results.append({
                "provider": name,
                "has_key": bool(env_val),
                "status": status_str,
                "model": test_model,
                "latency_ms": latency,
                "error": None,
            })

    if json_output:
        click.echo(json.dumps(results, indent=2))
        return

    click.echo("")
    click.echo(f"  {'Provider':<13} {'Key?':<8} {'Test Model':<30} {'Status':<12} {'Latency':>8}")
    click.echo("  " + "-" * 75)

    active = dead = no_key = 0
    for r in results:
        key_str = (f"[OK] {os.getenv(PROVIDERS[r['provider']]['env_var'], '')[:6]}.."
                   if r["has_key"] else "[NO]")
        if r["status"] == "ok":
            status_icon = "[GREEN] OK"
            active += 1
        elif r["status"] == "dead":
            status_icon = "[RED] DEAD"
            dead += 1
        elif r["status"] == "no_key":
            status_icon = "[GREY] No key"
            no_key += 1
        else:
            status_icon = "[YELLOW] Unknown"

        lat_str = f"{r['latency_ms']:.0f}ms" if r.get("latency_ms") else "-"
        routes_hint = f"({provider_route_counts.get(r['provider'], 0)} routes)"
        click.echo(
            f"  {r['provider']:<13} {key_str:<8} {r['model']:<30} {status_icon:<12} {lat_str:>8}  {routes_hint}"
        )

    click.echo("")
    total = len(results)
    click.secho(f"  Active: {active}/{total} | Dead: {dead}/{total} | Unconfigured: {no_key}/{total}", fg="cyan")

    for r in results:
        if r["status"] == "dead":
            click.secho(f"\n[WARN]  {r['provider']} appears dead. Run: walkie setup", fg="yellow")

    if not sweep:
        click.secho("\n  Tip: Run `walkie status --sweep` for a live probe of each provider.", fg="cyan", err=True)

@cli.command("evolve")
@click.option("--context", required=True, help="JSON string or file path containing the CoT abstract.")
@click.option("-m", "--model", default="nvidia/z-ai/glm-5.2", help="External LLM to consult.")
def evolve(context, model):
    """Consult an external LLM to critique recent CoT and safely inject a new rule."""
    import evolve as ev
    from pathlib import Path

    # Check if context is a file
    if Path(context).exists():
        with open(context, "r", encoding="utf-8") as f:
            cot_text = f.read()
    else:
        cot_text = context

    click.secho("[EVOLVE] Sending CoT abstract to external LLM...", fg="cyan")

    prompt = f"{ev.ARCHITECT_SYSTEM_PROMPT}\n\n### CoT Abstract\n{cot_text}"
    try:
        reply, _ = call_llm(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1000,
            no_log=True
        )
    except Exception as e:
        click.secho(f"\n[ERROR] External LLM consultation failed: {e}", fg="red")
        return

    try:
        data = ev.parse_evolution_json(reply)
    except ValueError as e:
        click.secho(f"\n[ERROR] {e}", fg="red")
        return

    critique = data["critique"]
    rule = data["suggested_rule"]

    click.echo(f"\n[CRITIQUE] {critique}")
    click.echo(f"[SUGGESTED RULE] {rule['content']}")

    target_file = Path(rule["target_file"])
    if not target_file.is_absolute():
        target_file = Path.cwd() / rule["target_file"]

    if not target_file.exists():
        click.secho(f"\n[ERROR] Target file {target_file} does not exist.", fg="red")
        return

    click.echo(f"\n[BACKUP] Saving backup of {target_file.name}...")
    try:
        backup_path = ev.backup_rules(target_file)
        click.secho(f"Backup saved to: {backup_path}", fg="green")
    except Exception as e:
        click.secho(f"[ERROR] Failed to backup: {e}", fg="red")
        return

    click.echo("[INJECT] Applying rule...")
    success, msg = ev.inject_rule(target_file, rule["section_anchor"], rule["content"])

    if success:
        click.secho(f"[SUCCESS] Rule injected into {target_file.name} under <!-- EVOLVE_SECTION: {rule['section_anchor'].upper()} -->", fg="green")
        click.secho(f"If this rule breaks things, you can restore by running:", fg="yellow")
        click.secho(f"  walkie evolve-restore {backup_path.name}", fg="yellow")
    else:
        click.secho(f"[FAIL] {msg}", fg="red")


@cli.command("evolve-restore")
@click.argument("backup_filename", required=False)
def evolve_restore(backup_filename):
    """Restore a rule file from a backup."""
    import evolve as ev
    from pathlib import Path

    if not backup_filename:
        backups = ev.list_backups()
        if not backups:
            click.secho("No backups found.", fg="yellow")
            return
        click.secho("Available backups:", fg="cyan")
        for b in backups[:10]:
            click.echo(f"  {b}")
        click.echo("\nTo restore, run: walkie evolve-restore <filename>")
        return

    target_dir = Path.cwd()
    try:
        target_path = ev.restore_rules(backup_filename, target_dir)
        click.secho(f"[SUCCESS] Restored {target_path.name} from {backup_filename}", fg="green")
    except Exception as e:
        click.secho(f"[ERROR] {e}", fg="red")

def get_vendor(model_str: str) -> str:
    m_lower = model_str.lower()
    if "gemini" in m_lower or "google" in m_lower: return "google"
    if "claude" in m_lower or "anthropic" in m_lower: return "anthropic"
    if "deepseek" in m_lower: return "deepseek"
    if "glm" in m_lower or "z-ai" in m_lower or "zhipu" in m_lower: return "z-ai"
    if "qwen" in m_lower or "alibaba" in m_lower: return "qwen"
    if "gpt" in m_lower or "openai" in m_lower: return "openai"
    if "llama" in m_lower or "meta" in m_lower: return "meta"
    if "laguna" in m_lower or "poolside" in m_lower: return "poolside"
    if "nemotron" in m_lower or "nvidia" in m_lower: return "nvidia"

    # Fallback to route_model
    try:
        routed, _, _ = route_model(model_str)
        routed_lower = routed.lower()
        if "gemini" in routed_lower or "google" in routed_lower: return "google"
        if "claude" in routed_lower or "anthropic" in routed_lower: return "anthropic"
        if "gpt" in routed_lower or "openai" in routed_lower: return "openai"
        if "deepseek" in routed_lower: return "deepseek"
        if "glm" in routed_lower or "z-ai" in routed_lower: return "z-ai"
        if "laguna" in routed_lower or "poolside" in routed_lower: return "poolside"
        if "nemotron" in routed_lower or "nvidia" in routed_lower: return "nvidia"
    except Exception:
        pass
    parts = model_str.split('/')
    return parts[0].lower() if len(parts) > 1 else model_str.lower()


def validate_contract_schema(contract: dict) -> bool:
    """Validate that the contract structure matches the expected design contract schema."""
    required = ["meta", "tokens", "components", "rules", "enforcement"]
    if not all(k in contract for k in required):
        return False
    if not isinstance(contract.get("meta"), dict) or "version" not in contract["meta"]:
        return False
    tokens = contract.get("tokens")
    if not isinstance(tokens, dict):
        return False
    # Validate subkey types to prevent token_lint failures
    if "color" in tokens and not isinstance(tokens["color"], dict):
        return False
    if "spacing" in tokens and not isinstance(tokens["spacing"], list):
        return False
    if "radius" in tokens and not isinstance(tokens["radius"], list):
        return False
    if "font_size" in tokens and not isinstance(tokens["font_size"], list):
        return False
    return True


def parse_loop_patches(reply: str) -> List[Tuple[str, str, str]]:
    """Parse patches from Implementer output.
    Format:
    <<<<
    [file_path]
    [original code to replace]
    ====
    [replacement code]
    >>>>
    """
    pattern = re.compile(r"<<<<\s*\r?\n(.*?)\r?\n(.*?)\r?\n====\s*\r?\n(.*?)\r?\n>>>>", re.DOTALL)
    matches = pattern.findall(reply)
    patches = []
    for file_path, original, replacement in matches:
        patches.append((file_path.strip(), original, replacement))
    return patches

@cli.command("loop")
@click.option('--goal', required=True, help="User-stated goal to drive the loop.")
@click.option('--stop-cmd', required=True, help="Command that serves as ground-truth success oracle.")
@click.option('--design-contract', required=True, help="Path to the design contract YAML.")
@click.option('--gen-model', default="nvidia/z-ai/glm-5.2", help="Implementer (native LLM).")
@click.option('--audit-model', default="openrouter/google/gemini-2.5-flash:free", help="Auditor model (different vendor).")
@click.option('--redteam-model', default="zenmux/anthropic/claude-4-fable", help="Red Team model (different vendor).")
@click.option('--ui-gates', default="token-lint,component-usage", help="Gates to enforce (comma-separated).")
@click.option('--sandbox', default="worktree", type=click.Choice(["worktree", "none"]), help="Sandbox isolation mode.")
@click.option('--max-iterations', default=10, type=int, help="Max iterations before budget stop.")
@click.option('--cost-cap-usd', default=0.50, type=float, help="USD cost cap.")
@click.option('--session', required=True, help="Session ID to load/save loop trace.")
@click.option('--json-output', is_flag=True, help="Output final usage report in structured JSON.")
def loop_cmd(goal, stop_cmd, design_contract, gen_model, audit_model, redteam_model, ui_gates, sandbox, max_iterations, cost_cap_usd, session, json_output):
    """Goal-driven, multi-LLM, design-governed looping engine."""
    import subprocess
    import tempfile
    import shutil
    import yaml
    import hashlib
    import token_lint



    # startup vendor check
    v_gen = get_vendor(gen_model)
    v_aud = get_vendor(audit_model)
    v_red = get_vendor(redteam_model)
    vendors = {v_gen, v_aud, v_red}
    if len(vendors) < 3:
        click.secho(f"[ERROR] Start guard failed: Loop requires at least 3 distinct vendors to prevent self-preference bias.", fg="red", err=True)
        click.secho(f"Configured vendors: Implementer={v_gen}, Auditor={v_aud}, Red Team={v_red}", fg="yellow", err=True)
        sys.exit(1)

    # load Design Contract
    contract_path = Path(design_contract)
    if not contract_path.exists():
        click.secho(f"[ERROR] Design contract not found at {contract_path}", fg="red", err=True)
        sys.exit(1)

    with open(contract_path, "r", encoding="utf-8") as f:
        contract = yaml.safe_load(f)

    # Create sandbox
    cwd = Path.cwd()
    sandbox_path = cwd
    is_worktree = False

    if sandbox == "worktree":
        click.echo("[INIT] Creating git worktree sandbox...")
        try:
            # check if in git
            git_ok = subprocess.run(["git", "rev-parse", "--is-inside-work-tree"], capture_output=True, text=True)
            if git_ok.returncode == 0:
                head_commit = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
                import uuid
                temp_sandbox = Path(tempfile.gettempdir()) / f"walkie-sandbox-{session}-{uuid.uuid4().hex[:8]}"
                if temp_sandbox.exists():
                    subprocess.run(["git", "worktree", "prune"], capture_output=True)
                    shutil.rmtree(temp_sandbox, ignore_errors=True)

                subprocess.run(["git", "worktree", "add", "--detach", str(temp_sandbox), head_commit], check=True, capture_output=True)
                sandbox_path = temp_sandbox
                is_worktree = True
                click.secho(f"Sandbox created via git worktree: {sandbox_path}", fg="green")
            else:
                click.secho("Not in git repo, bypassing worktree sandbox.", fg="yellow")
        except Exception as e:
            click.secho(f"Warning: git worktree failed: {e}. Running in-place.", fg="yellow")

    # Accumulator structure
    accumulator = {
        "total_usd": 0.0,
        "iterations": 0,
        "outcome": "STUCK",
        "models": {},
        "roles": {
            "Implementer": {"input": 0, "output": 0, "usd": 0.0},
            "Auditor": {"input": 0, "output": 0, "usd": 0.0},
            "Red Team": {"input": 0, "output": 0, "usd": 0.0}
        },
        "history": []
    }

    class BudgetCapExceeded(Exception):
        pass

    def get_model_cost(model_name: str, prompt_tokens: int, completion_tokens: int) -> float:
        m_lower = model_name.lower()
        if ":free" in m_lower or "-free" in m_lower or "/free" in m_lower:
            return 0.0
        try:
            import litellm
            routed, _, _ = route_model(model_name)
            if ":free" in routed.lower() or "-free" in routed.lower() or "/free" in routed.lower():
                return 0.0
            cost = litellm.completion_cost(model=routed, prompt_tokens=prompt_tokens, completion_tokens=completion_tokens)
            if cost is not None:
                return float(cost)
        except Exception:
            pass
        in_p, out_p = 0.000002, 0.000006
        m_lower = model_name.lower()
        if any(x in m_lower for x in ("mini", "flash", "8b", "7b")):
            in_p, out_p = 0.00000015, 0.0000006
        elif any(x in m_lower for x in ("sonnet", "pro", "70b")):
            in_p, out_p = 0.000003, 0.000015
        elif any(x in m_lower for x in ("opus", "ultra")):
            in_p, out_p = 0.000015, 0.000075
        return (prompt_tokens * in_p) + (completion_tokens * out_p)

    def log_usage(model_name: str, role: str, usage: dict):
        if not usage: return
        in_t = usage.get("prompt_tokens", 0) or usage.get("input_tokens", 0) or 0
        out_t = usage.get("completion_tokens", 0) or usage.get("output_tokens", 0) or 0
        cost = get_model_cost(model_name, in_t, out_t)

        if model_name not in accumulator["models"]:
            accumulator["models"][model_name] = {"input": 0, "output": 0, "usd": 0.0}
        accumulator["models"][model_name]["input"] += in_t
        accumulator["models"][model_name]["output"] += out_t
        accumulator["models"][model_name]["usd"] += cost

        accumulator["roles"][role]["input"] += in_t
        accumulator["roles"][role]["output"] += out_t
        accumulator["roles"][role]["usd"] += cost
        accumulator["total_usd"] += cost

        if accumulator["total_usd"] >= cost_cap_usd:
            raise BudgetCapExceeded(f"Budget cap of ${cost_cap_usd:.2f} reached.")

    # Load session trace
    session_id = f"loop_{session}"
    sess_data = load_session(session_id) or {"session_id": session_id, "turns": []}

    # Tracking metrics to prevent oscillation / stuck
    last_diff_hash = None
    last_score = -1
    oscillation_count_diff = 0
    oscillation_count_score = 0
    patched_files_set = set()

    def get_in_scope_files(s_path, c_data):
        import fnmatch
        import os
        globs = c_data.get("enforcement", {}).get("token_lint", {}).get("scan_globs", ["**/*"])
        files_map = {}
        for root, _, files in os.walk(s_path):
            if any(x in root for x in ('.git', '.walkie', 'venv', 'node_modules', '__pycache__')): continue
            for file in files:
                f_path = Path(root) / file
                rel = f_path.relative_to(s_path).as_posix()
                if any(fnmatch.fnmatch(rel, g) for g in globs):
                    try:
                        files_map[rel] = f_path.read_text(encoding="utf-8")
                    except Exception:
                        pass
        return files_map

    # MAIN LOOP
    gates_list = [g.strip() for g in ui_gates.split(",")]
    import time

    try:
        for it in range(1, max_iterations + 1):
            it_start_time = time.time()
            accumulator["iterations"] = it
            click.echo(f"\n--- ITERATION {it} ---")

            # 1. OBSERVE (Run stop command)
            click.echo("[OBSERVE] Running stop oracle command in sandbox...")
            try:
                res_stop = subprocess.run(stop_cmd, shell=True, cwd=str(sandbox_path), capture_output=True, text=True, timeout=60.0)
                stop_code = res_stop.returncode
                stop_output = res_stop.stdout + "\n" + res_stop.stderr
            except subprocess.TimeoutExpired:
                stop_code = -1
                stop_output = "Command timed out after 60s."

            # Scan changed/patched files to evaluate design gates
            modified_files = {}
            if it == 1:
                modified_files = get_in_scope_files(sandbox_path, contract)
            else:
                for rel_f in patched_files_set:
                    f_path = sandbox_path / rel_f
                    if f_path.exists() and f_path.is_file():
                        try:
                            modified_files[rel_f] = f_path.read_text(encoding="utf-8")
                        except Exception:
                            pass
                if not modified_files:
                    modified_files = get_in_scope_files(sandbox_path, contract)

            # Design Contract Gates check
            gates_passed = True
            gate_feedback = ""

            if "token-lint" in gates_list and modified_files:
                gate_res = token_lint.run_gate(modified_files, str(contract_path))
                if not gate_res["passed"]:
                    gates_passed = False
                    gate_feedback += f"\n[token-lint] Design Contract violations:\n{gate_res['feedback']}"

            if "component-usage" in gates_list and modified_files:
                comps = contract.get("components", {})
                for rel_f, content in modified_files.items():
                    for comp_name, comp_cfg in comps.items():
                        canon_imp = comp_cfg.get("import")
                        if re.search(rf"\b{comp_name}\b", content):
                            imp_pattern = rf"import\s+.*\b{comp_name}\b.*\s+from\s+['\"]{re.escape(canon_imp)}['\"]"
                            if not re.search(imp_pattern, content):
                                if canon_imp in rel_f or rel_f.endswith(comp_name + ".tsx") or rel_f.endswith(comp_name + ".jsx"):
                                    continue
                                gates_passed = False
                                gate_feedback += f"\n[component-usage] File '{rel_f}' uses canonical component '{comp_name}' without the correct import: '{canon_imp}'"

            # Check Stop oracle condition
            if stop_code == 0 and gates_passed:
                click.secho(f"[STOP] Oracle conditions satisfied. stop-cmd passed and design gates are clean!", fg="green")
                accumulator["outcome"] = "SUCCESS"
                break

            # 2. RED TEAM (Adversarial critique)
            click.echo("[RED TEAM] Searching for concrete reproducible defects...")
            rt_messages = [
                {"role": "system", "content": "You are an adversarial Red Team critic. Locate reproducible defects in the code relative to the Design Contract and goal."},
                {"role": "user", "content": f"Goal: {goal}\nModified Files:\n" + "\n".join(f"--- File: {k} ---\n{v[:4000]}" for k, v in modified_files.items()) + f"\n\nStop Command Output:\n{stop_output[:2000]}\nOutput a JSON object with: 'defect_found' (bool), 'description' (string), 'reproducible_case' (string), 'amendment_proposal' (optional dictionary of missing contract tokens to merge under 'tokens')."}
            ]
            try:
                rt_reply, rt_usage = call_llm(redteam_model, rt_messages, response_format={"type": "json_object"})
                log_usage(redteam_model, "Red Team", rt_usage)
                rt_data = json.loads(rt_reply)
            except Exception as e:
                rt_data = {"defect_found": False, "description": f"Failed to call Red Team: {e}"}

            # 3. ACT (Implementer Repairs)
            click.echo("[ACT] Requesting Implementer to patch code...")
            rt_desc = rt_data.get('description', '') if isinstance(rt_data, dict) and rt_data.get('defect_found') else ''
            rt_repro = f"\nReproducible defect case:\n{rt_data.get('reproducible_case')}" if isinstance(rt_data, dict) and rt_data.get('reproducible_case') else ""
            imp_prompt = f"""Goal: {goal}
Stop Command Output:
{stop_output[:2000]}

Design Contract Constraints:
{yaml.dump(contract.get('tokens', {}))}

Current violations:
{gate_feedback}
{rt_data.get('description', '') if rt_data.get('defect_found') else ''}

Fix these issues and return the correct file patches. Use the standard walkie loop patch blocks:
<<<<
[file_path]
[original code to replace]
====
[replacement code]
>>>>
"""
            imp_messages = [
                {"role": "system", "content": "You are a professional software builder. Implement fixes following the Design Contract exactly."},
                {"role": "user", "content": imp_prompt}
            ]

            try:
                imp_reply, imp_usage = call_llm(gen_model, imp_messages)
                log_usage(gen_model, "Implementer", imp_usage)
                patches = parse_loop_patches(imp_reply)

                # Apply patches in sandbox CWD
                diff_hashes = []
                format_warnings = []
                for filepath, original, replacement in patches:
                    if not filepath or ("/" not in filepath and "\\" not in filepath and "." not in filepath) or len(filepath) > 100:
                        format_warnings.append(f"Rejected patch block filepath: '{filepath}' does not look like a valid relative path.")
                        continue
                    target_p = sandbox_path / filepath
                    if not target_p.exists():
                        format_warnings.append(f"Target file '{filepath}' to patch does not exist in the sandbox.")
                        continue

                    orig_content = target_p.read_text(encoding="utf-8")
                    if original in orig_content:
                        new_content = orig_content.replace(original, replacement)
                        target_p.write_text(new_content, encoding="utf-8")
                        diff_hashes.append(hashlib.md5(new_content.encode("utf-8")).hexdigest())
                        patched_files_set.add(filepath)
                    else:
                        format_warnings.append(f"Original block to replace in '{filepath}' not found exactly. Check whitespace/newlines.")

                if format_warnings:
                    gate_feedback += "\n[patch-errors] The following patches failed to apply:\n" + "\n".join(f"- {w}" for w in format_warnings)

                # Detect oscillation via diff hash
                current_diff_hash = "".join(diff_hashes)
                if current_diff_hash == last_diff_hash:
                    oscillation_count_diff += 1
                else:
                    oscillation_count_diff = 0
                last_diff_hash = current_diff_hash

                if oscillation_count_diff >= 2:
                    click.secho("[STOP] Loop stuck (diff oscillation detected). Discarding sandbox.", fg="yellow")
                    accumulator["outcome"] = "STUCK"
                    break

            except Exception as e:
                click.secho(f"Warning: Implementer call failed: {e}", fg="red")

            # Rebuild modified_files from sandbox to ensure Panel (Auditor) grades fresh content
            modified_files = {}
            for rel_f in patched_files_set:
                f_path = sandbox_path / rel_f
                if f_path.exists() and f_path.is_file():
                    try:
                        modified_files[rel_f] = f_path.read_text(encoding="utf-8")
                    except Exception:
                        pass
            if not modified_files:
                modified_files = get_in_scope_files(sandbox_path, contract)

            # 4. PANEL (Auditor Grading)
            click.echo("[PANEL] Requesting Auditor evaluation...")
            aud_prompt = f"""Evaluate the current sandbox implementation against the goal: '{goal}'.
Modified Files:
""" + "\n".join(f"--- File: {k} ---\n{v[:4000]}" for k, v in modified_files.items()) + f"""
JSON output only containing:
{{
  "violations": ["list of design token or functional errors"],
  "score": 0 to 100,
  "verdict": "CONTINUE" or "REPAIR" or "SUCCESS",
  "reason": "Detailed critique",
  "amendment_proposal": "optional dictionary of proposed Design Contract token changes to merge under 'tokens'"
}}"""
            aud_messages = [
                {"role": "system", "content": "You are a Design Contract Auditor. Check conformance to style scales and component usages."},
                {"role": "user", "content": aud_prompt}
            ]
            try:
                aud_reply, aud_usage = call_llm(audit_model, aud_messages, response_format={"type": "json_object"})
                log_usage(audit_model, "Auditor", aud_usage)
                aud_data = json.loads(aud_reply)

                # Progress tracking via score plateau
                current_score = aud_data.get("score", 0)
                if current_score <= last_score and it > 1:
                    oscillation_count_score += 1
                else:
                    oscillation_count_score = 0
                last_score = current_score

                if oscillation_count_score >= 3:
                    click.secho("[STOP] Loop stuck (score plateau detected). Discarding sandbox.", fg="yellow")
                    accumulator["outcome"] = "STUCK"
                    break
            except Exception as e:
                aud_data = {"score": 50, "verdict": "CONTINUE", "reason": f"Auditor failed: {e}"}

            # Consensus-gated Contract Amendment (requires both external models)
            rt_amend = (rt_data.get("amendment_proposal") if isinstance(rt_data, dict) else None)
            aud_amend = (aud_data.get("amendment_proposal") if isinstance(aud_data, dict) else None)
            if rt_amend and aud_amend and v_aud != v_red:
                has_updates = False
                import copy
                temp_contract = copy.deepcopy(contract)
                # Merge proposed tokens/keys
                if isinstance(rt_amend, dict) and rt_amend:
                    temp_contract.setdefault("tokens", {}).update(rt_amend)
                    has_updates = True
                if isinstance(aud_amend, dict) and aud_amend:
                    temp_contract.setdefault("tokens", {}).update(aud_amend)
                    has_updates = True

                if has_updates:
                    click.secho("[CONSENSUS] Panel consensus achieved on Design Contract amendment!", fg="green")
                    temp_contract["meta"]["version"] += 1
                    if "amended_by" not in temp_contract["meta"]:
                        temp_contract["meta"]["amended_by"] = []
                    temp_contract["meta"]["amended_by"].append(f"iter_{it}_consensus")

                    # Perform schema validation
                    if validate_contract_schema(temp_contract):
                        contract = temp_contract
                        # Atomic write via tmp replace
                        tmp_contract = contract_path.parent / (contract_path.name + ".tmp")
                        with open(tmp_contract, "w", encoding="utf-8") as f:
                            yaml.safe_dump(contract, f)
                        tmp_contract.replace(contract_path)

            # Re-run stop command right after ACT/verify phase for next iteration or exit validation
            click.echo("[VERIFY] Re-running stop command after repair phase...")
            try:
                res_stop = subprocess.run(stop_cmd, shell=True, cwd=str(sandbox_path), capture_output=True, text=True, timeout=60.0)
                stop_code = res_stop.returncode
                stop_output = res_stop.stdout + "\n" + res_stop.stderr
            except subprocess.TimeoutExpired:
                stop_code = -1
                stop_output = "Command timed out after 60s."

            # Persist turn info
            sess_data["turns"].append({
                "iteration": it,
                "score": (aud_data.get("score") if isinstance(aud_data, dict) else 0),
                "defect_found": (rt_data.get("defect_found") if isinstance(rt_data, dict) else False),
                "violations": (aud_data.get("violations", []) if isinstance(aud_data, dict) else []),
                "cumulative_usd_spent": accumulator["total_usd"]
            })
            save_session(session_id, sess_data)

            # Per-iteration wall clock timeout check (max 180s)
            if time.time() - it_start_time > 180.0:
                click.secho("[STOP] Iteration timed out after 180s.", fg="yellow")
                accumulator["outcome"] = "TIMEOUT"
                break

    except BudgetCapExceeded as e:
        click.secho(f"[STOP] {e}", fg="yellow")
        accumulator["outcome"] = "BUDGET"

    # LOOP FINISH / REPORTING
    click.echo("\n=================================")
    click.secho(f"Loop completed: {accumulator['outcome']}", fg="cyan", bold=True)
    click.echo(f"Total Iterations: {accumulator['iterations']}")
    click.echo(f"Total Cost: ${accumulator['total_usd']:.5f} USD")

    click.echo("\n[Token & Cost Breakdown]")
    click.echo("  * By Model:")
    for m, info in accumulator["models"].items():
        role_label = "Implementer" if m == gen_model else "External"
        click.echo(f"    - Model {m} ({role_label}):")
        click.echo(f"      Input: {info['input']} tokens")
        click.echo(f"      Output: {info['output']} tokens")
        click.echo(f"      Cost: ${info['usd']:.5f} USD")

    click.echo("\n[Role Breakdown]")
    for role, info in accumulator["roles"].items():
        click.echo(f"  - {role}: In={info['input']} Out={info['output']} Cost=${info['usd']:.5f} USD")

    click.echo("\n[Iteration History]")
    for turn in sess_data.get("turns", []):
        click.echo(f"  - Iteration {turn['iteration']}: Score={turn.get('score')} Defect={turn.get('defect_found')} CumulativeCostSpent=${turn.get('cumulative_usd_spent', 0.0):.5f} USD")
    click.echo("=================================\n")

    # Copy back patched files to host repository on SUCCESS
    if accumulator["outcome"] == "SUCCESS":
        backup_dir = cwd / ".walkie" / "backup" / f"{session}_{int(time.time())}"
        backed_up = False
        for rel_f in patched_files_set:
            src = sandbox_path / rel_f
            dest = cwd / rel_f
            if dest.exists() and src.exists():
                try:
                    if dest.read_text(encoding="utf-8") != src.read_text(encoding="utf-8"):
                        backup_file = backup_dir / rel_f
                        backup_file.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(dest, backup_file)
                        backed_up = True
                except Exception as be:
                    click.secho(f"[ERROR] Failed to backup {rel_f}: {be}. Aborting copy-back for this file to prevent data loss.", fg="red")
                    continue
            if src.exists():
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dest)
        if backed_up:
            click.secho(f"[INFO] Existing host files were modified during loop. Backups saved under: {backup_dir.relative_to(cwd)}", fg="yellow")
        click.secho("[SUCCESS] Patched files successfully copied back to working directory.", fg="green")

    # Clean up worktree if detached
    if is_worktree and sandbox_path != cwd:
        click.echo("[CLEANUP] Removing worktree sandbox...")
        subprocess.run(["git", "worktree", "remove", "-f", str(sandbox_path)], capture_output=True)

    if json_output:
        click.echo(json.dumps(accumulator, indent=2))

    # If successful, output final status
    if accumulator["outcome"] == "SUCCESS":
        click.secho("SUCCESS: Stop oracle passed all validation checks!", fg="green")


if __name__ == '__main__':
    cli()

