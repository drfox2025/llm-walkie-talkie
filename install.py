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

    # Step 3: Install Antigravity Custom Skill
    print("\n[3/3] Installing Antigravity Custom Skill...")
    choice = input("Do you want to install the 'ai-consult' skill globally for all workspaces? (y/n): ").strip().lower()
    
    source_skill = Path(__file__).resolve().parent / ".agents" / "skills" / "ai_consult"
    
    if choice == 'y':
        dest_dir = Path.home() / ".gemini" / "config" / "skills" / "ai_consult"
        try:
            dest_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_skill / "SKILL.md", dest_dir / "SKILL.md")
            print(f"[OK] Installed globally to {dest_dir}\n")
        except Exception as e:
            print(f"[FAIL] Failed to install globally: {e}")
    else:
        workspace_path = input("Enter the absolute path of your active project workspace: ").strip()
        if workspace_path:
            dest_dir = Path(workspace_path) / ".agents" / "skills" / "ai_consult"
            try:
                dest_dir.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source_skill / "SKILL.md", dest_dir / "SKILL.md")
                print(f"[OK] Installed to workspace at {dest_dir}\n")
            except Exception as e:
                print(f"[FAIL] Failed to install to workspace: {e}")
        else:
            print("Skipped skill installation.\n")

    print("====================================================")
    print(" Setup Completed Successfully!")
    print(" Run 'walkie ask --prompt \"Hi\"' to start conversing.")
    print("====================================================")

if __name__ == "__main__":
    main()
