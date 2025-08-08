import psutil
import platform
import time

def get_metrics():
    return {
        "os_info": {
            "system": platform.system(),
            "node": platform.node(),
            "release": platform.release(),
            "version": platform.version(),
            "machine": platform.machine(),
            "processor": platform.processor()
        },
        "uptime": time.time() - psutil.boot_time(),
        "cpu_info": {
            "physical_cores": psutil.cpu_count(logical=False),
            "total_cores": psutil.cpu_count(logical=True),
            "cpu_usage_percent": psutil.cpu_percent(interval=1)
        },
        "memory_info": dict(psutil.virtual_memory()._asdict()),
        "disk_info": [dict(part._asdict()) for part in psutil.disk_partitions()],
        "network_info": psutil.net_io_counters(pernic=False)._asdict(),
        "load_average": psutil.getloadavg(),
        "top_processes": sorted([
            {
                "pid": p.pid,
                "name": p.name(),
                "cpu_percent": p.cpu_percent(),
                "memory_percent": p.memory_percent()
            }
            for p in psutil.process_iter(['pid', 'name'])
        ], key=lambda x: x["cpu_percent"], reverse=True)[:5]
    }
