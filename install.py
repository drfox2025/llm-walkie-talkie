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

    # Step 3: Install Antigravity Plugin & IDE Extension
    print("\n[3/3] Installing Antigravity Plugin & IDE Extension...")
    choice = input("Do you want to install LWT as an Antigravity Plugin globally & install the IDE extension? (y/n): ").strip().lower()
    
    source_plugin = Path(__file__).resolve().parent / "antigravity-plugin"
    
    if choice == 'y':
        # 3.1 Install plugin to .gemini/config/plugins
        dest_dir = Path.home() / ".gemini" / "config" / "plugins" / "llm-walkie-talkie"
        try:
            if dest_dir.exists():
                shutil.rmtree(dest_dir)
            shutil.copytree(source_plugin, dest_dir)
            print(f"[OK] Installed plugin globally to {dest_dir}")
        except Exception as e:
            print(f"[FAIL] Failed to install plugin globally: {e}")

        # 3.2 Install VSIX to Antigravity IDE
        print("Installing IDE Extension (.vsix) to Antigravity IDE...")
        # Find latest VSIX
        vsix_files = list(source_plugin.glob("*.vsix"))
        if vsix_files:
            # Sort by name/version to get the latest VSIX
            vsix_files.sort()
            latest_vsix = vsix_files[-1]
            
            # Find antigravity-ide CLI
            cli_path = None
            for p in [
                shutil.which("antigravity-ide"),
                shutil.which("antigravity-ide.cmd"),
                Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Antigravity IDE" / "bin" / "antigravity-ide.cmd",
                Path.home() / "AppData" / "Local" / "Programs" / "Antigravity IDE" / "bin" / "antigravity-ide.cmd"
            ]:
                if p and Path(p).exists():
                    cli_path = Path(p)
                    break
            
            if cli_path:
                print(f"Found Antigravity IDE CLI at: {cli_path}")
                try:
                    subprocess.run([str(cli_path), "--install-extension", str(latest_vsix)], check=True)
                    print(f"[OK] Installed IDE extension {latest_vsix.name} successfully!\n")
                except subprocess.CalledProcessError as e:
                    print(f"[FAIL] Failed to run extension installer: {e}\n")
            else:
                print(f"[WARNING] Antigravity IDE CLI not found. Please install the extension manually by running:")
                print(f"  antigravity-ide --install-extension {latest_vsix}\n")
        else:
            print("[FAIL] No .vsix file found in antigravity-plugin folder.\n")
    else:
        print("Skipped plugin and extension installation.\n")

    print("====================================================")
    print(" Setup Completed Successfully!")
    print(" Quick start commands:")
    print("   walkie quickstart                     # Zero-friction setup (30s)")
    print("   walkie discover --coding-only         # See all free coding models")
    print('   walkie ask --prompt "Hello, world!"   # Start a conversation')
    print("====================================================")

if __name__ == "__main__":
    main()
