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
import litellm

# Centralized Configuration & Logging Directory
try:
    CONFIG_DIR = Path.home() / '.walkie'
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR = CONFIG_DIR / 'logs'
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    test_file = LOG_DIR / ".write_test"
    test_file.write_text("ok", encoding="utf-8")
    test_file.unlink()
except Exception:
    CONFIG_DIR = Path(__file__).resolve().parent
    LOG_DIR = CONFIG_DIR / 'logs'
    LOG_DIR.mkdir(parents=True, exist_ok=True)

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
        "test_model": "openai/glm-4",
        "api_base": "https://zenmux.ai/api/v1"
    },
    "NVIDIA": {
        "env_var": "NVIDIA_API_KEY",
        "description": "NVIDIA API Key (NIM integration gateway)",
        "test_model": "z-ai/glm-5.2",
        "api_base": "https://integrate.api.nvidia.com/v1"
    },
    "GROQ": {
        "env_var": "GROQ_API_KEY",
        "description": "Groq API Key (fast Llama 3 / Mixtral)",
        "test_model": "groq/llama3-8b-8192",
    },
    "OPENROUTER": {
        "env_var": "OPENROUTER_API_KEY",
        "description": "OpenRouter API Key (access to various free and paid models. Note: tencent/hy3:free is deprecating on July 21st, 2026)",
        "test_model": "openrouter/auto",
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
        "test_model": "gpt-3.5-turbo",
    },
    "ANTHROPIC": {
        "env_var": "ANTHROPIC_API_KEY",
        "description": "Anthropic API Key",
        "test_model": "claude-3-haiku-20240307",
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
    pass

@cli.command()
def setup():
    """Interactive setup to configure API keys."""
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
        if cfg.get("url"):
            click.echo(f"Help URL: {cfg['url']}")

        if current_val:
            click.echo(f"Current key is set (starts with {current_val[:4]}...)")
            update = click.confirm("Do you want to update this key?", default=False)
            if not update:
                continue

        new_key = click.prompt(f"Enter {env_var}", default="", show_default=False, hide_input=True)
        new_key = new_key.strip()
        if new_key:
            pattern = cfg.get("pattern")
            if pattern and not re.match(pattern, new_key):
                click.secho(f"Warning: The entered key does not match the typical pattern for {provider}.", fg="yellow")
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
                api_base = info.get("api_base")
                api_key = new_key
                model = info["test_model"]

                kwargs = {
                    "model": model,
                    "messages": [{"role": "user", "content": "Hi"}],
                    "max_tokens": 5
                }
                if api_base:
                    kwargs["api_base"] = api_base
                    kwargs["api_key"] = api_key
                else:
                    kwargs["api_key"] = api_key

                litellm.completion(**kwargs)
                click.secho(f"Success! {provider} is working.", fg="green")
            except Exception as e:
                click.secho(f"Failed to verify {provider}: {str(e)}", fg="red")

    if os.name != 'nt' and env_path.exists():
        os.chmod(env_path, 0o600)
    click.secho("\nSetup complete!", fg="green")

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
        
        if file_ext == "py":
            for triple in ['"""', "'''"]:
                if code.startswith(triple, i):
                    idx = code.find(triple, i + 3)
                    if idx == -1:
                        result.append(code[i:])
                        i = n
                    else:
                        result.append(code[i:idx + 3])
                        i = idx + 3
                    break
            else:
                pass
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
            if info.get("api_base"):
                routed_model = "openai/" + model.split("/", 1)[1]
                api_base = info.get("api_base")
            else:
                routed_model = model
            
            if provider == "NVIDIA" and "deepseek" in routed_model.lower():
                api_key = os.getenv("NVIDIA_DEEPSEEK_API_KEY") or os.getenv(env_var)
            else:
                api_key = os.getenv(env_var)
            break

    return routed_model, api_base, api_key

def build_prompt(
    prompt: str,
    prompt_file: Optional[str],
    attach: List[str],
    strip_comments: bool,
    model: str
) -> Tuple[str, List[str]]:
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

    return full_prompt, images_list

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

    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S_%f")
    safe_model = re.sub(r'[^\w.\-]+', '-', model)[:80]

    log_data = {
        "timestamp": timestamp,
        "model": model,
        "routed_model": routed_model,
        "system_prompt": system,
        "user_prompt": full_prompt,
        "response": reply,
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
def ask(model, prompt, prompt_file, system, max_tokens, temperature, top_p, extra_body, attach, strip_comments, json_output, stream, no_log):
    """Ask a question to an LLM."""
    full_prompt, images_list = build_prompt(prompt, prompt_file, attach, strip_comments, model)
    routed_model, api_base, api_key = route_model(model)

    messages = []
    if system:
        messages.append({"role": "system", "content": system})

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

def call_llm(model: str, messages: List[dict], **opts) -> Tuple[str, dict]:
    """Single entry for litellm.completion. Returns (reply, usage_dict)."""
    routed, api_base, api_key = route_model(model)
    kwargs = {"model": routed, "messages": messages, "timeout": opts.get("timeout", 45)}
    if api_base: kwargs["api_base"] = api_base
    if api_key: kwargs["api_key"] = api_key
    for k in ("max_tokens", "temperature", "top_p", "stream", "extra_body"):
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
    pattern = r"(?:<|=|\s)*REPLACEMENT_START(?:>|=|\s)*\n?(.*?)\n?(?:<|=|\s)*REPLACEMENT_WITH(?:>|=|\s)*\n?(.*?)\n?(?:<|=|\s)*REPLACEMENT_END(?:>|=|\s)*"
    return re.findall(pattern, reply, re.DOTALL)

def _normalize_block(block: str) -> str:
    return "\n".join(line.strip().replace("\t", " ") for line in block.splitlines() if line.strip())

def apply_patches(content: str, patches: List[Tuple[str, str]], *, normalize: bool = True) -> Tuple[str, Optional[str]]:
    """Apply replacement patches to content with normalized indentation fallback matching."""
    working = content
    for orig, rep in patches:
        if orig in working:
            working = working.replace(orig, rep, 1)
            continue
        if normalize:
            orig_lines = [line.strip().replace("\t", " ") for line in orig.splitlines() if line.strip()]
            working_lines = working.splitlines()
            matched_start = -1
            
            for idx in range(len(working_lines) - len(orig_lines) + 1):
                window = [working_lines[idx+i].strip().replace("\t", " ") for i in range(len(orig_lines))]
                if window == orig_lines:
                    matched_start = idx
                    break
            
            if matched_start != -1:
                candidate_lines = working_lines[matched_start : matched_start + len(orig_lines)]
                candidate = "\n".join(candidate_lines)
                if candidate in working:
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
def consult(file, task, model, system, attach, dry_run, no_log, retries, line_range, verify_model, chain_model, keep_comments):
    """Automate surgical patching of files with a self-correcting model feedback harness."""
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

    base_user_prompt = f"Task: {task}\n\nTarget File: {s_file}\n"
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
            ], max_tokens=150)
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
        except Exception as e:
            click.secho(f"Error saving file {file}: {str(e)}", fg="red", err=True)
            sys.exit(1)
@cli.command()
@click.option('--output', '-o', default="llm_context.yaml", help="Path to write the generated project map.")
@click.option('--exclude', '-e', multiple=True, help="Glob patterns of files/directories to exclude.")
def map(output, exclude):
    """Generate a highly compressed, token-efficient YAML map of the codebase for LLMs."""
    import fnmatch
    from concurrent.futures import ThreadPoolExecutor, as_completed
    
    excludes = list(exclude) if exclude else [
        ".git", "__pycache__", "node_modules", "build", "dist", 
        ".walkie", "walkie_talkie.zip", "logs", "*.egg-info", "*.pyc"
    ]
    
    root_path = Path.cwd()
    project_map = {
        "project_name": root_path.name,
        "directory_structure": [],
        "python_modules": {},
        "config_files": {},
        "dependencies": [],
        "mermaid_dependencies": ""
    }
    
    files_to_parse = []
    config_files = []
    
    click.secho("Scanning workspace...", fg="yellow", err=True)
    
    for dirpath, dirnames, filenames in os.walk(root_path):
        # Filter directories in place
        dirnames[:] = [d for d in dirnames if not any(fnmatch.fnmatch(d, pat) for pat in excludes)]
        
        for filename in filenames:
            if any(fnmatch.fnmatch(filename, pat) for pat in excludes):
                continue
            
            filepath = Path(dirpath) / filename
            rel_filepath = filepath.relative_to(root_path)
            rel_str = str(rel_filepath).replace("\\", "/")
            
            project_map["directory_structure"].append(rel_str)
            
            if filename.endswith(".py"):
                files_to_parse.append((filepath, rel_str))
            elif filename in ("requirements.txt", "pyproject.toml"):
                config_files.append((filepath, filename))

    def parse_python_file(filepath, rel_str):
        try:
            if filepath.stat().st_size > 1_000_000:
                return rel_str, {"error": "File size exceeds 1MB limit"}, []
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                code = f.read()
            import ast as ast_lib
            tree = ast_lib.parse(code)
            module_info = {
                "classes": [],
                "functions": [],
                "imports": []
            }
            for node in ast_lib.walk(tree):
                if isinstance(node, ast_lib.ClassDef):
                    methods = [n.name for n in node.body if isinstance(n, ast_lib.FunctionDef)]
                    module_info["classes"].append({
                        "name": node.name,
                        "methods": methods
                    })
            for child in tree.body:
                if isinstance(child, ast_lib.FunctionDef):
                    module_info["functions"].append(child.name)
                elif isinstance(child, ast_lib.Import):
                    for name in child.names:
                        module_info["imports"].append(name.name)
                elif isinstance(child, ast_lib.ImportFrom):
                    if child.module:
                        module_info["imports"].append(child.module)
            return rel_str, {
                "classes": module_info["classes"],
                "functions": module_info["functions"]
            }, module_info["imports"]
        except Exception as e:
            return rel_str, {"error": f"Failed to parse AST: {str(e)}"}, []

    modules_list = [Path(fp).stem for fp, _ in files_to_parse]
    imports_map = {}
    
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {executor.submit(parse_python_file, fp, r_str): (fp, r_str) for fp, r_str in files_to_parse}
        for future in as_completed(futures):
            r_str, info, imports = future.result()
            project_map["python_modules"][r_str] = info
            stem = Path(futures[future][0]).stem
            imports_map[stem] = imports

    for filepath, filename in config_files:
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            project_map["config_files"][filename] = content.splitlines()[:15]
        except Exception:
            pass

    # Build Mermaid dependency flow
    mermaid_lines = ["graph TD"]
    has_edges = False
    for mod, imps in imports_map.items():
        for imp in imps:
            base_imp = imp.split('.')[0]
            if base_imp in modules_list and base_imp != mod:
                mermaid_lines.append(f"    {mod} --> {base_imp}")
                has_edges = True
                
    if has_edges:
        project_map["mermaid_dependencies"] = "\n".join(mermaid_lines)
    else:
        project_map["mermaid_dependencies"] = "graph TD\n    NoLocalDependencies"
        
    try:
        import yaml as yaml_lib
        with open(output, 'w', encoding='utf-8') as f:
            yaml_lib.dump(project_map, f, sort_keys=False)
        click.secho(f"Success! Codebase map saved to {output}", fg="green")
    except Exception as e:
        click.secho(f"Error saving project map: {str(e)}", fg="red", err=True)
        sys.exit(1)

if __name__ == '__main__':
    cli()
