# from flask import Flask, jsonify
from flask import Flask, render_template_string, jsonify

from metrics import get_cpu_metrics, get_memory_metrics, get_disk_metrics, get_network_metrics, get_system_info, get_timestamp
import psycopg2
import os
import threading
import requests
import time

app = Flask(__name__)

# Read DB connection details from environment variables
DB_HOST = os.getenv("DB_HOST", "postgres")
DB_PORT = os.getenv("DB_PORT", "5432")
# DB_NAME = os.getenv("POSTGRES_DB", "kube_usecase")
DB_USER = os.getenv("POSTGRES_USER", "postgres")
DB_PASSWORD = os.getenv("POSTGRES_PASSWORD", "postgres")

HTML_TEMPLATE ="""
<!DOCTYPE html>
<html>
<head>
    <title>System Metrics</title>
    <style>
        body { font-family: Arial, sans-serif; }
        table { border-collapse: collapse; width: 60%; margin-bottom: 30px; }
        th, td { border: 1px solid #ddd; padding: 8px; }
        th { background-color: #f2f2f2; }
        h2 { margin-top: 40px; }
    </style>
</head>
<body>
    <h1>System Metrics</h1>

    {% for section, data in metrics.items() %}
        <h2>{{ section | capitalize }} Metrics</h2>
        <table>
            <tr>
                <th>Metric</th>
                <th>Value</th>
            </tr>
            {% if section == "network" %}
                {% for interface, values in data.items() %}
                    <tr>
                        <td colspan="2" style="background:#ddd;"><b>Interface: {{ interface }}</b></td>
                    </tr>
                    {% for key, value in values.items() %}
                        <tr>
                            <td>{{ key }}</td>
                            <td>{{ value }}</td>
                        </tr>
                    {% endfor %}
                {% endfor %}
            {% else %}
                {% for key, value in data.items() %}
                    <tr>
                        <td>{{ key }}</td>
                        <td>{{ value }}</td>
                    </tr>
                {% endfor %}
            {% endif %}
        </table>
    {% endfor %}
</body>
</html>
"""

def get_db_connection():
    print(DB_PASSWORD)
    print(DB_USER)
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        # dbname=DB_NAME
        user=DB_USER,
        password=DB_PASSWORD
    )

@app.route('/metrics')
def metrics():
    conn = get_db_connection()
    cursor = conn.cursor()

    result = {}

    def fetch_latest(query, keys):
        try:
            cursor.execute(query)
            row = cursor.fetchone()
            if row:
                return dict(zip(keys, row))
        except Exception as e:
            # Table might not exist
            return None
        return None

    # CPU Metrics
    cpu = fetch_latest(
        "SELECT timestamp, total_cores, physical_cores, total_cpu_usage FROM cpu_metrics ORDER BY timestamp DESC LIMIT 1",
        ["timestamp", "Total Cores", "Physical Cores", "Total CPU Usage (%)"]
    )
    if cpu:
        result["cpu"] = cpu

    # Memory Metrics
    memory = fetch_latest("""
        SELECT timestamp, total_ram_mb, used_ram_mb, free_ram_mb, ram_usage, swap_total_mb, swap_used_mb, swap_usage
        FROM memory_metrics ORDER BY timestamp DESC LIMIT 1
    """, [
        "timestamp", "Total RAM (MB)", "Used RAM (MB)", "Free RAM (MB)",
        "RAM Usage (%)", "Swap Total (MB)", "Swap Used (MB)", "Swap Usage (%)"
    ])
    if memory:
        result["memory"] = memory

    # Disk Metrics
    disk = fetch_latest("""
        SELECT timestamp, total_gb, used_gb, free_gb, percent_used
        FROM disk_metrics ORDER BY timestamp DESC LIMIT 1
    """, [
        "timestamp", "total_disk_space_gb", "used_disk_space_gb",
        "free_disk_space_gb", "percent_used"
    ])
    if disk:
        result["disk"] = disk

    # Network Metrics
    try:
        cursor.execute("""
            SELECT timestamp, interface, bytes_sent, bytes_recv, packets_sent, packets_recv, errin, errout, dropin, dropout
            FROM network_metrics ORDER BY timestamp DESC LIMIT 5
        """)
        rows = cursor.fetchall()
        network_data = {}
        for row in rows:
            network_data[row[1]] = {
                "timestamp": row[0],
                "bytes_sent": row[2],
                "bytes_recv": row[3],
                "packets_sent": row[4],
                "packets_recv": row[5],
                "errin": row[6],
                "errout": row[7],
                "dropin": row[8],
                "dropout": row[9]
            }
        if network_data:
            result["network"] = network_data
    except Exception:
        pass  # Ignore if table does not exist

    # System Info
    system = fetch_latest("""
        SELECT timestamp, os, hostname, architecture, uptime_sec
        FROM system_info ORDER BY timestamp DESC LIMIT 1
    """, [
        "timestamp", "OS", "Hostname", "Architecture", "Uptime (sec)"
    ])
    if system:
        result["system"] = system

    cursor.close()
    conn.close()

    if not result:
        return jsonify({"message": "No resources found"}), 200

    return render_template_string(HTML_TEMPLATE, metrics=result)


@app.route('/store', methods=['POST'])
def store_metrics():
    conn = get_db_connection()
    cursor = conn.cursor()

    timestamp = get_timestamp()

    # ---------------- CPU Metrics ----------------
    cpu = get_cpu_metrics()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cpu_metrics (
            id SERIAL PRIMARY KEY,
            timestamp TIMESTAMP,
            total_cores INT,
            physical_cores INT,
            total_cpu_usage FLOAT
        )
    """)
    cursor.execute("""
        INSERT INTO cpu_metrics (timestamp, total_cores, physical_cores, total_cpu_usage)
        VALUES (%s, %s, %s, %s)
    """, (timestamp, cpu.get("Total Cores"), cpu.get("Physical Cores"),
          cpu.get("Total CPU Usage (%)")))

    # ---------------- Memory Metrics ----------------
    memory = get_memory_metrics()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS memory_metrics (
            id SERIAL PRIMARY KEY,
            timestamp TIMESTAMP,
            total_ram_mb BIGINT,
            used_ram_mb BIGINT,
            free_ram_mb BIGINT,
            ram_usage FLOAT,
            swap_total_mb BIGINT,
            swap_used_mb BIGINT,
            swap_usage FLOAT
        )
    """)
    cursor.execute("""
        INSERT INTO memory_metrics (timestamp, total_ram_mb, used_ram_mb, free_ram_mb, ram_usage, swap_total_mb, swap_used_mb, swap_usage)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    """, (timestamp, memory.get("Total RAM (MB)"), memory.get("Used RAM (MB)"),
          memory.get("Free RAM (MB)"), memory.get("RAM Usage (%)"),
          memory.get("Swap Total (MB)"), memory.get("Swap Used (MB)"), memory.get("Swap Usage (%)")))

    # ---------------- Disk Metrics ----------------
    disk = get_disk_metrics()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS disk_metrics (
            id SERIAL PRIMARY KEY,
            timestamp TIMESTAMP,
            total_gb FLOAT,
            used_gb FLOAT,
            free_gb FLOAT,
            percent_used TEXT
        )
    """)
    cursor.execute("""
        INSERT INTO disk_metrics (timestamp, total_gb, used_gb, free_gb, percent_used)
        VALUES (%s, %s, %s, %s, %s)
    """, (timestamp, disk.get("total_disk_space_gb"), disk.get("used_disk_space_gb"),
          disk.get("free_disk_space_gb"), disk.get("percent_used")))

    # ---------------- Network Metrics ----------------
    network = get_network_metrics()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS network_metrics (
            id SERIAL PRIMARY KEY,
            timestamp TIMESTAMP,
            interface TEXT,
            bytes_sent BIGINT,
            bytes_recv BIGINT,
            packets_sent BIGINT,
            packets_recv BIGINT,
            errin BIGINT,
            errout BIGINT,
            dropin BIGINT,
            dropout BIGINT
        )
    """)
    for iface, stats in network.items():
        if iface == "error":
            continue
        cursor.execute("""
            INSERT INTO network_metrics (timestamp, interface, bytes_sent, bytes_recv, packets_sent, packets_recv, errin, errout, dropin, dropout)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (timestamp, iface, stats["bytes_sent"], stats["bytes_recv"],
              stats["packets_sent"], stats["packets_recv"],
              stats["errin"], stats["errout"], stats["dropin"], stats["dropout"]))

    # ---------------- System Info ----------------
    system = get_system_info()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS system_info (
            id SERIAL PRIMARY KEY,
            timestamp TIMESTAMP,
            os TEXT,
            hostname TEXT,
            architecture TEXT,
            uptime_sec BIGINT
        )
    """)
    cursor.execute("""
        INSERT INTO system_info (timestamp, os, hostname, architecture, uptime_sec)
        VALUES (%s, %s, %s, %s, %s)
    """, (timestamp, system.get("OS"), system.get("Hostname"),
          system.get("Architecture"), system.get("Uptime (sec)")))

    # Commit changes
    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({"status": "success", "message": "Metrics stored in PostgreSQL."}), 201

# def background_metrics_pusher():
#     while True:
#         try:
#             print(DB_USER)
#             print(DB_PASSWORD)
#             requests.post("http://localhost:5000/store")
#             print("Metrics pushed successfully")
#         except Exception as e:
#             print(f"Failed to push metrics: {e}")
#         time.sleep(300)  # 5 minutes

if __name__ == '__main__':
    # threading.Thread(target=background_metrics_pusher, daemon=True).start()
    app.run(host='0.0.0.0', port=5000)
