import subprocess
import os
import sys
import time

def check_for_updates():
    """Check for git updates and pull if available."""
    try:
        print("🔍 Checking for updates...")
        # Fetch latest changes
        subprocess.run(["git", "fetch"], check=True, capture_output=True)
        
        # Check if behind
        status = subprocess.run(
            ["git", "status", "-uno"], 
            check=True, 
            capture_output=True, 
            text=True
        )
        
        if "Your branch is behind" in status.stdout:
            print("⬇️ Update available! Pulling changes...")
            subprocess.run(["git", "pull"], check=True)
            print("✅ Updated successfully!")
            return True
        else:
            print("✅ Already up to date.")
            return False
            
    except Exception as e:
        print(f"⚠️ Update check failed: {e}")
        return False

def start_bot():
    """Start the Gena bot."""
    print("🚀 Starting Gena Bot...")
    try:
        # Set PYTHONPATH to include src directory
        env = os.environ.copy()
        src_path = os.path.join(os.getcwd(), "src")
        env["PYTHONPATH"] = f"{src_path}:{env.get('PYTHONPATH', '')}"
        
        # Run the bot
        subprocess.run([sys.executable, "src/telebot.py"], env=env)
    except KeyboardInterrupt:
        print("\n👋 Bot stopped.")
    except Exception as e:
        print(f"❌ Error running bot: {e}")

if __name__ == "__main__":
    if check_for_updates():
        print("🔄 Restarting script to apply updates...")
        # Re-run this script to ensure new code is used
        os.execv(sys.executable, [sys.executable] + sys.argv)
    else:
        start_bot()
