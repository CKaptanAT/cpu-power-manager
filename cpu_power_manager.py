#!/usr/bin/env python3
"""
CPU Power Manager - Linux CPU Frequency and Power Profile Manager

Requirements:
- Linux system with CPU frequency scaling support
- tkinter (usually pre-installed)
- powerprofilesctl (for power profile management on systemd systems)
- PyGObject (for powerprofilesctl): pip install PyGObject
-root privileges for CPU frequency and power profile changes (handled via sudo/pkexec)

Usage:
python cpu_power_manager.py

Note: Power profile management requires systemd and powerprofilesctl.
CPU governor management works on most Linux systems with cpufreq support (on Arch with 'cpupower' typically).
"""

import os
import tkinter as tk
from tkinter import ttk, messagebox
import subprocess
import shutil
import sys
import threading

# Global variable to track if running as root
is_root = os.geteuid() == 0 if hasattr(os, 'geteuid') else False

def run_with_sudo(command):
    """
    Run a command with sudo/pkexec if not already root.
    Returns (success: bool, output: str, error: str)
    """
    try:
        if is_root:
            # Already root, run directly
            result = subprocess.run(
                command if isinstance(command, list) else command.split(),
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0, result.stdout, result.stderr
        else:
            # Not root, use pkexec or sudo
            if shutil.which("pkexec"):
                # Prefer pkexec (handles password gracefully via system dialog)
                result = subprocess.run(
                    ["pkexec"] + (command if isinstance(command, list) else command.split()),
                    capture_output=True,
                    text=True,
                    timeout=15
                )
            else:
                # Fall back to sudo
                result = subprocess.run(
                    ["sudo"] + (command if isinstance(command, list) else command.split()),
                    capture_output=True,
                    text=True,
                    timeout=15
                )
            
            if result.returncode != 0:
                error_msg = result.stderr or result.stdout or "Command failed"
                # Check for auth failures
                if "not authorized" in error_msg.lower() or "denied" in error_msg.lower():
                    return False, "", "Authentication failed. Please check your password."
                return False, "", error_msg
            return True, result.stdout, ""
    except subprocess.TimeoutExpired:
        return False, "", "Command timed out"
    except Exception as e:
        return False, "", str(e)

def check_root_access():
    """Check and warn if not running as root"""
    if not is_root:
        response = messagebox.showwarning(
            "Privilege Notice",
            "This application requires elevated privileges for CPU frequency control.\n\n"
            "You will be prompted for your password when making changes.\n\n"
            "Continue anyway?",
            type=messagebox.OKCANCEL
        )
        return response == messagebox.OK
    return True

def get_cpu_info():
    """Get CPU information from sysfs"""
    cpu_info = []
    try:
        cpu_count = int(subprocess.check_output("nproc", shell=True, timeout=5).decode().strip())
    except:
        cpu_count = 1  # fallback

    for cpu in range(cpu_count):
        base = f'/sys/devices/system/cpu/cpu{cpu}/cpufreq/'
        try:
            cur_freq = int(open(base + 'scaling_cur_freq').read().strip()) / 1000
            max_freq = int(open(base + 'scaling_max_freq').read().strip()) / 1000
            governor = open(base + 'scaling_governor').read().strip()
            available_governors = open(base + 'scaling_available_governors').read().strip().split()
        except FileNotFoundError:
            continue  # skip if no cpufreq for this cpu
        cpu_info.append({
            'cpu': cpu,
            'cur_freq': cur_freq,
            'max_freq': max_freq,
            'governor': governor,
            'available_governors': available_governors
        })
    return cpu_info

def set_all_governors(governor, cpu_list):
    """Set governor for all CPUs in one operation (with sudo if needed)"""
    if is_root:
        # Direct write if already root
        failed = []
        for cpu in cpu_list:
            base = f'/sys/devices/system/cpu/cpu{cpu}/cpufreq/'
            try:
                with open(base + 'scaling_governor', 'w') as f:
                    f.write(governor)
            except Exception as e:
                failed.append((cpu, str(e)))
        return failed
    else:
        # Use a single sh command with sudo/pkexec to set all governors
        commands = []
        for cpu in cpu_list:
            base = f'/sys/devices/system/cpu/cpu{cpu}/cpufreq/'
            commands.append(f"echo {governor} > {base}scaling_governor")
        
        # Join all commands with && so they run sequentially in one sudo session
        compound_command = " && ".join(commands)
        success, _, error = run_with_sudo(["sh", "-c", compound_command])
        if success:
            return []
        else:
            # If the compound command fails, we don't know which specific CPU failed
            # Return a generic error for all CPUs
            return [(cpu, f"Failed to set governor: {error}") for cpu in cpu_list]

def refresh_info():
    """Refresh CPU information display"""
    for row in tree.get_children():
        tree.delete(row)
    cpu_info = get_cpu_info()
    for info in cpu_info:
        tree.insert('', 'end', values=(info['cpu'], f"{info['cur_freq']:.0f} MHz", f"{info['max_freq']:.0f} MHz", info['governor']))

def on_set_governor():
    """Handle individual CPU governor setting"""
    selected = tree.selection()
    if not selected:
        messagebox.showwarning("Warning", "Select a CPU first")
        return
    item = tree.item(selected[0])
    cpu = item['values'][0]
    cpu_info = get_cpu_info()
    info = next((i for i in cpu_info if i['cpu'] == cpu), None)
    if info:
        # Simple dialog to choose governor
        gov_window = tk.Toplevel(root)
        gov_window.title(f"Set Governor for CPU {cpu}")
        tk.Label(gov_window, text="Choose Governor:").pack(pady=5)
        gov_var = tk.StringVar(value=info['governor'])
        for gov in info['available_governors']:
            tk.Radiobutton(gov_window, text=gov, variable=gov_var, value=gov).pack()
        
        def apply_governor():
            success, msg = set_governor(cpu, gov_var.get())
            gov_window.destroy()
            if success:
                messagebox.showinfo("Success", msg)
                refresh_info()
            else:
                messagebox.showerror("Error", msg)
        
        tk.Button(gov_window, text="Set", command=apply_governor).pack(pady=5)

def on_set_all_governor():
    """Handle setting governor for all CPUs"""
    cpu_info = get_cpu_info()
    if not cpu_info:
        messagebox.showwarning("Warning", "No CPUs detected")
        return

    all_governors = sorted({gov for info in cpu_info for gov in info['available_governors']})
    if not all_governors:
        messagebox.showwarning("Warning", "No governors available")
        return

    gov_window = tk.Toplevel(root)
    gov_window.title("Set Governor for All CPUs")
    tk.Label(gov_window, text="Choose Governor for all CPUs:").pack(pady=5)
    gov_var = tk.StringVar(value=cpu_info[0]['governor'])

    for gov in all_governors:
        tk.Radiobutton(gov_window, text=gov, variable=gov_var, value=gov).pack()

    def apply_all():
        chosen = gov_var.get()
        cpu_list = [info['cpu'] for info in cpu_info]
        failed = set_all_governors(chosen, cpu_list)
        gov_window.destroy()
        refresh_info()
        if failed:
            error_details = "\n".join([f"CPU {cpu}: {msg}" for cpu, msg in failed])
            messagebox.showerror("Error", f"Failed to set governor for some CPUs:\n{error_details}")
        else:
            messagebox.showinfo("Success", f"Governor set to '{chosen}' for all CPUs")

    tk.Button(gov_window, text="Set All", command=apply_all).pack(pady=5)

# ========== POWER PROFILE MANAGEMENT ==========

def powerprofilesctl_working():
    """Test if powerprofilesctl actually works"""
    if not shutil.which("powerprofilesctl"):
        return False
    try:
        result = subprocess.run(
            ["powerprofilesctl", "list"],
            capture_output=True,
            text=True,
            timeout=2
        )
        return result.returncode == 0
    except Exception:
        return False

def get_power_profile():
    """Get current power profile"""
    try:
        out = subprocess.check_output(
            ["powerprofilesctl", "get"],
            stderr=subprocess.STDOUT,
            text=True,
            timeout=2
        ).strip()
        return out or "Unknown"
    except subprocess.CalledProcessError as e:
        return f"Error: {e}"
    except Exception as e:
        return f"Unavailable"

def get_available_power_profiles():
    """Get available power profiles"""
    try:
        out = subprocess.check_output(
            ["powerprofilesctl", "list"],
            stderr=subprocess.STDOUT,
            text=True,
            timeout=2
        )
    except Exception:
        return []

    profiles = []
    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        # Remove asterisk if present and get profile name before colon
        if line.startswith("*"):
            line = line[1:].strip()
        if ":" in line:
            profile_name = line.split(":")[0].strip()
            if profile_name and profile_name not in ["CpuDriver", "Degraded", "PlatformDriver"]:
                profiles.append(profile_name)
    return profiles

def set_power_profile(profile):
    """Set power profile (with sudo if needed)"""
    success, _, error = run_with_sudo(["powerprofilesctl", "set", profile])
    if success:
        messagebox.showinfo("Success", f"Power profile set to {profile}")
        refresh_power()
    else:
        messagebox.showerror("Error", f"Failed to set power profile: {error}")

def refresh_power():
    """Refresh power profile display"""
    if powerprofilesctl_working():
        current = get_power_profile()
        profile_label.config(text=f"Current Power Profile: {current}")
    else:
        profile_label.config(text="Power profiles unavailable (powerprofilesctl not working)")

def on_set_power():
    """Open dialog to set power profile"""
    profiles = get_available_power_profiles()
    if not profiles:
        messagebox.showerror("Error", "No power profiles available")
        return

    pow_window = tk.Toplevel(root)
    pow_window.title("Set Power Profile")
    tk.Label(pow_window, text="Choose Power Profile:").pack(pady=5)

    current = get_power_profile()
    prof_var = tk.StringVar(value=profiles[0])

    for prof in profiles:
        tk.Radiobutton(pow_window, text=prof, variable=prof_var, value=prof).pack()

    tk.Button(pow_window, text="Set", command=lambda: set_power_profile(prof_var.get())).pack(pady=5)

def main():
    """Main application"""
    global root, tree, refresh_button, set_button, set_all_button, power_frame, profile_label

    # Check if running on Linux
    if os.name != 'posix':
        print("This application is designed for Linux systems only.")
        sys.exit(1)

    # Check for root/sudo access
    if not check_root_access():
        sys.exit(0)

    root = tk.Tk()
    root.title("CPU Power Manager")
    root.geometry("600x400")

    # Status frame
    status_frame = tk.Frame(root, bg="lightblue", height=30)
    status_frame.pack(fill=tk.X)
    if is_root:
        status_label = tk.Label(status_frame, text="Running as: ROOT", bg="lightblue", fg="green", font=("Arial", 9, "bold"))
    else:
        status_label = tk.Label(status_frame, text="Running as: Regular User (using sudo/pkexec)", bg="lightblue", fg="orange", font=("Arial", 9, "bold"))
    status_label.pack(side=tk.LEFT, padx=5, pady=3)

    # CPU Information Section
    info_label = tk.Label(root, text="CPU Frequency Information", font=("Arial", 10, "bold"))
    info_label.pack()

    tree = ttk.Treeview(root, columns=('CPU', 'Current Freq', 'Max Freq', 'Governor'), show='headings', height=8)
    tree.heading('CPU', text='CPU')
    tree.heading('Current Freq', text='Current Freq (MHz)')
    tree.heading('Max Freq', text='Max Freq (MHz)')
    tree.heading('Governor', text='Governor')
    tree.column('CPU', width=60)
    tree.column('Current Freq', width=130)
    tree.column('Max Freq', width=130)
    tree.column('Governor', width=130)
    tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    refresh_button = tk.Button(root, text="Refresh", command=refresh_info, bg="lightgreen")
    refresh_button.pack(pady=2)

    set_button = tk.Button(root, text="Set Governor for Selected CPU", command=on_set_governor, bg="lightyellow")
    set_button.pack(pady=2)

    refresh_info()

    set_all_button = tk.Button(root, text="Set Governor for All CPUs", command=on_set_all_governor, bg="lightcyan")
    set_all_button.pack(pady=2)

    # Power Profile Section
    power_sep = ttk.Separator(root, orient='horizontal')
    power_sep.pack(fill=tk.X, pady=5)

    power_label = tk.Label(root, text="Power Profile Management", font=("Arial", 10, "bold"))
    power_label.pack()

    power_frame = tk.Frame(root)
    power_frame.pack()

    profile_label = tk.Label(power_frame, text="Checking power profiles...", justify=tk.CENTER)
    profile_label.pack(pady=5)

    if powerprofilesctl_working():
        set_power_button = tk.Button(power_frame, text="Set Power Profile", command=on_set_power, bg="lightcoral")
        set_power_button.pack(pady=5)
        refresh_power()
    else:
        profile_label.config(text="Power profiles unavailable\nRequires: systemd + powerprofilesctl + PyGObject")
        disabled_button = tk.Button(
            power_frame,
            text="Set Power Profile (Unavailable)",
            state=tk.DISABLED
        )
        disabled_button.pack(pady=5)

    root.mainloop()

if __name__ == "__main__":
    main()
