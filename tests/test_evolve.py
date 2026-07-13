import json
import tempfile
import unittest
from pathlib import Path

# Add the parent directory to the path so we can import evolve
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

import evolve as ev

class TestEvolve(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)
        
        # Override the backups directory for testing
        self.original_get_backups_dir = ev.get_backups_dir
        
        def mock_get_backups_dir():
            d = self.temp_path / "backups"
            d.mkdir(parents=True, exist_ok=True)
            return d
            
        ev.get_backups_dir = mock_get_backups_dir
        
        # Create a dummy rule file
        self.dummy_rules_path = self.temp_path / "AGENTS.md"
        with open(self.dummy_rules_path, "w", encoding="utf-8") as f:
            f.write("## Section 1\n<!-- EVOLVE_SECTION: CODING -->\n- Rule 1\n\n## Section 2\n<!-- EVOLVE_SECTION: TOOLS -->\n- Rule 2\n")
            
    def tearDown(self):
        ev.get_backups_dir = self.original_get_backups_dir
        self.temp_dir.cleanup()
        
    def test_parse_json_valid(self):
        llm_response = '''```json
        {
          "critique": "Test critique",
          "suggested_rule": {
            "target_file": "scratch/AGENTS.md",
            "section_anchor": "CODING",
            "action": "append",
            "content": "- Test rule"
          }
        }
        ```'''
        data = ev.parse_evolution_json(llm_response)
        self.assertEqual(data["critique"], "Test critique")
        self.assertEqual(data["suggested_rule"]["section_anchor"], "CODING")
        
    def test_backup_and_restore(self):
        # 1. Backup
        backup_path = ev.backup_rules(self.dummy_rules_path)
        self.assertTrue(backup_path.exists())
        
        # 2. Modify original
        with open(self.dummy_rules_path, "a", encoding="utf-8") as f:
            f.write("\nMODIFIED")
            
        # 3. Restore
        restored_path = ev.restore_rules(backup_path.name, self.temp_path)
        self.assertTrue(restored_path.exists())
        self.assertEqual(restored_path, self.dummy_rules_path)
        
        # Verify content
        with open(self.dummy_rules_path, "r", encoding="utf-8") as f:
            content = f.read()
            self.assertNotIn("MODIFIED", content)
            
    def test_inject_rule_success(self):
        success, msg = ev.inject_rule(self.dummy_rules_path, "CODING", "- New injected rule")
        self.assertTrue(success)
        
        with open(self.dummy_rules_path, "r", encoding="utf-8") as f:
            content = f.read()
            self.assertIn("- New injected rule", content)
            
    def test_inject_rule_idempotency(self):
        success, msg = ev.inject_rule(self.dummy_rules_path, "CODING", "- New injected rule")
        self.assertTrue(success)
        
        # Try again with same rule
        success, msg = ev.inject_rule(self.dummy_rules_path, "CODING", "- New injected rule")
        self.assertFalse(success)
        self.assertIn("Idempotency check failed", msg)
        
    def test_inject_rule_missing_anchor_fallback(self):
        # Anchor is missing but other anchors exist -> falls back and succeeds
        success, msg = ev.inject_rule(self.dummy_rules_path, "NONEXISTENT", "- Fallback rule")
        self.assertTrue(success)
        
        with open(self.dummy_rules_path, "r", encoding="utf-8") as f:
            content = f.read()
            self.assertIn("- Fallback rule", content)
            
    def test_inject_rule_no_anchors_creation(self):
        # Create a file with no anchors at all
        no_anchor_file = self.temp_path / "NO_ANCHORS.md"
        with open(no_anchor_file, "w", encoding="utf-8") as f:
            f.write("# Simple File\n")
            
        success, msg = ev.inject_rule(no_anchor_file, "NEW_SECTION", "- Created rule")
        self.assertTrue(success)
        self.assertIn("Created new section", msg)
        
        with open(no_anchor_file, "r", encoding="utf-8") as f:
            content = f.read()
            self.assertIn("<!-- EVOLVE_SECTION: NEW_SECTION -->", content)
            self.assertIn("- Created rule", content)

if __name__ == '__main__':
    unittest.main()
