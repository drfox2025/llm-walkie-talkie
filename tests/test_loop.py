import unittest
import json
import tempfile
import os
import shutil
from pathlib import Path
import yaml

import token_lint

class TestLoopEngine(unittest.TestCase):
    def setUp(self):
        # Create a temporary directory for tests
        self.test_dir = Path(tempfile.mkdtemp())
        self.contract_path = self.test_dir / "theme.contract.yaml"
        
        # Write a dummy contract
        self.contract_data = {
            "meta": {
                "version": 1,
                "framework": "react",
                "styling": "tailwind",
                "amended_by": []
            },
            "tokens": {
                "color": {
                    "bg.default": "#ffffff",
                    "brand.primary": "#2563eb"
                },
                "spacing": [0, 4, 8, 16],
                "radius": [0, 4, 8],
                "font_size": [12, 14, 16]
            },
            "components": {
                "Button": {
                    "import": "@/components/ui/Button",
                    "variants": ["primary", "secondary"]
                }
            },
            "enforcement": {
                "token_lint": {
                    "fail_on_offlist_color": True,
                    "fail_on_offlist_spacing": True,
                    "fail_on_offlist_radius": True,
                    "scan_globs": ["src/**/*.tsx", "src/**/*.css"],
                    "allow_files": ["src/theme/tokens.ts", "theme.contract.yaml"]
                },
                "component_usage": {
                    "forbid_raw": ["button"]
                }
            }
        }
        with open(self.contract_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(self.contract_data, f)

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_token_lint_rejects_off_token_color(self):
        # Off-token color #ff0000
        content = """
        const style = { color: '#ff0000', margin: '4px' };
        """
        res = token_lint.run_gate({"src/components/MyButton.tsx": content}, str(self.contract_path))
        self.assertFalse(res["passed"])
        self.assertIn("Off-token color literal", res["feedback"])

    def test_token_lint_rejects_off_token_spacing(self):
        # Off-token spacing value 13px (only 0, 4, 8, 16 are allowed)
        content = """
        const style = { color: '#2563eb', padding: '13px' };
        """
        res = token_lint.run_gate({"src/components/MyButton.tsx": content}, str(self.contract_path))
        self.assertFalse(res["passed"])
        self.assertIn("Off-scale px value 13", res["feedback"])

    def test_component_usage_rejects_raw_button(self):
        # Raw <button> is forbidden under component_usage.forbid_raw
        content = """
        export default function App() {
            return <button>Click me</button>;
        }
        """
        res = token_lint.run_gate({"src/components/MyButton.tsx": content}, str(self.contract_path))
        self.assertFalse(res["passed"])
        self.assertIn("Raw <button> forbidden", res["feedback"])

    def test_consistency_check_passes_same_token_buttons_diff_content(self):
        # Two buttons conforming to the design tokens
        content1 = """
        import { Button } from "@/components/ui/Button";
        const b1 = <Button variant="primary" style={{ padding: '8px' }}>Login</Button>;
        """
        content2 = """
        import { Button } from "@/components/ui/Button";
        const b2 = <Button variant="primary" style={{ padding: '16px' }}>Log Out</Button>;
        """
        res = token_lint.run_gate({
            "src/components/Btn1.tsx": content1,
            "src/components/Btn2.tsx": content2
        }, str(self.contract_path))
        self.assertTrue(res["passed"])

    def test_validate_contract_schema_valid(self):
        from walkie import validate_contract_schema
        valid_contract = {
            "meta": {"version": 1},
            "tokens": {},
            "components": {},
            "rules": [],
            "enforcement": {}
        }
        self.assertTrue(validate_contract_schema(valid_contract))

    def test_validate_contract_schema_invalid(self):
        from walkie import validate_contract_schema
        invalid_contract = {
            "meta": {},
            "tokens": []
        }
        self.assertFalse(validate_contract_schema(invalid_contract))

    def test_parse_loop_patches_valid(self):
        from walkie import parse_loop_patches
        reply = """
Here is the patch output:
<<<<
src/components/MyButton.tsx
const val = 12;
====
const val = 16;
>>>>
Some concluding text here.
"""
        patches = parse_loop_patches(reply)
        self.assertEqual(len(patches), 1)
        self.assertEqual(patches[0][0], "src/components/MyButton.tsx")
        self.assertEqual(patches[0][1], "const val = 12;")
        self.assertEqual(patches[0][2], "const val = 16;")

    def test_parse_loop_patches_mixed_newlines(self):
        from walkie import parse_loop_patches
        reply = "<<<<\r\nsrc/theme.css\r\nbody { margin: 0; }\r\n====\r\nbody { margin: 8px; }\r\n>>>>"
        patches = parse_loop_patches(reply)
        self.assertEqual(len(patches), 1)
        self.assertEqual(patches[0][0], "src/theme.css")
        self.assertEqual(patches[0][1], "body { margin: 0; }")
        self.assertEqual(patches[0][2], "body { margin: 8px; }")

    def test_validate_contract_schema_invalid_subkeys(self):
        from walkie import validate_contract_schema
        contract = {
            "meta": {"version": 1},
            "tokens": {"spacing": "offscale_string"},  # should be list
            "components": {},
            "rules": [],
            "enforcement": {}
        }
        self.assertFalse(validate_contract_schema(contract))

    def test_get_vendor_resolution(self):
        from walkie import get_vendor
        self.assertEqual(get_vendor("openrouter/google/gemini-2.5-flash:free"), "google")
        self.assertEqual(get_vendor("openrouter/nvidia/nemotron-3-ultra-550b-a55b:free"), "nvidia")
        self.assertEqual(get_vendor("openrouter/poolside/laguna-m.1:free"), "poolside")
        self.assertEqual(get_vendor("zenmux/anthropic/claude-4-fable"), "anthropic")
        self.assertEqual(get_vendor("nvidia/z-ai/glm-5.2"), "z-ai")
        self.assertEqual(get_vendor("deepseek/deepseek-coder"), "deepseek")
        
        # Test same-provider-different-vendor start guard mapping
        v1 = get_vendor("openrouter/nvidia/nemotron-3-ultra-550b-a55b:free")
        v2 = get_vendor("openrouter/google/gemini-2.5-flash:free")
        v3 = get_vendor("openrouter/poolside/laguna-m.1:free")
        self.assertEqual(v1, "nvidia")
        self.assertEqual(v2, "google")
        self.assertEqual(v3, "poolside")
        self.assertTrue(len({v1, v2, v3}) == 3)

    def test_get_provider_resolution(self):
        from walkie import get_provider
        self.assertEqual(get_provider("nvidia/z-ai/glm-5.2"), "NVIDIA")
        self.assertEqual(get_provider("openrouter/google/gemini-2.5-flash:free"), "OPENROUTER")
        self.assertEqual(get_provider("gemini/gemini-1.5-flash"), "GEMINI")
        self.assertEqual(get_provider("unknown-prefix/model"), "UNKNOWN")

    def test_extract_patches_with_drifted_markers(self):
        from walkie import extract_patches
        reply = """
Here is the patch:
<<<< REPLACEMENT_START >>>>
original code
==== REPLACEMENT_WITH ===>
new code
<<<< REPLACEMENT_END >>>>
"""
        patches = extract_patches(reply)
        self.assertEqual(len(patches), 1)
        self.assertEqual(patches[0][0].strip(), "original code")
        self.assertEqual(patches[0][1].strip(), "new code")

    def test_token_lint_decimal_px_rejected(self):
        # Even if '4' is allowed, decimal '4.5px' must be rejected
        content = """
        const style = { margin: '4.5px' };
        """
        res = token_lint.run_gate({"src/components/MyButton.tsx": content}, str(self.contract_path))
        self.assertFalse(res["passed"])
        self.assertIn("Fractional px value", res["feedback"])

    def test_indexer_imports_parsing_and_resolution(self):
        import indexer
        # Create a mock workspace layout
        workspace = Path(self.test_dir)
        (workspace / "src" / "components").mkdir(parents=True, exist_ok=True)
        
        button_file = workspace / "src" / "components" / "Button.tsx"
        button_file.write_text("export const Button = () => null;", encoding="utf-8")
        
        app_file = workspace / "src" / "App.tsx"
        app_content = """
        import { Button } from "./components/Button";
        import "@/components/Button";
        import "some-bare-pkg";
        const lazy = import("./components/Button");
        const req = require("./components/Button");
        """
        app_file.write_text(app_content, encoding="utf-8")
        
        index_data = indexer.build_or_update_symbols_index(workspace, force_walk=True)
        
        # Check that imports were parsed
        app_key = "src/App.tsx"
        self.assertIn(app_key, index_data["files"])
        app_imports = index_data["files"][app_key]["imports"]
        self.assertIn("./components/Button", app_imports)
        self.assertIn("@/components/Button", app_imports)
        self.assertIn("some-bare-pkg", app_imports)
        
        # Check dependency resolution maps src/App.tsx as a reverse dep of src/components/Button.tsx
        btn_key = "src/components/Button.tsx"
        resolved_rev = index_data.get("resolved_reverse_deps", {})
        self.assertIn(btn_key, resolved_rev)
        self.assertIn(app_key, resolved_rev[btn_key])

    def test_token_lint_strips_comments(self):
        # Even with an off-token color or spacing value, if it is in comments it should pass
        content = """
        // const style = { color: '#ff0000', margin: '13px' };
        /* off-token color: #aabbcc */
        /*
           multi-line comment:
           margin: 13px;
        */
        """
        res = token_lint.run_gate({"src/components/MyButton.tsx": content}, str(self.contract_path))
        self.assertTrue(res["passed"])

    def test_extract_robust_json(self):
        from walkie import extract_robust_json
        
        # Test clean json
        self.assertEqual(extract_robust_json('{"key": "value"}'), {"key": "value"})
        
        # Test markdown codeblock wrapped
        self.assertEqual(extract_robust_json('```json\n{"key": "value"}\n```'), {"key": "value"})
        
        # Test with surrounding fluff text
        self.assertEqual(extract_robust_json('Some prefix text {"key": "value"} some suffix'), {"key": "value"})

    def test_dashboard_settings_respected(self):
        import walkie
        import discovery
        import os
        import importlib

        # Save original values
        saved = {}
        for var_name in ["LWT_PROVIDER_ORDER", "SESSION_MAX_TURNS", "SESSION_INJECT_TURNS", "SESSION_DIFF_CHAR_CAP"]:
            saved[var_name] = os.environ.get(var_name)

        try:
            # Verify discovery provider priority
            os.environ["LWT_PROVIDER_ORDER"] = "GROQ,OPENAI,GEMINI"
            importlib.reload(discovery)
            self.assertEqual(discovery.PROVIDER_PRIORITY, ["GROQ", "OPENAI", "GEMINI"])

            # Verify session constants from environment
            os.environ["SESSION_MAX_TURNS"] = "35"
            os.environ["SESSION_INJECT_TURNS"] = "12"
            os.environ["SESSION_DIFF_CHAR_CAP"] = "800"
            importlib.reload(walkie)
            self.assertEqual(walkie.SESSION_MAX_TURNS, 35)
            self.assertEqual(walkie.SESSION_INJECT_TURNS, 12)
            self.assertEqual(walkie.SESSION_DIFF_CHAR_CAP, 800)
        finally:
            # Restore original values
            for var_name in saved:
                if saved[var_name] is not None:
                    os.environ[var_name] = saved[var_name]
                else:
                    if var_name in os.environ:
                        del os.environ[var_name]
            importlib.reload(discovery)
            importlib.reload(walkie)

    def test_loop_vendor_guard_fallback_confirm_no(self):
        from click.testing import CliRunner
        import walkie
        runner = CliRunner()
        # Run loop command with same model for all 3 vendors to trigger the vendor guard check
        result = runner.invoke(walkie.cli, [
            "loop",
            "--goal", "Fix a button style",
            "--stop-cmd", 'python -c "import sys; sys.exit(0)"',
            "--design-contract", str(self.contract_path),
            "--gen-model", "nvidia/z-ai/glm-5.2",
            "--audit-model", "nvidia/z-ai/glm-5.2",
            "--redteam-model", "nvidia/z-ai/glm-5.2",
            "--session", "test-fallback-session-no"
        ], input="n\n")
        self.assertIn("Start guard check: Loop requires at least 3 distinct vendors", result.output)
        self.assertIn("No external LLMs found for a 3-vendor group. Fall-back to native agent emulation mode?", result.output)
        self.assertIn("User rejected fallback mode.", result.output)
        self.assertEqual(result.exit_code, 1)

    def test_loop_vendor_guard_fallback_confirm_yes(self):
        from click.testing import CliRunner
        import walkie
        runner = CliRunner()
        # Mock call_llm to prevent real API calls and make it return a success
        original_call_llm = walkie.call_llm
        
        # Clean up tmp file just in case
        tmp_file = Path("test_state.tmp")
        if tmp_file.exists():
            tmp_file.unlink()

        stop_cmd = 'python -c "import sys, pathlib; p = pathlib.Path(\'test_state.tmp\'); (p.write_text(\'\') or sys.exit(1)) if not p.exists() else (p.unlink() or sys.exit(0))"'
        try:
            called_models = []
            def mock_call_llm(model, messages, **opts):
                called_models.append(model)
                # auditor JSON reply format expected
                if "Auditor" in messages[0]["content"]:
                    return json.dumps({
                        "violations": [],
                        "score": 100,
                        "verdict": "SUCCESS",
                        "reason": "Looking good"
                    }), {}
                # redteam JSON reply format expected
                elif "Red Team" in messages[0]["content"]:
                    return json.dumps({
                        "defect_found": False,
                        "description": "None"
                    }), {}
                # implementer reply
                else:
                    return "No patches", {}

            walkie.call_llm = mock_call_llm

            result = runner.invoke(walkie.cli, [
                "loop",
                "--goal", "Fix a button style",
                "--stop-cmd", stop_cmd,
                "--design-contract", str(self.contract_path),
                "--gen-model", "nvidia/z-ai/glm-5.2",
                "--audit-model", "nvidia/z-ai/glm-5.2",
                "--redteam-model", "nvidia/z-ai/glm-5.2",
                "--session", "test-fallback-session-yes",
                "--max-iterations", "2"
            ], input="y\n")

            self.assertIn("Start guard check: Loop requires at least 3 distinct vendors", result.output)
            self.assertIn("Native agent emulation mode activated.", result.output)
            self.assertEqual(result.exit_code, 0)
            # Since it's fallback mode, all calls must go to the native model (nvidia/z-ai/glm-5.2)
            self.assertTrue(len(called_models) > 0)
        finally:
            walkie.call_llm = original_call_llm
            if tmp_file.exists():
                tmp_file.unlink()

    def test_token_lint_rgba_rejected(self):
        import token_lint
        # Verify raw rgba color fails color check
        content = "const style = { color: 'rgba(255, 0, 0, 0.5)' };"
        res = token_lint.run_gate({"src/components/MyButton.tsx": content}, str(self.contract_path))
        self.assertFalse(res["passed"])
        self.assertIn("Off-token rgb/rgba color literal", res["feedback"])

    def test_token_lint_strict_property_separation(self):
        import token_lint
        # spacing has [0, 4, 8, 16], radius has [0, 4, 8], font_size has [12, 14, 16]
        # borderRadius: 16px should fail because 16 is not in radius
        content = "const style = { borderRadius: '16px' };"
        res = token_lint.run_gate({"src/components/MyButton.tsx": content}, str(self.contract_path))
        self.assertFalse(res["passed"])
        self.assertIn("Off-scale px value 16 for radius", res["feedback"])

        # gap: 16px should pass because 16 is in spacing
        content_gap = "const style = { gap: '16px' };"
        res_gap = token_lint.run_gate({"src/components/MyButton.tsx": content_gap}, str(self.contract_path))
        self.assertTrue(res_gap["passed"])

        # margin: 12px should fail because 12 is not in spacing
        content_margin = "const style = { margin: '12px' };"
        res_margin = token_lint.run_gate({"src/components/MyButton.tsx": content_margin}, str(self.contract_path))
        self.assertFalse(res_margin["passed"])
        self.assertIn("Off-scale px value 12 for spacing", res_margin["feedback"])


if __name__ == "__main__":
    unittest.main()
