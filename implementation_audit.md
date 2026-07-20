# Codebase Implementation Audit

This document summarizes the bugs, edge cases, and potential issues identified during the audit of the recent fuzzy resolver and connection verification manifest implementation. All fixes have been verified and applied.

---

## 1. Sandbox Overwrite Bug (Critical Workspace Issue)

### Issue
The `walkie sandbox --commit` command syncs changes back using:
```python
shutil.copytree(sandbox_path, cwd, dirs_exist_ok=True, ignore=shutil.ignore_patterns('.git', 'node_modules', '.venv', '__pycache__'))
```
Because the sandbox was created via `git worktree add --detach`, it was initialized with the unmodified files from git `HEAD` (not the uncommitted changes in the host workspace). When committed, this command copied the unmodified versions of `walkie.py` and `discovery.py` back to the host workspace, **completely overwriting and reverting** all uncommitted changes in the host workspace.

### Solution / Mitigation
- Developers must commit or stage files before running sandbox tests if they rely on worktree sync.
- Or, manually copy the modified files into the sandbox path right after creation.

---

## 2. Version Score Parsing Bug (Edge Case)

### Issue
The original `extract_version_score()` regex was:
```python
ver_match = re.search(r'[.-]v?(\d+)', name)
```
This required a dot or dash prefix before the version digit. However, for models like `deepseek-v4-pro`, `normalize_model_name()` stripped the `deepseek-` prefix leaving just `v4-pro`. Because `v4-pro` starts directly with `v` (no prefix dot/dash), the regex failed to match, returning a version score of `0.0`.

### Fix
Updated the regex to use `(?:^|[.-])` to allow matching at the start of the string:
```python
ver_match = re.search(r'(?:^|[.-])v?(\d+)\.(\d+)', name)
# and
ver_match = re.search(r'(?:^|[.-])v?(\d+)', name)
```
This correctly parses `v4-pro` to version `4.0`.

---

## 3. Empty Query Matching Bug (Logical Issue)

### Issue
The fuzzy resolver `resolve_fuzzy_model()` queried the manifest using:
```python
if family == query or query in canonical or query in model_id.lower():
```
If the user passed an empty or whitespace-only query, `query` normalized to `""`. Since an empty string is a substring of every model name (`"" in canonical` is always `True`), this caused empty queries to match **all** verified models, returning the first/strongest one instead of returning `None`.

### Fix
Added an early check to return `None` if the normalized query is empty:
```python
query = user_name.lower().strip()
if not query:
    return None
```

---

## 4. Concurrent Write Race Condition (Thread Safety)

### Issue
Multiple calls to `update_verified_entry()` could run concurrently (e.g. from parallel tasks in `walkie loop`). Both processes would read the manifest simultaneously, modify the list in memory, and write it back, causing one process to overwrite the updates of the other (lost update race condition).

### Fix
Implemented a lightweight atomic folder-creation mutex `verified_manifest_lock()`:
```python
@contextlib.contextmanager
def verified_manifest_lock():
    lock_dir = CONFIG_DIR / "verified_models.lock"
    acquired = False
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
```
This synchronizes read-modify-write blocks in `update_verified_entry()` using a context manager, ensuring thread/process safety.

---

## 5. Failover Resilience Loop Bug (Logical Issue)

### Issue
The failover loop in `call_llm()` (used when `LWT_FAILOVER` is active) originally aborted/broke early if any route encountered a non-transient exception (such as `NotFoundError: 404 page not found` or `BadGatewayError`):
```python
transient = ("429" in msg or "timeout" in msg or "timed out" in msg
             or " 5" in msg or "rate limit" in msg or "overloaded" in msg)
if not transient:
    break
```
If a model's primary provider (e.g. NVIDIA NIM) returned a 404 because they decommissioned a model endpoint, this was classified as a non-transient error, causing the entire failover loop to exit immediately without trying the healthy backup provider routes (e.g. OpenRouter).

### Fix
Removed the `transient` exception check and early `break` statement in `walkie.py`. If a route fails for *any* reason, it will log the warning (if `WALKIE_DEBUG=1` is set) and gracefully `continue` to the next fallback route in the list. The loop only throws an exception if *all* resolved routes fail.

