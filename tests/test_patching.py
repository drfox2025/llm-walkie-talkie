import pytest
from walkie import extract_patches, apply_patches

def test_extract_patches_normal():
    llm_output = """
Here is the fix:

<<<< REPLACEMENT_START >>>>
def add(a, b):
    return a + b
==== REPLACEMENT_WITH ====
def add(a, b):
    # Fixed addition
    return a + b
<<<< REPLACEMENT_END >>>>

Hope this helps!
"""
    patches = extract_patches(llm_output)
    assert len(patches) == 1
    orig, rep = patches[0]
    assert "def add(a, b):" in orig
    assert "# Fixed addition" in rep

def test_extract_patches_tight_borders():
    llm_output = """<<REPLACEMENT_START>>def foo():
    pass
==REPLACEMENT_WITH==def foo():
    return True
<<REPLACEMENT_END>>"""
    patches = extract_patches(llm_output)
    assert len(patches) == 1
    orig, rep = patches[0]
    assert orig == "def foo():\n    pass"
    assert rep == "def foo():\n    return True"

def test_apply_patches_exact_match():
    original_code = "def add(a, b):\n    return a + b\n"
    patches = [
        ("def add(a, b):\n    return a + b", "def add(a, b):\n    # Fixed addition\n    return a + b")
    ]
    new_code, error = apply_patches(original_code, patches)
    assert error is None
    assert "# Fixed addition" in new_code

def test_apply_patches_exact_match_ambiguous():
    original_code = "def foo():\n    pass\ndef bar():\n    pass\ndef foo():\n    pass\n"
    patches = [
        ("def foo():\n    pass", "def foo():\n    return True")
    ]
    new_code, error = apply_patches(original_code, patches)
    assert error is not None
    assert "Ambiguous patch block" in error

def test_apply_patches_normalized_fallback():
    # Original has mixed indentation and newlines, patch provided lacks proper indentation
    original_code = "class Test:\n    def foo():\n        pass\n"
    patches = [
        ("def foo():\n    pass", "def foo():\n    return True")
    ]
    new_code, error = apply_patches(original_code, patches, normalize=True)
    assert error is None
    # We expect the 'return True' to dynamically re-indent to match the 4 spaces of the matched block
    assert "    def foo():\n        return True" in new_code

def test_apply_patches_normalized_ambiguous():
    # File has two identical functions that differ only in whitespace
    original_code = "class Test:\n    def foo():\n        pass\n\ndef foo():\n    pass\n"
    patches = [
        ("def foo():\n  pass", "def foo():\n  return True")
    ]
    new_code, error = apply_patches(original_code, patches, normalize=True)
    assert error is not None
    assert "Ambiguous patch block: normalized original block matches 2 times" in error
