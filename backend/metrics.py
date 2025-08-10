import psutil
import platform
import socket
import uuid
import os
import subprocess
from datetime import datetime

def get_timestamp():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def get_cpu_metrics():
    cpu_metrics = {}

    # Read CPU core count from mounted /proc/cpuinfo
    try:
        cpuinfo_path = "/host/proc/cpuinfo"
        if os.path.exists(cpuinfo_path):
            with open(cpuinfo_path, "r") as f:
                physical_cores = set()
                total_cores = 0
                for line in f:
                    if line.startswith("processor"):
                        total_cores += 1
                    elif line.startswith("physical id"):
                        physical_cores.add(line.strip().split(":")[1].strip())
                cpu_metrics["Total Cores"] = total_cores
                cpu_metrics["Physical Cores"] = len(physical_cores)
    except Exception as e:
        cpu_metrics["Total Cores"] = "Error reading host CPU cores"
        cpu_metrics["Physical Cores"] = "Error"

    # CPU usage per core (psutil can use host mount)
    try:
        cpu_metrics["Total CPU Usage (%)"] = psutil.cpu_percent()
    except Exception as e:
        cpu_metrics["Total CPU Usage (%)"] = "Error"

    return cpu_metrics


def get_memory_metrics(proc_path="/host/proc"):
    """Get host memory metrics by reading from mounted /proc directory."""
    vm = psutil.virtual_memory()
    sm = psutil.swap_memory()

    # If running inside container, psutil will still read container's /proc
    # To read host metrics, we temporarily override /proc mountpoint
    if proc_path != "/proc":
        psutil.PROCFS_PATH = proc_path
        vm = psutil.virtual_memory()
        sm = psutil.swap_memory()
        psutil.PROCFS_PATH = "/proc"  # restore after reading

    return {
        "Total RAM (MB)": vm.total // (1024 * 1024),
        "Used RAM (MB)": vm.used // (1024 * 1024),
        "Free RAM (MB)": vm.available // (1024 * 1024),
        "RAM Usage (%)": vm.percent,
        "Swap Total (MB)": sm.total // (1024 * 1024),
        "Swap Used (MB)": sm.used // (1024 * 1024),
        "Swap Usage (%)": sm.percent
    }


def get_disk_metrics():
    total = used = free = 0

    # Read mount points from /proc/mounts (host version if mounted in container)
    with open("/proc/mounts", "r") as f:
        for line in f:
            parts = line.split()
            if len(parts) < 2:
                continue
            mount_point = parts[1]

            try:
                stats = os.statvfs(mount_point)
                mount_total = stats.f_blocks * stats.f_frsize
                mount_free = stats.f_bfree * stats.f_frsize
                mount_used = mount_total - mount_free

                total += mount_total
                used += mount_used
                free += mount_free
            except OSError:
                continue  # Ignore inaccessible mounts

    percent_used = (used / total) * 100 if total else 0

    return {
        "total_disk_space_gb": round(total / (1024 ** 3), 2),
        "used_disk_space_gb": round(used / (1024 ** 3), 2),
        "free_disk_space_gb": round(free / (1024 ** 3), 2),
        "percent_used": f"{percent_used:.2f} %"
    }

def get_network_metrics():
    stats = {}
    try:
        with open("/proc/net/dev", "r") as f:
            lines = f.readlines()

        for line in lines[2:]:  # skip headers
            parts = line.split()
            if len(parts) < 17:
                continue

            iface = parts[0].strip(":")
            stats[iface] = {
                "bytes_sent": int(parts[9]),
                "bytes_recv": int(parts[1]),
                "packets_sent": int(parts[10]),
                "packets_recv": int(parts[2]),
                "errin": int(parts[3]),
                "errout": int(parts[11]),
                "dropin": int(parts[4]),
                "dropout": int(parts[12])
            }
    except FileNotFoundError:
        stats["error"] = "/proc/net/dev not found - mount host /proc to container"
    return stats

def get_system_info():
    info = {}

    # 1. OS Info from /etc/os-release
    os_info_path = "/host/etc/os-release"
    if os.path.exists(os_info_path):
        with open(os_info_path) as f:
            for line in f:
                if line.startswith("PRETTY_NAME="):
                    info["OS"] = line.strip().split("=")[1].strip('"')
    
    # 2. Hostname
    hostname_path = "/host/etc/hostname"
    if os.path.exists(hostname_path):
        with open(hostname_path) as f:
            info["Hostname"] = f.read().strip()

    # 3. Architecture
    uname_path = "/host/proc/version"
    if os.path.exists(uname_path):
        with open(uname_path) as f:
            version_info = f.read().strip()
            info["Architecture"] = version_info.split()[-1]

    # 4. Uptime
    uptime_path = "/host/proc/uptime"
    if os.path.exists(uptime_path):
        with open(uptime_path) as f:
            uptime_seconds = float(f.read().split()[0])
            info["Uptime (sec)"] = int(uptime_seconds)

    return info
    