import json
import os
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Tuple, List

# Core regex to find the evolution section anchor
EVOLVE_ANCHOR_REGEX = re.compile(r"<!--\s*EVOLVE_SECTION:\s*(?P<section_name>[A-Z0-9_-]+)\s*-->", re.IGNORECASE)

ARCHITECT_SYSTEM_PROMPT = """You are an Agent Architect. An autonomous IDE AI agent is providing you with an abstract of its recent execution (Chain of Thought).
Your job is to identify ONE specific behavioral inefficiency or mistake, and suggest a permanent rule change to its rulebook to prevent this in the future.

You MUST return your response as a valid JSON object with the following structure:
{
  "critique": "A brief explanation of what went wrong or could be optimized.",
  "suggested_rule": {
    "target_file": "The file to modify (usually AGENTS.md)",
    "section_anchor": "The ALL_CAPS name of the section anchor to append to (e.g. CODING, TOOLS, WORKFLOW)",
    "action": "append",
    "content": "- Your concise, actionable rule here (always start with a bullet point)."
  }
}

Keep your critique under 2 sentences. Make the rule extremely actionable. Do not output anything outside of this JSON structure.
"""

def get_backups_dir() -> Path:
    """Get the directory for rule backups."""
    walkie_dir = Path.home() / ".walkie"
    backups_dir = walkie_dir / "backups"
    backups_dir.mkdir(parents=True, exist_ok=True)
    return backups_dir

def backup_rules(file_path: Path) -> Path:
    """Creates a timestamped backup of the rule file."""
    if not file_path.exists():
        raise FileNotFoundError(f"Cannot backup: {file_path} does not exist.")
        
    backups_dir = get_backups_dir()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_filename = f"{file_path.name}.{timestamp}.bak"
    backup_path = backups_dir / backup_filename
    
    shutil.copy2(file_path, backup_path)
    return backup_path

def restore_rules(backup_filename: str, target_dir: Path) -> Path:
    """Restores a rule file from a specific backup."""
    backups_dir = get_backups_dir()
    backup_path = backups_dir / backup_filename
    
    if not backup_path.exists():
        raise FileNotFoundError(f"Backup not found: {backup_path}")
        
    # Infer target filename by stripping the timestamp and .bak
    # Example: AGENTS.md.20260713_110000.bak -> AGENTS.md
    parts = backup_filename.split('.')
    if len(parts) >= 3 and parts[-1] == "bak":
        target_name = ".".join(parts[:-2])
    else:
        target_name = backup_filename.replace(".bak", "")
        
    target_path = target_dir / target_name
    shutil.copy2(backup_path, target_path)
    return target_path

def list_backups() -> List[str]:
    """Returns a list of all backup filenames, sorted newest first."""
    backups_dir = get_backups_dir()
    if not backups_dir.exists():
        return []
    
    backups = [f.name for f in backups_dir.iterdir() if f.suffix == ".bak"]
    backups.sort(reverse=True)
    return backups

def parse_evolution_json(llm_response: str) -> Dict[str, Any]:
    """Extracts and parses the JSON payload from the Architect LLM response."""
    # Sometimes LLMs wrap JSON in markdown blocks
    clean_resp = llm_response.strip()
    if clean_resp.startswith("```json"):
        clean_resp = clean_resp[7:]
    elif clean_resp.startswith("```"):
        clean_resp = clean_resp[3:]
        
    if clean_resp.endswith("```"):
        clean_resp = clean_resp[:-3]
        
    clean_resp = clean_resp.strip()
    
    try:
        data = json.loads(clean_resp)
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse LLM response as JSON: {e}\nRaw Response:\n{llm_response}")
        
    if "critique" not in data or "suggested_rule" not in data:
        raise ValueError("JSON response missing required keys ('critique', 'suggested_rule').")
        
    return data

def inject_rule(file_path: Path, section_anchor: str, rule_content: str) -> Tuple[bool, str]:
    """
    Injects a rule into the target file under the specified HTML anchor.
    Returns (Success, Message).
    """
    if not file_path.exists():
        return False, f"Target file {file_path} does not exist."
        
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
        
    # 1. Idempotency Check: if this exact string is already in the file, skip
    # Strip whitespace/bullets for a fuzzier match if needed, but exact substring is safer
    if rule_content.strip() in content:
        return False, "Rule is already present in the file (Idempotency check failed)."
        
    # 2. Find the anchor
    lines = content.split('\n')
    anchor_idx = -1
    for i, line in enumerate(lines):
        match = EVOLVE_ANCHOR_REGEX.search(line)
        if match and match.group("section_name").upper() == section_anchor.upper():
            anchor_idx = i
            break
            
    if anchor_idx == -1:
        # Fallback 1: Look for any evolution anchor at all
        for i, line in enumerate(lines):
            match = EVOLVE_ANCHOR_REGEX.search(line)
            if match:
                anchor_idx = i
                section_anchor = match.group("section_name")
                break
                
        # Fallback 2: Append new section to the end of the file
        if anchor_idx == -1:
            lines.append(f"\n## {section_anchor.title()} Guidelines")
            lines.append(f"<!-- EVOLVE_SECTION: {section_anchor.upper()} -->")
            lines.insert(len(lines), rule_content.strip())
            with open(file_path, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))
            return True, f"Created new section <!-- EVOLVE_SECTION: {section_anchor.upper()} --> at the end of the file."
        
    # 3. Inject the rule right after the anchor
    lines.insert(anchor_idx + 1, rule_content.strip())
    
    # 4. Write back
    with open(file_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
        
    return True, "Rule successfully injected."
