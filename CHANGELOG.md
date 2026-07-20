# Changelog

All notable changes to the LLM Walkie-Talkie extension will be documented in this file.

## [1.0.14] - 2026-07-20

### Added
- **Intelligent Fuzzy Resolver (`walkie resolve`)**: New CLI command that automatically resolves informal or partial model names (e.g., "GLM", "Claude") to their exact optimal provider route using substring matching and canonical mapping.
- **Connection Verification Manifest**: Introduced `~/.walkie/verified_models.json` to persistently track models that have successfully connected. The fuzzy resolver prioritizes these known-good models to eliminate blind guesses.
- **Capability Tier Classifier**: Added heuristics to classify models into `flagship`, `advanced`, `mid`, and `small` tiers based on parameter counts and model family tags (e.g., Opus/Pro/Ultra/70b). This disambiguates tied fuzzy matches by picking the most capable model.
- **Semantic Version Scoring**: Added robust regex parsing to extract version numbers (e.g., `4.5` > `4.20`, or `v4-pro`) to ensure requests for a model family always default to the newest version.

### Fixed
- **Failover Resilience Loop Bug**: Fixed a logical flaw in `call_llm()` where non-transient errors (like a `404 Not Found` from a decommissioned endpoint) would prematurely abort the failover loop. The system now gracefully falls back to healthy backup routes regardless of the error type.
- **Empty Query Matching**: Fixed an edge case where an empty string query `""` would mistakenly match all models in the fuzzy resolver.
- **Concurrent Manifest Writes**: Implemented an atomic `verified_manifest_lock` to prevent race conditions when multiple processes update the verified models manifest simultaneously.

## [1.0.13] - 2026-07-16

### Added
- **OS-level Hard Link Sandbox Creation**: Built a performance fallback using `os.link` when copying workspace directories for standalone sandboxes. Sandbox provisioning is now virtually instant for large projects.
- **Oracle Security Guardrails**: Introduced command execution blocklisting (`is_safe_command`) to restrict hallucinated agents from executing network commands like `curl`, `wget`, `nc`, `ping` during test runs.
- **Oscillation Escalation Mode**: Loop convergence engine now detects MD5 hash diff oscillations and automatically switches to `escalation_mode`—raising the LLM Implementer's temperature to 0.8 and injecting feedback warning alerts to break looping logic traps.
- **English-First Open VSX Layout**: Redesigned extension documentation to place English descriptions, key feature breakdowns, and guides at the top for international compatibility, while maintaining the Vietnamese summaries.
- **Refined Agent Skill Presets**: Documented skill setups for `/ai-consult`, `/lwt-goal`, and `/llm-loop`.

## [1.0.12] - 2026-07-15

### Added
- **Virtual Sandbox Standalone Mode**: Initial framework for creating isolated testing environments to protect the host workspace.
- **Initial Packaging Config**: Baseline Open VSX packaging manifests and metadata.
