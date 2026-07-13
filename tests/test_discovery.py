"""
tests/test_discovery.py — Unit tests for discovery.py
Uses only stdlib; no external services called.
"""
import json
import os
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

# Ensure the project root is on the path
sys.path.insert(0, str(Path(__file__).parent.parent))

import discovery as disc


# ── Fixtures ───────────────────────────────────────────────────────────────────

def _make_route(provider, model_id, ctx=32000, latency=None, success=None, samples=0):
    return {
        "provider": provider,
        "env_var": f"{provider}_API_KEY",
        "model_id": model_id,
        "api_base": f"https://api.{provider.lower()}.com/v1",
        "context_length": ctx,
        "is_free": True,
        "latency_ms_ewma": latency,
        "success_rate": success,
        "sample_count": samples,
        "last_status": None,
        "last_checked": None,
    }


# ── test_normalize_model_name ──────────────────────────────────────────────────

def test_normalize_basic():
    assert disc.normalize_model_name("openrouter/deepseek/deepseek-r1:free") == "r1"

def test_normalize_nvidia_prefix():
    assert disc.normalize_model_name("nvidia/z-ai/glm-5.2") == "glm-5.2"

def test_normalize_alias():
    # deepseek-ai → deepseek alias; name deepseek-r1 → r1
    assert disc.normalize_model_name("nvidia/deepseek-ai/deepseek-r1") == "r1"

def test_normalize_meta_llama_alias():
    result = disc.normalize_model_name("openrouter/meta-llama/llama-3-70b-instruct")
    assert "llama-3-70b" in result

def test_normalize_no_provider():
    assert disc.normalize_model_name("glm-5.2") == "glm-5.2"

def test_normalize_suffix_strip():
    # :free suffix stripped
    result = disc.normalize_model_name("openrouter/google/gemma-3-27b:free")
    assert ":free" not in result
    assert "gemma" in result


# ── test_classify_model ────────────────────────────────────────────────────────

def test_classify_coding_tags():
    tags = disc.classify_model("openrouter/deepseek/deepseek-coder:free")
    assert "coding" in tags

def test_classify_reasoning_tags():
    tags = disc.classify_model("nvidia/deepseek-ai/deepseek-r1")
    assert "reasoning" in tags or "coding" in tags

def test_classify_fast_tags():
    tags = disc.classify_model("openrouter/google/gemma-2-7b:free")
    assert "fast" in tags


# ── test_group_by_logical_model ───────────────────────────────────────────────

def test_group_deduplicates_across_providers():
    routes = [
        {**_make_route("NVIDIA", "nvidia/deepseek-ai/deepseek-r1", ctx=128000),
         "description": "", "name": "DeepSeek R1"},
        {**_make_route("OPENROUTER", "openrouter/deepseek/deepseek-r1:free", ctx=128000),
         "description": "", "name": "DeepSeek R1 (free)"},
    ]
    grouped = disc.group_by_logical_model(routes)
    # Both should collapse to the same canonical
    assert len(grouped) == 1
    canonical = list(grouped.keys())[0]
    assert len(grouped[canonical]["routes"]) == 2


def test_group_preserves_existing_metrics():
    old_registry = {
        "logical_models": {
            "glm-5.2": {
                "display_name": "GLM 5.2",
                "tags": ["coding"],
                "first_seen": "2026-01-01",
                "last_seen": "2026-07-01",
                "routes": [
                    {**_make_route("NVIDIA", "nvidia/z-ai/glm-5.2"),
                     "latency_ms_ewma": 850.0, "success_rate": 0.95, "sample_count": 10}
                ]
            }
        }
    }
    new_routes = [
        {**_make_route("NVIDIA", "nvidia/z-ai/glm-5.2"), "description": "", "name": "GLM 5.2"},
    ]
    grouped = disc.group_by_logical_model(new_routes, old_registry)
    assert "glm-5.2" in grouped
    route = grouped["glm-5.2"]["routes"][0]
    assert route["latency_ms_ewma"] == 850.0
    assert route["success_rate"] == 0.95


# ── test_elect_primary_idx ────────────────────────────────────────────────────

def test_elect_primary_uses_priority_when_no_data():
    priority = ["NVIDIA", "OPENROUTER"]
    routes = [
        _make_route("OPENROUTER", "openrouter/deepseek/deepseek-r1:free"),
        _make_route("NVIDIA", "nvidia/deepseek-ai/deepseek-r1"),
    ]
    idx = disc.elect_primary_idx(routes, priority)
    assert routes[idx]["provider"] == "NVIDIA"


def test_elect_primary_uses_ewma_when_enough_samples():
    priority = ["NVIDIA", "OPENROUTER"]
    routes = [
        _make_route("NVIDIA", "nvidia/deepseek-ai/deepseek-r1",
                    latency=2000, success=0.9, samples=10),
        _make_route("OPENROUTER", "openrouter/deepseek/deepseek-r1:free",
                    latency=500, success=0.95, samples=10),
    ]
    idx = disc.elect_primary_idx(routes, priority)
    # OpenRouter is faster and more reliable — should win by EWMA
    assert routes[idx]["provider"] == "OPENROUTER"


# ── test_resolve_with_fallback ────────────────────────────────────────────────

def test_resolve_canonical_name(monkeypatch):
    registry = {
        "provider_priority": ["NVIDIA", "OPENROUTER"],
        "logical_models": {
            "glm-5.2": {
                "routes": [
                    _make_route("NVIDIA", "nvidia/z-ai/glm-5.2"),
                    _make_route("OPENROUTER", "openrouter/z-ai/glm-5.2:free"),
                ]
            }
        }
    }
    # Both keys configured
    monkeypatch.setenv("NVIDIA_API_KEY", "nvapi-test")
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")

    routes = disc.resolve_with_fallback("glm-5.2", registry)
    assert len(routes) == 2
    # NVIDIA should be primary (first in priority)
    assert routes[0]["provider"] == "NVIDIA"


def test_resolve_filters_missing_keys(monkeypatch):
    registry = {
        "provider_priority": ["NVIDIA", "OPENROUTER"],
        "logical_models": {
            "glm-5.2": {
                "routes": [
                    _make_route("NVIDIA", "nvidia/z-ai/glm-5.2"),
                    _make_route("OPENROUTER", "openrouter/z-ai/glm-5.2:free"),
                ]
            }
        }
    }
    # Only NVIDIA key set
    monkeypatch.setenv("NVIDIA_API_KEY", "nvapi-test")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

    routes = disc.resolve_with_fallback("glm-5.2", registry)
    assert len(routes) == 1
    assert routes[0]["provider"] == "NVIDIA"


def test_resolve_unknown_model_returns_empty(monkeypatch):
    registry = {"provider_priority": [], "logical_models": {}}
    routes = disc.resolve_with_fallback("nonexistent-model-xyz", registry)
    assert routes == []


# ── test_diff_registry ────────────────────────────────────────────────────────

def test_diff_registry_detects_new_model():
    old = {"logical_models": {"deepseek-r1": {"routes": []}}}
    new_routes = [
        {**_make_route("OPENROUTER", "openrouter/qwen/qwen3-coder:free"),
         "description": "", "name": "Qwen3 Coder"},
        {**_make_route("OPENROUTER", "openrouter/deepseek/deepseek-r1:free"),
         "description": "", "name": "DeepSeek R1"},
    ]
    new_grouped = disc.group_by_logical_model(new_routes, old)
    new_canonicals = set(new_grouped.keys())
    old_canonicals = set(old["logical_models"].keys())
    added = sorted(new_canonicals - old_canonicals)
    assert any("qwen" in a or "coder" in a for a in added)


# ── test_key_masking ──────────────────────────────────────────────────────────

def test_mask_nvapi_key():
    text = "Authorization: Bearer nvapi-abc123XYZ"
    assert "nvapi-***MASKED***" in disc.mask_keys(text)
    assert "abc123XYZ" not in disc.mask_keys(text)


def test_mask_openrouter_key():
    text = "key=sk-or-v1-SECRETKEYVALUE"
    masked = disc.mask_keys(text)
    assert "SECRETKEYVALUE" not in masked
    assert "sk-or-***MASKED***" in masked


def test_mask_gemini_key():
    text = "AIzaSyDEF456GHI789"
    masked = disc.mask_keys(text)
    assert "DEF456GHI789" not in masked


def test_mask_no_key():
    text = "This text has no API keys in it."
    assert disc.mask_keys(text) == text


# ── test_atomic_registry_write ────────────────────────────────────────────────

def test_atomic_registry_write(tmp_path, monkeypatch):
    monkeypatch.setattr(disc, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(disc, "REGISTRY_PATH", tmp_path / "model_registry.json")

    registry = {
        "updated_at": "2026-07-13T10:00:00",
        "scan_ttl_seconds": 86400,
        "provider_priority": ["NVIDIA"],
        "logical_models": {},
    }
    disc.save_registry(registry)

    loaded = disc.load_registry()
    assert loaded["provider_priority"] == ["NVIDIA"]
    # Ensure no leftover .tmp file
    assert not (tmp_path / "model_registry.tmp").exists()


# ── test_registry_ttl ─────────────────────────────────────────────────────────

def test_registry_fresh_within_ttl():
    fresh_ts = time.strftime("%Y-%m-%dT%H:%M:%S")
    registry = {"updated_at": fresh_ts, "scan_ttl_seconds": 86400}
    assert disc.registry_is_fresh(registry) is True


def test_registry_stale_past_ttl():
    # 2 days ago
    stale_ts = time.strftime("%Y-%m-%dT%H:%M:%S",
                             time.localtime(time.time() - 2 * 86400))
    registry = {"updated_at": stale_ts, "scan_ttl_seconds": 86400}
    assert disc.registry_is_fresh(registry) is False


# ── test_update_route_metrics ─────────────────────────────────────────────────

def test_update_metrics_ewma():
    registry = {
        "logical_models": {
            "glm-5.2": {
                "routes": [
                    {**_make_route("NVIDIA", "nvidia/z-ai/glm-5.2"),
                     "latency_ms_ewma": None, "success_rate": None, "sample_count": 0}
                ]
            }
        }
    }
    disc.update_route_metrics(registry, "nvidia/z-ai/glm-5.2", success=True, latency_ms=800.0)
    route = registry["logical_models"]["glm-5.2"]["routes"][0]
    assert route["latency_ms_ewma"] == 800.0
    assert route["sample_count"] == 1
    assert route["last_status"] == "ok"

    disc.update_route_metrics(registry, "nvidia/z-ai/glm-5.2", success=False)
    route = registry["logical_models"]["glm-5.2"]["routes"][0]
    assert route["last_status"] == "fail"
    assert route["success_rate"] < 1.0
