"""token_lint.py — deterministic Design Contract enforcement gate.

Ground-truth PASS/FAIL for the llm-loop UI gates. Operates on the modified/patched files list (or the entire in-scope tree on iteration 1) so that compliance is checked against design tokens. Structured output feeds back into the consult repair prompt. LLM panel verdicts stay advisory.
"""
import re
import fnmatch
import os
from pathlib import Path
from typing import List, Dict, Any

import yaml  # add to pyproject/requirements


def _normalize_path(file_path: str) -> str:
    """Normalize path to relative (if possible) with forward slashes."""
    try:
        rel = os.path.relpath(file_path, os.getcwd())
        return rel.replace("\\", "/")
    except ValueError:
        # Cross-drive on Windows or other error
        return file_path.replace("\\", "/")


# --- literal detectors (only used-value contexts, not token source files) ---
HEX_RE      = re.compile(r"#[0-9a-fA-F]{3,8}\b")
# px literals in CSS/JSX: margin/padding/gap/radius/font-size assignments
# NOTE: Specifically scoped to absolute px units. Unitless values and relative units (rem/em)
# are bypassed to support responsive layouts.
PX_RE       = re.compile(r"(?<![\w-])(-?\d+(?:\.\d+)?)px\b")
# raw HTML element usage in JSX (forbidden primitives)
RAW_EL_RE   = lambda tag: re.compile(rf"<\s*{tag}(\s|>|/)")
RGB_RGBA_RE = re.compile(r"\brgba?\([^\)]+\)")


def load_contract(path: str) -> Dict[str, Any]:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Design Contract not found: {path}")
    return yaml.safe_load(p.read_text(encoding="utf-8"))


def _file_exempt(file_path: str, contract: Dict[str, Any]) -> bool:
    allow = contract.get("enforcement", {}).get("token_lint", {}).get("allow_files", [])
    # Convert file path to string and check if it matches any pattern
    f_str = _normalize_path(file_path)
    return any(fnmatch.fnmatch(f_str, g) or f_str.endswith(g) for g in allow)


def _in_scope(file_path: str, contract: Dict[str, Any]) -> bool:
    globs = contract.get("enforcement", {}).get("token_lint", {}).get("scan_globs", ["**/*.tsx", "**/*.jsx", "**/*.html", "**/*.css", "**/*.js", "**/*.ts"])
    f_str = _normalize_path(file_path)
    return any(fnmatch.fnmatch(f_str, g) for g in globs)


def lint_content(file_path: str, content: str, contract: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Return a list of structured violations for one file's (patched) content."""
    tl = contract.get("enforcement", {}).get("token_lint", {})
    if _file_exempt(file_path, contract) or not _in_scope(file_path, contract):
        return []

    tokens   = contract.get("tokens", {})
    colors   = {v.lower() for v in tokens.get("color", {}).values()}
    spacing  = set(tokens.get("spacing", []))
    radius   = set(tokens.get("radius", []))
    fsizes   = set(tokens.get("font_size", []))
    forbid   = contract.get("enforcement", {}).get("component_usage", {}).get("forbid_raw", [])

    violations: List[Dict[str, Any]] = []
    
    # Strip comments to prevent false positives in commented code
    # We remove block comments /* ... */ first across the entire content if present,
    # or handle them line-by-line. To keep line numbers exact, we replace comment 
    # characters with spaces so line structure is preserved.
    processed_content = content
    # Replace block comments with spaces keeping newline structure
    def repl_block(m):
        return re.sub(r'[^\r\n]', ' ', m.group(0))
    processed_content = re.sub(r'/\*.*?\*/', repl_block, processed_content, flags=re.DOTALL)

    for i, line in enumerate(processed_content.splitlines(), start=1):
        # Strip inline // comments
        if "//" in line:
            # Simple strip; note this might strip inside strings but is a safe fallback for design tokens
            line = line.split("//", 1)[0]
        # Strip python style comments if python file
        if file_path.endswith(".py") and "#" in line:
            line = line.split("#", 1)[0]

        # 1) off-token colors
        if tl.get("fail_on_offlist_color", True):
            for m in HEX_RE.finditer(line):
                if m.group(0).lower() not in colors:
                    violations.append(_v(file_path, i, "color", m.group(0),
                                         "Off-token color literal. Use a semantic token."))
            for m in RGB_RGBA_RE.finditer(line):
                violations.append(_v(file_path, i, "color", m.group(0),
                                     "Off-token rgb/rgba color literal. Use a semantic token."))
        # 2) off-token px (spacing/radius/font). Check per-scale strictly.
        if tl.get("fail_on_offlist_spacing", True):
            for m in PX_RE.finditer(line):
                raw_val = m.group(1)
                # Reject fractional pixel values (e.g., 4.5px) since only integer scales are allowed
                if '.' in raw_val:
                    violations.append(_v(file_path, i, "spacing", m.group(0),
                                         f"Fractional px value {raw_val}px not allowed. Use integer token from scale."))
                    continue
                try:
                    val = int(raw_val)
                except ValueError:
                    continue

                # Heuristic to identify token type to avoid token list cross-bypass
                line_lower = line.lower()
                is_radius = "radius" in line_lower
                is_font = "font" in line_lower or "size" in line_lower
                
                if is_radius:
                    allowed_scale = radius
                    scale_name = "radius"
                elif is_font:
                    allowed_scale = fsizes
                    scale_name = "font_size"
                else:
                    allowed_scale = spacing
                    scale_name = "spacing"

                if val not in allowed_scale:
                    violations.append(_v(file_path, i, scale_name, m.group(0),
                                         f"Off-scale px value {val} for {scale_name}. Use a token from the {scale_name} scale."))
        # 3) forbidden raw elements (must use canonical component)
        for tag in forbid:
            if RAW_EL_RE(tag).search(line):
                violations.append(_v(file_path, i, "component", f"<{tag}>",
                                     f"Raw <{tag}> forbidden. Use the canonical component."))
    return violations


def _v(file, line, kind, found, msg):
    return {"file": file, "line": line, "type": kind, "found": found, "message": msg}


def run_gate(patched_files: Dict[str, str], contract_path: str) -> Dict[str, Any]:
    """patched_files: {path: full_content_after_patch}. Returns gate verdict."""
    contract = load_contract(contract_path)
    all_v: List[Dict[str, Any]] = []
    for fpath, content in patched_files.items():
        all_v.extend(lint_content(fpath, content, contract))

    passed = len(all_v) == 0
    return {
        "gate": "token-lint",
        "passed": passed,
        "violation_count": len(all_v),
        "violations": all_v,
        "feedback": "" if passed else "\n".join(
            f"[{v['type']}] {v['file']}:{v['line']} — {v['found']}: {v['message']}"
            for v in all_v
        ),
    }
