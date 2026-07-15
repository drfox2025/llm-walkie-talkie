import unittest
import json
import tempfile
import os
import shutil
from pathlib import Path
import walkie

class TestSession(unittest.TestCase):
    def setUp(self):
        # Point walkie's CONFIG_DIR and SESSION_DIR to a temporary location
        self.test_dir = Path(tempfile.mkdtemp())
        self._orig_config_dir = walkie.CONFIG_DIR
        self._orig_session_dir = walkie.SESSION_DIR
        
        walkie.CONFIG_DIR = self.test_dir
        walkie.SESSION_DIR = self.test_dir / 'sessions'
        walkie.SESSION_DIR.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        walkie.CONFIG_DIR = self._orig_config_dir
        walkie.SESSION_DIR = self._orig_session_dir
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_session_round_trip(self):
        session_id = "test-session-123"
        data = {
            "id": session_id,
            "messages": [
                {"role": "user", "content": "hello"},
                {"role": "assistant", "content": "world"}
            ]
        }
        walkie.save_session(session_id, data)
        
        loaded = walkie.load_session(session_id)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded["id"], session_id)
        self.assertEqual(len(loaded["messages"]), 2)
        self.assertEqual(loaded["messages"][0]["content"], "hello")

    def test_session_path_traversal_sanitizer(self):
        session_id = "../../../etc/passwd"
        data = {"id": session_id, "messages": []}
        walkie.save_session(session_id, data)
        
        # Path should be sanitized and saved safely inside the SESSION_DIR
        # '.' is preserved by the regex, '/' becomes '-'
        safe_name = "..-..-..-etc-passwd.json"
        expected_path = walkie.SESSION_DIR / safe_name
        self.assertTrue(expected_path.exists())

    def test_session_lru_trim_with_system_preservation(self):
        session_id = "test-lru-trim"
        messages = [{"role": "system", "content": "system_prompt"}]
        # Add 30 turns (15 user-assistant exchanges)
        for i in range(15):
            messages.append({"role": "user", "content": f"user {i}"})
            messages.append({"role": "assistant", "content": f"assistant {i}"})
            
        data = {"id": session_id, "messages": messages}
        walkie.save_session(session_id, data)
        
        loaded = walkie.load_session(session_id)
        self.assertIsNotNone(loaded)
        loaded_msgs = loaded["messages"]
        
        # Cap is 20. First msg must be system prompt, remaining 19 are preserved.
        self.assertEqual(len(loaded_msgs), 20)
        self.assertEqual(loaded_msgs[0]["role"], "system")
        self.assertEqual(loaded_msgs[0]["content"], "system_prompt")
        
        # Check that the oldest non-system messages were pruned.
        # Since we keep last 19 out of 30, it prunes the first 11 messages.
        # messages[11] is user 5, which is pruned. messages[12] is assistant 5 (kept as index 1).
        # messages[13] is user 6, kept as index 2.
        self.assertEqual(loaded_msgs[1]["role"], "assistant")
        self.assertEqual(loaded_msgs[1]["content"], "assistant 5")
        self.assertEqual(loaded_msgs[2]["role"], "user")
        self.assertEqual(loaded_msgs[2]["content"], "user 6")

    def test_session_turns_trim(self):
        session_id = "test-turns-trim"
        # Test loop turns trimming
        turns = [{"iteration": i, "score": 100} for i in range(30)]
        data = {"id": session_id, "turns": turns}
        walkie.save_session(session_id, data)
        
        loaded = walkie.load_session(session_id)
        self.assertIsNotNone(loaded)
        self.assertEqual(len(loaded["turns"]), 20)
        self.assertEqual(loaded["turns"][0]["iteration"], 10)
