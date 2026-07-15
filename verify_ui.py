# verify_ui.py - Automated validation of LWT Preferences Panel

import re
from pathlib import Path

def test_ui_security_and_links():
    ui_dir = Path(__file__).parent / "lwt-preferences-ui"
    html_path = ui_dir / "index.html"
    js_path = ui_dir / "app.js"
    css_path = ui_dir / "style.css"

    # 1. Assert file existences
    assert html_path.exists(), "index.html is missing!"
    assert js_path.exists(), "app.js is missing!"
    assert css_path.exists(), "style.css is missing!"

    # 2. Check html asset references
    html_content = html_path.read_text(encoding="utf-8")
    assert 'href="style.css"' in html_content, "index.html does not link style.css"
    assert 'src="app.js"' in html_content, "index.html does not link app.js"

    # 3. Check js masking rules (security check)
    js_content = js_path.read_text(encoding="utf-8")
    assert "maskKey" in js_content, "maskKey function is missing from app.js!"
    assert "•" in js_content, "maskKey should replace key bodies with bullet characters!"
    
    # Verify no hardcoded secrets inside javascript state
    pattern = re.compile(r'(nvapi-|sk-or-|sk-ant-|AIzaSy)[a-zA-Z0-9_\-]{15,}')
    found_secrets = pattern.findall(js_content)
    assert not found_secrets, f"Detected hardcoded plaintext credentials in code: {found_secrets}"

    print("[OK] All security and structure verification checks PASSED successfully!")

if __name__ == "__main__":
    test_ui_security_and_links()
