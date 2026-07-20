"""
discovery.py — Smart model discovery, cross-provider grouping, and failover resolver.

Part of LLM Walkie-Talkie. Zero external dependencies (stdlib urllib.request only).
"""
import json
import os
import re
import time
import urllib.request
import urllib.error
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import contextlib

# ── Constants ──────────────────────────────────────────────────────────────────

CONFIG_DIR = Path(os.environ.get("WALKIE_CONFIG_DIR", Path.home() / ".walkie"))
REGISTRY_PATH = CONFIG_DIR / "model_registry.json"
REGISTRY_TTL = int(os.environ.get("WALKIE_REGISTRY_TTL", 86400))  # 24h default

# Fixed provider preference when no EWMA data exists yet
_env_priority = os.environ.get("LWT_PROVIDER_ORDER")
if _env_priority:
    PROVIDER_PRIORITY = [p.strip().upper() for p in _env_priority.split(",") if p.strip()]
else:
    PROVIDER_PRIORITY = ["NVIDIA", "ZENMUX", "OPENROUTER", "GROQ", "GEMINI", "OPENAI", "ANTHROPIC"]

# Min samples before switching from priority order to EWMA-based election
MIN_EWMA_SAMPLES = 5

# Known organisation-prefix normalizations across providers
ORG_ALIASES: Dict[str, str] = {
    "deepseek-ai": "deepseek",
    "meta-llama": "meta",
    "mistralai": "mistral",
    "tiiuae": "falcon",
    "01-ai": "yi",
    "cohere-for-ai": "cohere",
    "huggingfaceh4": "hf",
}

# Suffixes to strip when building canonical names
SUFFIX_STRIP = [":free", ":nitro", ":extended", ":beta", ":preview",
                "-instruct", "-chat", "-hf"]

# Tags heuristic: if any keyword appears in model id or description → assign tag
TAG_KEYWORDS: Dict[str, List[str]] = {
    "coding":    ["code", "coder", "coding", "dev", "program", "deepseek", "glm", "qwen", "starcoder"],
    "reasoning": ["reason", "think", "r1", "r2", "o1", "o3", "reflect", "cogito"],
    "math":      ["math", "mathstral", "numina"],
    "vision":    ["vision", "vl", "visual", "llava", "pixtral"],
    "fast":      ["flash", "turbo", "haiku", "mini", "small", "8b", "7b"],
}

# ── Key masking ────────────────────────────────────────────────────────────────

_KEY_PATTERN = re.compile(
    r'(nvapi-|sk-or-|sk-ant-|AIzaSy|gsk_|sk-ai-v1-)[a-zA-Z0-9_\-]{6,}'
)

def mask_keys(text: str) -> str:
    """Scrub API key prefixes from any string before logging."""
    return _KEY_PATTERN.sub(lambda m: m.group(1) + "***MASKED***", text)


# ── Canonical name normalization ───────────────────────────────────────────────

def normalize_model_name(model_id: str) -> str:
    """
    Convert any provider-specific model id to a canonical short name.

    Examples:
      openrouter/deepseek/deepseek-r1:free → deepseek-r1
      nvidia/deepseek-ai/deepseek-r1       → deepseek-r1
      nvidia/z-ai/glm-5.2                  → glm-5.2
      groq/llama3-8b-8192                  → llama3-8b-8192
    """
    raw = model_id.lower().strip()

    # Remove leading provider gateway prefix (openrouter/, zenmux/, nvidia/ at pos 0)
    known_gateways = {"openrouter", "nvidia", "zenmux", "groq", "gemini", "anthropic",
                      "openai", "mistral", "cohere", "together", "hf"}
    parts = raw.split("/")
    if len(parts) >= 2 and parts[0] in known_gateways:
        parts = parts[1:]

    if len(parts) >= 2:
        org, name = parts[-2], parts[-1]
    elif len(parts) == 1:
        org, name = "", parts[0]
    else:
        return raw

    # Apply alias map
    org = ORG_ALIASES.get(org, org)

    # Strip known suffixes from name
    for suf in SUFFIX_STRIP:
        if name.endswith(suf):
            name = name[: -len(suf)]

    # If name starts with org-, strip it (deepseek-r1 stays, not deepseek-deepseek-r1)
    canonical = name
    if org and canonical.startswith(org + "-"):
        canonical = canonical[len(org) + 1:]

    return canonical.strip("-").strip()


# ── Model tagging ──────────────────────────────────────────────────────────────

def classify_model(model_id: str, description: str = "") -> List[str]:
    """Heuristic tagger: return list of relevant tags for a model."""
    haystack = (model_id + " " + description).lower()
    return [tag for tag, keywords in TAG_KEYWORDS.items()
            if any(kw in haystack for kw in keywords)]


# ── Capability tier classification ─────────────────────────────────────────────

# Tier ordering: higher numeric score = more capable
TIER_SCORES = {"flagship": 5, "advanced": 4, "mid": 3, "small": 2, "nano": 1}

# Keywords that indicate capability tier (checked against lowercase model_id)
_TIER_KEYWORDS = {
    "flagship": ["ultra", "flagship", "opus", "pro", "max"],
    "advanced": ["super", "advanced", "large", "plus", "sonnet"],
    "small":    ["mini", "small", "lite", "haiku", "flash"],
    "nano":     ["nano", "tiny", "micro"],
}


def classify_capability_tier(model_id: str, context_length: int = 0) -> Tuple[str, Optional[int]]:
    """
    Classify a model's capability tier and extract parameter count.

    Returns (tier, param_count_billions).
    Tiers: 'flagship' > 'advanced' > 'mid' > 'small' > 'nano'

    Resolution priority:
      1. Explicit tier keywords in model name (e.g. 'ultra' → flagship)
      2. Parameter count suffix (e.g. '550b' → flagship if ≥200B)
      3. Version number heuristic (higher version = more advanced)
      4. Default: 'mid'
    """
    name = model_id.lower()

    # Extract parameter count (e.g. '550b', '120b', '30b', '8b')
    param_match = re.search(r'(\d+)b(?:-|$|[^a-z])', name)
    param_b = int(param_match.group(1)) if param_match else None

    # 1. Check explicit tier keywords
    for tier, keywords in _TIER_KEYWORDS.items():
        if any(kw in name for kw in keywords):
            return tier, param_b

    # 2. Infer from parameter count
    if param_b is not None:
        if param_b >= 200:
            return "flagship", param_b
        elif param_b >= 50:
            return "advanced", param_b
        elif param_b >= 20:
            return "mid", param_b
        elif param_b >= 5:
            return "small", param_b
        else:
            return "nano", param_b

    # 3. Default
    return "mid", param_b


def extract_model_family(model_id: str) -> str:
    """
    Extract the model family name from a model_id for fuzzy matching.

    Examples:
      nvidia/z-ai/glm-5.2          → glm
      zenmux/x-ai/grok-4.5-free    → grok
      nvidia/nvidia/nemotron-3-ultra-550b-a55b → nemotron
      nvidia/deepseek-ai/deepseek-v4-pro       → deepseek
      openrouter/qwen/qwen3-coder:free         → qwen
    """
    canonical = normalize_model_name(model_id)
    # Match the core family name (first alphabetic segment of ≥2 chars)
    family_match = re.match(r'^([a-z]{2,})', canonical)
    if family_match:
        return family_match.group(1)

    # Fallback: if canonical is too short (e.g. 'v4-pro' from deepseek),
    # extract org from the raw model_id path segments
    raw = model_id.lower().strip()
    parts = raw.split("/")
    # Skip gateway prefix
    known_gateways = {"openrouter", "nvidia", "zenmux", "groq", "gemini",
                      "anthropic", "openai", "mistral", "cohere", "together", "hf"}
    if len(parts) >= 2 and parts[0] in known_gateways:
        parts = parts[1:]
    if len(parts) >= 2:
        org = parts[-2]
        # Apply alias map
        org = ORG_ALIASES.get(org, org)
        org_family = re.match(r'^([a-z]{2,})', org)
        if org_family:
            return org_family.group(1)

    return canonical


def extract_version_score(model_id: str) -> float:
    """
    Extract a numeric version score from a model_id for comparison.
    Higher score = more advanced version.

    Version numbers are treated as decimal: 4.5 = 4.5, 4.20 = 4.2.
    This matches xAI/GLM naming where grok-4.5 > grok-4.20 (4.5 > 4.2).

    Examples:
      grok-4.5  → 4.5
      grok-4.20 → 4.2
      glm-5.2   → 5.2
      deepseek-v4-pro → 4.0
    """
    name = normalize_model_name(model_id).lower()
    # Look for version patterns: X.Y, vX, or standalone numbers
    ver_match = re.search(r'(?:^|[.-])v?(\d+)\.(\d+)', name)
    if ver_match:
        major = int(ver_match.group(1))
        minor = int(ver_match.group(2))
        # Treat as decimal: "4.5" → 4.5, "4.20" → 4.2, "5.2" → 5.2
        return float(f"{major}.{minor}")
    ver_match = re.search(r'(?:^|[.-])v?(\d+)', name)
    if ver_match:
        return float(ver_match.group(1))
    return 0.0


# ── Registry I/O ──────────────────────────────────────────────────────────────

def load_registry() -> Dict[str, Any]:
    """Load model registry from disk. Returns empty structure if missing/corrupt."""
    try:
        if REGISTRY_PATH.exists():
            data = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
            return data
    except Exception:
        pass
    return {
        "updated_at": None,
        "scan_ttl_seconds": REGISTRY_TTL,
        "provider_priority": PROVIDER_PRIORITY,
        "logical_models": {},
    }


def save_registry(data: Dict[str, Any]) -> None:
    """Atomically write registry to disk."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    tmp = REGISTRY_PATH.with_suffix(".tmp")
    try:
        tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
        os.replace(tmp, REGISTRY_PATH)
    except Exception as e:
        try:
            tmp.unlink(missing_ok=True)
        except Exception:
            pass
        raise RuntimeError(f"Failed to save registry: {e}") from None


def registry_is_fresh(data: Dict[str, Any]) -> bool:
    """Return True if the registry was updated within the TTL window."""
    updated_at = data.get("updated_at")
    if not updated_at:
        return False
    try:
        age = time.time() - time.mktime(time.strptime(updated_at, "%Y-%m-%dT%H:%M:%S"))
        ttl = data.get("scan_ttl_seconds", REGISTRY_TTL)
        return age < ttl
    except Exception:
        return False


# ── Provider fetchers ──────────────────────────────────────────────────────────

def _http_get(url: str, headers: Optional[Dict[str, str]] = None,
              timeout: int = 15) -> Optional[Dict]:
    """Simple JSON GET via stdlib urllib."""
    req = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None


def fetch_openrouter_models() -> List[Dict[str, Any]]:
    """
    Fetch free models from OpenRouter's public catalog.
    Filters where pricing.prompt == "0" AND pricing.completion == "0"
    OR model id ends with :free.
    """
    api_key = os.environ.get("OPENROUTER_API_KEY")
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    data = _http_get("https://openrouter.ai/api/v1/models", headers=headers)
    if not data:
        return []

    results = []
    for m in data.get("data", []):
        pricing = m.get("pricing", {})
        is_free = (
            (str(pricing.get("prompt", "1")) == "0"
             and str(pricing.get("completion", "1")) == "0")
            or str(m.get("id", "")).endswith(":free")
        )
        if not is_free:
            continue
        results.append({
            "provider": "OPENROUTER",
            "env_var": "OPENROUTER_API_KEY",
            "model_id": f"openrouter/{m['id']}",
            "api_base": "https://openrouter.ai/api/v1",
            "context_length": m.get("context_length", 0),
            "is_free": True,
            "description": m.get("description", ""),
            "name": m.get("name", m["id"]),
        })
    return results


def fetch_nvidia_models() -> List[Dict[str, Any]]:
    """
    Fetch models available on NVIDIA NIM (requires NVIDIA_API_KEY).
    Returns empty list if key not configured.
    """
    api_key = os.environ.get("NVIDIA_API_KEY")
    if not api_key:
        return []
    headers = {"Authorization": f"Bearer {api_key}"}
    data = _http_get("https://integrate.api.nvidia.com/v1/models", headers=headers)
    if not data:
        return []

    results = []
    for m in data.get("data", []):
        mid = m.get("id", "")
        results.append({
            "provider": "NVIDIA",
            "env_var": "NVIDIA_API_KEY",
            "model_id": f"nvidia/{mid}",
            "api_base": "https://integrate.api.nvidia.com/v1",
            "context_length": 0,  # NIM doesn't expose this in list endpoint
            "is_free": True,      # All NIM API key tier models use free quota
            "description": "",
            "name": mid,
        })
    return results


# ── Grouping and election ──────────────────────────────────────────────────────

def group_by_logical_model(
    all_routes: List[Dict[str, Any]],
    existing_registry: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Group provider-specific routes by canonical model name.
    Preserves existing EWMA metrics from previous registry entries.
    """
    existing_models = (existing_registry or {}).get("logical_models", {})
    grouped: Dict[str, Any] = {}

    for route in all_routes:
        canonical = normalize_model_name(route["model_id"])
        if not canonical:
            continue

        if canonical not in grouped:
            # Seed from existing registry to preserve metrics
            existing = existing_models.get(canonical, {})
            grouped[canonical] = {
                "display_name": route.get("name", canonical),
                "tags": classify_model(route["model_id"], route.get("description", "")),
                "first_seen": existing.get("first_seen", _now()),
                "last_seen": _now(),
                "routes": [],
            }
        else:
            grouped[canonical]["last_seen"] = _now()
            # Merge tags
            new_tags = classify_model(route["model_id"], route.get("description", ""))
            grouped[canonical]["tags"] = list(
                set(grouped[canonical]["tags"]) | set(new_tags)
            )

        # Find existing route entry to preserve metrics
        existing_route = next(
            (r for r in existing_models.get(canonical, {}).get("routes", [])
             if r["model_id"] == route["model_id"]),
            {}
        )

        grouped[canonical]["routes"].append({
            "provider": route["provider"],
            "env_var": route["env_var"],
            "model_id": route["model_id"],
            "api_base": route.get("api_base"),
            "context_length": route.get("context_length", 0),
            "is_free": route.get("is_free", True),
            # Preserve existing metrics
            "latency_ms_ewma": existing_route.get("latency_ms_ewma"),
            "success_rate": existing_route.get("success_rate"),
            "sample_count": existing_route.get("sample_count", 0),
            "last_status": existing_route.get("last_status"),
            "last_checked": existing_route.get("last_checked"),
        })

    return grouped


def elect_primary_idx(routes: List[Dict[str, Any]],
                      priority: List[str]) -> int:
    """
    Return index of the best route in the list.
    Uses provider_priority order until a route has MIN_EWMA_SAMPLES,
    then switches to EWMA latency + success_rate scoring.
    """
    # Check if any route has enough samples for EWMA
    has_data = any(
        (r.get("sample_count") or 0) >= MIN_EWMA_SAMPLES for r in routes
    )

    if has_data:
        # Score: lower latency + higher success_rate wins
        def score(r):
            lat = r.get("latency_ms_ewma") or 9999
            sr = r.get("success_rate") or 0.0
            return lat / max(sr, 0.01)
        return min(range(len(routes)), key=lambda i: score(routes[i]))
    else:
        # Use fixed provider priority order
        def priority_key(r):
            p = r.get("provider", "")
            return priority.index(p) if p in priority else len(priority)
        return min(range(len(routes)), key=lambda i: priority_key(routes[i]))


# ── Resolver ───────────────────────────────────────────────────────────────────

def resolve_with_fallback(
    model: str,
    registry: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """
    Resolve a model string to an ordered list of route dicts.

    Resolution order:
    1. Exact model_id match across all routes
    2. Canonical name lookup in logical_models
    3. Return empty list (caller falls back to direct route_model())

    Each returned dict has: provider, env_var, model_id, api_base,
    context_length, latency_ms_ewma, success_rate.
    """
    if registry is None:
        registry = load_registry()

    logical = registry.get("logical_models", {})
    priority = registry.get("provider_priority", PROVIDER_PRIORITY)

    # 1. Exact model_id match
    for canonical, entry in logical.items():
        for route in entry.get("routes", []):
            if route["model_id"] == model or route["model_id"] == f"openrouter/{model}":
                # Found exact match — return full ordered chain
                all_routes = entry["routes"]
                pri_idx = elect_primary_idx(all_routes, priority)
                ordered = [all_routes[pri_idx]] + [
                    r for i, r in enumerate(all_routes) if i != pri_idx
                ]
                return _filter_with_keys(ordered)

    # 2. Canonical name lookup
    canonical = normalize_model_name(model)
    if canonical in logical:
        all_routes = logical[canonical]["routes"]
        pri_idx = elect_primary_idx(all_routes, priority)
        ordered = [all_routes[pri_idx]] + [
            r for i, r in enumerate(all_routes) if i != pri_idx
        ]
        return _filter_with_keys(ordered)

    # 3. Not found — empty (caller uses direct route_model())
    return []


def _filter_with_keys(routes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Return only routes for which the required env var is set."""
    return [r for r in routes if os.environ.get(r.get("env_var", ""))]


# ── Metrics update ────────────────────────────────────────────────────────────

def update_route_metrics(
    registry: Dict[str, Any],
    model_id: str,
    success: bool,
    latency_ms: Optional[float] = None,
) -> None:
    """
    Update EWMA latency and success_rate for a specific route in-place.
    Caller is responsible for saving registry afterward.
    """
    alpha = 0.2  # EWMA smoothing factor
    for entry in registry.get("logical_models", {}).values():
        for route in entry.get("routes", []):
            if route["model_id"] == model_id:
                n = route.get("sample_count", 0) + 1
                route["sample_count"] = n
                route["last_status"] = "ok" if success else "fail"
                route["last_checked"] = _now()

                # Update success_rate (simple rolling)
                old_sr = route.get("success_rate") or 0.0
                route["success_rate"] = old_sr + alpha * ((1.0 if success else 0.0) - old_sr)

                # Update EWMA latency only on success
                if success and latency_ms is not None:
                    old_lat = route.get("latency_ms_ewma")
                    if old_lat is None:
                        route["latency_ms_ewma"] = latency_ms
                    else:
                        route["latency_ms_ewma"] = old_lat + alpha * (latency_ms - old_lat)
                return


# ── Discovery scan ─────────────────────────────────────────────────────────────

def run_discovery(force: bool = False) -> Tuple[Dict[str, Any], Dict[str, List[str]]]:
    """
    Fetch models from all available providers, group, and update registry.
    Returns (updated_registry, diff_report).
    diff_report = {"added": [...], "removed": [...]}
    """
    registry = load_registry()

    if not force and registry_is_fresh(registry):
        return registry, {"added": [], "removed": []}

    all_routes = fetch_openrouter_models() + fetch_nvidia_models()

    old_canonical = set(registry.get("logical_models", {}).keys())
    new_grouped = group_by_logical_model(all_routes, registry)
    new_canonical = set(new_grouped.keys())

    diff = {
        "added": sorted(new_canonical - old_canonical),
        "removed": sorted(old_canonical - new_canonical),
    }

    registry["logical_models"] = new_grouped
    registry["updated_at"] = _now()
    registry["provider_priority"] = PROVIDER_PRIORITY

    save_registry(registry)
    return registry, diff


# ── Health sweep ───────────────────────────────────────────────────────────────

def sweep_configured_providers(probe_fn) -> List[Dict[str, Any]]:
    """
    Probe each configured provider's test model.
    probe_fn(model_id, api_base, api_key) → (ok: bool, latency_ms: float, error: str)
    Returns list of status dicts.
    """
    # Import PROVIDERS lazily to avoid circular import
    import importlib
    walkie = importlib.import_module("walkie")
    providers = walkie.PROVIDERS

    results = []
    for name, info in providers.items():
        env_val = os.environ.get(info["env_var"])
        if not env_val:
            results.append({
                "provider": name,
                "has_key": False,
                "status": "no_key",
                "model": info["test_model"],
                "latency_ms": None,
                "error": None,
            })
            continue

        ok, latency_ms, error = probe_fn(
            info["test_model"],
            info.get("api_base"),
            env_val,
        )
        results.append({
            "provider": name,
            "has_key": True,
            "status": "ok" if ok else "dead",
            "model": info["test_model"],
            "latency_ms": latency_ms,
            "error": mask_keys(str(error)) if error else None,
        })
    return results


# ── Helpers ────────────────────────────────────────────────────────────────────

def _now() -> str:
    import datetime
    return datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


def rank_free_models(
    registry: Dict[str, Any],
    use_case: str = "coding",
    configured_only: bool = False,
) -> List[Tuple[str, Dict[str, Any]]]:
    """
    Return (canonical_name, entry) pairs sorted by relevance.
    Priority: use_case tag match > context_length > provider priority.
    """
    priority = registry.get("provider_priority", PROVIDER_PRIORITY)
    results = []

    for canonical, entry in registry.get("logical_models", {}).items():
        routes = entry.get("routes", [])
        if configured_only:
            routes = _filter_with_keys(routes)
        if not routes:
            continue

        has_tag = use_case in entry.get("tags", [])
        max_ctx = max((r.get("context_length") or 0) for r in routes)
        best_prio = min(
            (priority.index(r["provider"]) if r["provider"] in priority else len(priority))
            for r in routes
        )
        results.append((canonical, entry, has_tag, max_ctx, best_prio))

    results.sort(key=lambda x: (not x[2], -x[3], x[4]))
    return [(r[0], r[1]) for r in results]


# ── Verified Models Manifest ──────────────────────────────────────────────────

VERIFIED_PATH = CONFIG_DIR / "verified_models.json"


@contextlib.contextmanager
def verified_manifest_lock():
    """Atomic folder-creation lock to prevent concurrent writes to the manifest."""
    lock_dir = CONFIG_DIR / "verified_models.lock"
    acquired = False
    # Retries for up to 3 seconds
    for _ in range(30):
        try:
            lock_dir.mkdir(exist_ok=False)
            acquired = True
            break
        except FileExistsError:
            time.sleep(0.1)
    try:
        yield acquired
    finally:
        if acquired:
            try:
                lock_dir.rmdir()
            except Exception:
                pass


def load_verified_manifest() -> Dict[str, Any]:
    """Load the verified models manifest from disk."""
    try:
        if VERIFIED_PATH.exists():
            return json.loads(VERIFIED_PATH.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {"last_updated": None, "verified_models": []}


def save_verified_manifest(data: Dict[str, Any]) -> None:
    """Atomically write the verified models manifest."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    data["last_updated"] = _now()
    tmp = VERIFIED_PATH.with_suffix(".tmp")
    try:
        tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
        os.replace(tmp, VERIFIED_PATH)
    except Exception:
        try:
            tmp.unlink(missing_ok=True)
        except Exception:
            pass


def update_verified_entry(model_id: str, success: bool) -> None:
    """
    Update or create a verified_models.json entry after an API call.
    Only records successful connections (sets last_verified_ok timestamp).
    """
    if not success:
        return

    with verified_manifest_lock():
        manifest = load_verified_manifest()
        models = manifest.get("verified_models", [])

    # Find existing entry
    existing = None
    for entry in models:
        if entry.get("model_id") == model_id:
            existing = entry
            break

    registry = load_registry()
    # Find the route info from model registry
    tags = []
    ctx_len = 0
    provider = ""
    for _canonical, lm_entry in registry.get("logical_models", {}).items():
        for route in lm_entry.get("routes", []):
            if route["model_id"] == model_id:
                tags = lm_entry.get("tags", [])
                ctx_len = route.get("context_length", 0)
                provider = route.get("provider", "")
                break
        if provider:
            break

    # If not found in registry, infer from model_id
    if not provider:
        parts = model_id.split("/")
        if len(parts) >= 2:
            provider = parts[0].upper()
        tags = classify_model(model_id)

    family = extract_model_family(model_id)
    tier, param_b = classify_capability_tier(model_id, ctx_len)
    # Infer variant from canonical name
    canonical = normalize_model_name(model_id)
    variant = canonical.replace(family, "").strip("-").strip() or canonical

    now = _now()

    if existing:
        existing["last_verified_ok"] = now
        existing["total_successful_calls"] = existing.get("total_successful_calls", 0) + 1
        existing["capability_tier"] = tier
        existing["param_count_b"] = param_b
        if ctx_len:
            existing["context_length"] = ctx_len
        if tags:
            existing["tags"] = tags
    else:
        models.append({
            "family": family,
            "variant": variant,
            "model_id": model_id,
            "provider": provider,
            "capability_tier": tier,
            "param_count_b": param_b,
            "context_length": ctx_len,
            "last_verified_ok": now,
            "total_successful_calls": 1,
            "tags": tags,
        })

    manifest["verified_models"] = models
    save_verified_manifest(manifest)


def resolve_fuzzy_model(user_name: str) -> Optional[str]:
    """
    Resolve a fuzzy/informal user model name to the best verified model_id.

    Resolution algorithm:
      1. Normalize user input to lowercase
      2. Search verified_models.json for entries where 'family' matches
      3. If multiple matches: rank by capability_tier > param_count > version > recency
      4. If no verified matches: fall back to model_registry.json
      5. Return the best model_id string, or None if no match

    Examples:
      "GLM"       → nvidia/z-ai/glm-5.2
      "Grok"      → zenmux/x-ai/grok-4.5-free (flagship > mid-tier)
      "Nemotron"  → nvidia/nvidia/nemotron-3-ultra-550b-a55b (550B > 30B)
    """
    query = user_name.lower().strip()
    if not query:
        return None

    # ── Phase 1: Search verified manifest ──
    manifest = load_verified_manifest()
    candidates = []
    for entry in manifest.get("verified_models", []):
        family = entry.get("family", "")
        model_id = entry.get("model_id", "")
        canonical = normalize_model_name(model_id).lower()

        # Match: family equals query, or query is a substring of canonical/model_id
        if family == query or query in canonical or query in model_id.lower():
            candidates.append(entry)

    if candidates:
        # Rank: tier score (desc) → param_count (desc) → version (desc) → recency (desc)
        def rank_key(e):
            tier_score = TIER_SCORES.get(e.get("capability_tier", "mid"), 3)
            param = e.get("param_count_b") or 0
            version = extract_version_score(e.get("model_id", ""))
            recency = e.get("last_verified_ok", "")
            return (-tier_score, -param, -version, recency)  # Sort ascending → best first

        candidates.sort(key=rank_key)
        return candidates[0]["model_id"]

    # ── Phase 2: Fall back to model registry ──
    registry = load_registry()
    reg_candidates = []
    for canonical, entry in registry.get("logical_models", {}).items():
        if query in canonical.lower() or query in entry.get("display_name", "").lower():
            routes = entry.get("routes", [])
            # Only consider routes with configured API keys
            valid_routes = _filter_with_keys(routes)
            if not valid_routes:
                valid_routes = routes  # Fall back to all routes if none have keys
            if valid_routes:
                tier, param_b = classify_capability_tier(valid_routes[0]["model_id"])
                reg_candidates.append({
                    "model_id": valid_routes[0]["model_id"],
                    "tier": tier,
                    "param_b": param_b or 0,
                    "version": extract_version_score(valid_routes[0]["model_id"]),
                })

    if reg_candidates:
        def reg_rank(e):
            return (-TIER_SCORES.get(e["tier"], 3), -e["param_b"], -e["version"])
        reg_candidates.sort(key=reg_rank)
        return reg_candidates[0]["model_id"]

    return None


def suggest_vendor_diverse_models(
    count: int = 3,
    use_case: str = "coding",
) -> List[Dict[str, str]]:
    """
    Suggest a vendor-diverse set of models for llm-loop's 3-vendor requirement.
    Returns list of dicts with 'model_id', 'provider', 'role' keys.
    """
    manifest = load_verified_manifest()
    models = manifest.get("verified_models", [])

    # Filter to models that were recently verified OK
    alive = [m for m in models if m.get("last_verified_ok")]

    # Group by provider
    by_provider: Dict[str, List[Dict]] = {}
    for m in alive:
        p = m.get("provider", "UNKNOWN")
        by_provider.setdefault(p, []).append(m)

    # Pick the best model from each provider (by tier, then recency)
    best_per_provider = []
    for provider, provider_models in by_provider.items():
        provider_models.sort(
            key=lambda e: (
                -TIER_SCORES.get(e.get("capability_tier", "mid"), 3),
                -(e.get("param_count_b") or 0),
            )
        )
        best_per_provider.append({
            "model_id": provider_models[0]["model_id"],
            "provider": provider,
            "tier": provider_models[0].get("capability_tier", "mid"),
        })

    # Sort providers by tier of their best model
    best_per_provider.sort(key=lambda e: -TIER_SCORES.get(e["tier"], 3))

    # Assign roles: gen (best), audit (second best), redteam (third)
    roles = ["gen-model", "audit-model", "redteam-model"]
    result = []
    for i, entry in enumerate(best_per_provider[:count]):
        result.append({
            "model_id": entry["model_id"],
            "provider": entry["provider"],
            "role": roles[i] if i < len(roles) else f"extra-{i}",
        })

    return result

