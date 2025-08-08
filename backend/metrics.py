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
    return {
        "Total Cores": psutil.cpu_count(logical=True),
        "Physical Cores": psutil.cpu_count(logical=False),
        "CPU Usage Per Core (%)": psutil.cpu_percent(percpu=True),
        "Total CPU Usage (%)": psutil.cpu_percent(),
        "Load Average (1m,5m,15m)": os.getloadavg() if hasattr(os, 'getloadavg') else "N/A",
        "CPU Stats": psutil.cpu_stats()._asdict()
    }

def get_memory_metrics():
    vm = psutil.virtual_memory()
    sm = psutil.swap_memory()
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
    for part in psutil.disk_partitions():
        try:
            usage = psutil.disk_usage(part.mountpoint)
            total += usage.total
            used += usage.used
            free += usage.free
        except PermissionError:
            continue

    percent_used = (used / total) * 100 if total else 0

    return {
        "total_disk_space_gb": round(total / (1024 ** 3), 2),
        "used_disk_space_gb": round(used / (1024 ** 3), 2),
        "free_disk_space_gb": round(free / (1024 ** 3), 2),
        "percent_used": f"{percent_used:.2f} %"
    }

def get_network_metrics():
    return psutil.net_io_counters(pernic=False)._asdict()


def get_process_metrics():
    processes = []
    for proc in psutil.process_iter(['pid', 'name', 'username', 'cpu_percent', 'memory_percent']):
        try:
            processes.append(proc.info)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    zombie_procs = [p.info for p in psutil.process_iter(['status']) if p.info['status'] == psutil.STATUS_ZOMBIE]
    return {
        "Total Processes": len(processes),
        "Zombie Processes": len(zombie_procs),
        "Top 5 Processes (by CPU)": sorted(processes, key=lambda p: p['cpu_percent'], reverse=True)[:5]
    }

def get_system_info():
    return {
        "OS": platform.system(),
        "OS Version": platform.version(),
        "Hostname": socket.gethostname(),
        "IP Address": socket.gethostbyname(socket.gethostname()),
        "Architecture": platform.machine(),
        "Uptime (sec)": int((datetime.now() - datetime.fromtimestamp(psutil.boot_time())).total_seconds()),
        "Logged In Users": len(psutil.users())
    }
