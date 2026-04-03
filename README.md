# cpu-power-manager
Linux CPU Frequency and Power Profile Management
Standalone Linux Application (GUI)

A user-friendly GUI application for managing CPU governors and system power profiles on Linux systems.

**Requirements:
- Linux system with CPU frequency scaling support
- tkinter (usually pre-installed)
- powerprofilesctl (for power profile management on systemd systems)
- PyGObject (for powerprofilesctl): pip install PyGObject
- root privileges for CPU frequency and power profile changes (handled via sudo/pkexec)
- **Systemd** (for power profile management)
- **X11 or Wayland** display server
  
**Usage:
python cpu_power_manager.py

CPU governor management works on most Linux systems with cpufreq support (on Arch with 'cpupower' typically).

**Features

### CPU Governor Management
- View current CPU frequencies and governors
- Change governor for individual CPUs
- Set governor for all CPUs simultaneously
- Real-time frequency monitoring (via 'Refresh')
