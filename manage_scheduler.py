#!/usr/bin/env python3
"""
RSS Scheduler Management Script

Simple script to manage the RSS scheduler with various options for handling
laptop sleep/wake scenarios.
"""

import argparse
import sys
import subprocess
import time
import signal
import os
from datetime import datetime
from pathlib import Path

def run_in_background():
    """Run the scheduler as a background process with nohup"""
    cmd = ["nohup", "python", "-m", "src.core.scheduler"]
    
    print("🚀 Starting RSS scheduler in background...")
    
    try:
        # Start the process
        with open("scheduler_bg.log", "w") as log_file:
            process = subprocess.Popen(
                cmd,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                preexec_fn=os.setsid  # Create new session
            )
        
        # Save PID
        with open("scheduler.pid", "w") as pid_file:
            pid_file.write(str(process.pid))
        
        print(f"✅ Scheduler started with PID: {process.pid}")
        print(f"📝 Logs: scheduler_bg.log")
        print(f"🛑 To stop: python manage_scheduler.py --stop")
        
        return True
        
    except Exception as e:
        print(f"❌ Failed to start scheduler: {e}")
        return False

def stop_background():
    """Stop the background scheduler process"""
    pid_file = Path("scheduler.pid")
    
    if not pid_file.exists():
        print("❌ No PID file found. Scheduler may not be running.")
        return False
    
    try:
        with open(pid_file, "r") as f:
            pid = int(f.read().strip())
        
        print(f"🛑 Stopping scheduler (PID: {pid})...")
        
        # Try graceful shutdown first
        os.kill(pid, signal.SIGTERM)
        time.sleep(2)
        
        # Check if still running
        try:
            os.kill(pid, 0)  # Just check if process exists
            print("⏰ Waiting for graceful shutdown...")
            time.sleep(3)
            
            # Force kill if still running
            try:
                os.kill(pid, 0)
                os.kill(pid, signal.SIGKILL)
                print("💀 Force killed scheduler")
            except ProcessLookupError:
                pass  # Process already terminated
                
        except ProcessLookupError:
            pass  # Process already terminated
        
        # Remove PID file
        pid_file.unlink()
        print("✅ Scheduler stopped successfully")
        return True
        
    except Exception as e:
        print(f"❌ Error stopping scheduler: {e}")
        return False

def check_status():
    """Check if the scheduler is running"""
    pid_file = Path("scheduler.pid")
    
    if not pid_file.exists():
        print("❌ Scheduler is not running (no PID file)")
        return False
    
    try:
        with open(pid_file, "r") as f:
            pid = int(f.read().strip())
        
        # Check if process is still running
        try:
            os.kill(pid, 0)
            print(f"✅ Scheduler is running (PID: {pid})")
            
            # Show recent log entries
            log_file = Path("scheduler_bg.log")
            if log_file.exists():
                print("\n📝 Recent log entries:")
                with open(log_file, "r") as f:
                    lines = f.readlines()
                    for line in lines[-5:]:  # Last 5 lines
                        print(f"   {line.strip()}")
            
            return True
            
        except ProcessLookupError:
            print(f"❌ Scheduler process {pid} not found (may have crashed)")
            pid_file.unlink()  # Clean up stale PID file
            return False
            
    except Exception as e:
        print(f"❌ Error checking status: {e}")
        return False

def run_interactive():
    """Run the scheduler interactively (foreground)"""
    print("🚀 Starting RSS scheduler in interactive mode...")
    print("💡 This will run in the foreground. Press Ctrl+C to stop.")
    
    try:
        from src.core.scheduler import main
        main()
    except KeyboardInterrupt:
        print("\n🛑 Scheduler stopped by user")
    except Exception as e:
        print(f"❌ Scheduler error: {e}")

def setup_service():
    """Setup systemd service for automatic startup"""
    service_file = Path("rss-scheduler.service")
    
    if not service_file.exists():
        print("❌ Service file not found. Run this from the project directory.")
        return False
    
    try:
        # Copy service file
        cmd = [
            "sudo", "cp", 
            str(service_file), 
            f"/etc/systemd/system/rss-scheduler@{os.getenv('USER')}.service"
        ]
        subprocess.run(cmd, check=True)
        
        # Reload systemd
        subprocess.run(["sudo", "systemctl", "daemon-reload"], check=True)
        
        print("✅ Service installed successfully")
        print(f"🔧 Enable with: sudo systemctl enable rss-scheduler@{os.getenv('USER')}")
        print(f"🚀 Start with: sudo systemctl start rss-scheduler@{os.getenv('USER')}")
        print(f"📊 Status with: sudo systemctl status rss-scheduler@{os.getenv('USER')}")
        
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to setup service: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="Manage RSS Awards Scheduler")
    
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--start", action="store_true", help="Start scheduler in background")
    group.add_argument("--stop", action="store_true", help="Stop background scheduler")
    group.add_argument("--status", action="store_true", help="Check scheduler status")
    group.add_argument("--interactive", action="store_true", help="Run scheduler interactively")
    group.add_argument("--setup-service", action="store_true", help="Setup systemd service")
    
    args = parser.parse_args()
    
    print("RSS Awards Scheduler Manager")
    print("=" * 40)
    
    if args.start:
        success = run_in_background()
        sys.exit(0 if success else 1)
    elif args.stop:
        success = stop_background()
        sys.exit(0 if success else 1)
    elif args.status:
        success = check_status()
        sys.exit(0 if success else 1)
    elif args.interactive:
        run_interactive()
    elif args.setup_service:
        success = setup_service()
        sys.exit(0 if success else 1)

if __name__ == "__main__":
    main() 