import os
import sys
import shutil
import subprocess
from pathlib import Path

def main():
    print("====================================================")
    print(" LLM Walkie-Talkie Installer & Setup Helper")
    print("====================================================\n")

    # Step 1: Install the package
    print("[1/3] Installing package locally via pip...")
    try:
        subprocess.run([sys.executable, "-m", "pip", "install", "."], check=True)
        print("[OK] Package installed successfully!\n")
    except subprocess.CalledProcessError as e:
        print(f"[FAIL] Failed to install package: {e}")
        sys.exit(1)

    # Step 2: Configure API Keys
    print("[2/3] Configuring API keys (Setup)...")
    print("The setup process will mask your entries and validate formats.\n")
    # Run setup command (pauses for user input)
    try:
        subprocess.run(["walkie", "setup"], check=True)
    except Exception:
        # Fallback if entry point is not registered in PATH yet
        try:
            subprocess.run([sys.executable, "walkie.py", "setup"], check=True)
        except Exception as e:
            print(f"[FAIL] Setup failed: {e}")
            sys.exit(1)

    # Step 3: Install Antigravity Plugin
    print("\n[3/3] Installing Antigravity Plugin...")
    choice = input("Do you want to install LWT as an Antigravity Plugin globally? (y/n): ").strip().lower()
    
    source_plugin = Path(__file__).resolve().parent / "antigravity-plugin"
    
    if choice == 'y':
        dest_dir = Path.home() / ".gemini" / "config" / "plugins" / "llm-walkie-talkie"
        try:
            if dest_dir.exists():
                shutil.rmtree(dest_dir)
            shutil.copytree(source_plugin, dest_dir)
            print(f"[OK] Installed plugin globally to {dest_dir}\n")
        except Exception as e:
            print(f"[FAIL] Failed to install plugin globally: {e}")
    else:
        print("Skipped plugin installation.\n")

    print("====================================================")
    print(" Setup Completed Successfully!")
    print(" Run 'walkie ask --prompt \"Hi\"' to start conversing.")
    print("====================================================")

if __name__ == "__main__":
    main()
