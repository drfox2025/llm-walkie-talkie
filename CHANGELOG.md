# Changelog

All notable changes to the LLM Walkie-Talkie extension will be documented in this file.

## [1.0.13] - 2026-07-16

### Added
- **OS-level Hard Link Sandbox Creation**: Built a performance fallback using `os.link` when copying workspace directories for standalone sandboxes. Sandbox provisioning is now virtually instant for large projects.
- **Oracle Security Guardrails**: Introduced command execution blocklisting (`is_safe_command`) to restrict hallucinated agents from executing network commands like `curl`, `wget`, `nc`, `ping` during test runs.
- **Oscillation Escalation Mode**: Loop convergence engine now detects MD5 hash diff oscillations and automatically switches to `escalation_mode`—raising the LLM Implementer's temperature to 0.8 and injecting feedback warning alerts to break looping logic traps.
- **English-First Open VSX Layout**: Redesigned extension documentation to place English descriptions, key feature breakdowns, and guides at the top for international compatibility, while maintaining the Vietnamese summaries.
- **Refined Agent Skill Presets**: Documented skill setups for `/ai-consult`, `/lwt-goal`, and `/llm-loop`.

## [1.0.12] - 2026-07-15
- Virtual Sandbox standalone mode setup.
- Initial packaging config.
