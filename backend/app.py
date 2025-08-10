from flask import Flask, jsonify
from metrics import get_cpu_metrics, get_memory_metrics, get_disk_metrics, get_network_metrics, get_process_metrics, get_system_info, get_timestamp
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

    # CPU Metrics
    cursor.execute("SELECT timestamp, total_cores, physical_cores, total_cpu_usage FROM cpu_metrics ORDER BY timestamp DESC LIMIT 1")
    row = cursor.fetchone()
    if row:
        result["cpu"] = {
            "timestamp": row[0],
            "Total Cores": row[1],
            "Physical Cores": row[2],
            "Total CPU Usage (%)": row[3]
        }

    # Memory Metrics
    cursor.execute("""
        SELECT timestamp, total_ram_mb, used_ram_mb, free_ram_mb, ram_usage, swap_total_mb, swap_used_mb, swap_usage
        FROM memory_metrics ORDER BY timestamp DESC LIMIT 1
    """)
    row = cursor.fetchone()
    if row:
        result["memory"] = {
            "timestamp": row[0],
            "Total RAM (MB)": row[1],
            "Used RAM (MB)": row[2],
            "Free RAM (MB)": row[3],
            "RAM Usage (%)": row[4],
            "Swap Total (MB)": row[5],
            "Swap Used (MB)": row[6],
            "Swap Usage (%)": row[7]
        }

    # Disk Metrics
    cursor.execute("""
        SELECT timestamp, total_gb, used_gb, free_gb, percent_used
        FROM disk_metrics ORDER BY timestamp DESC LIMIT 1
    """)
    row = cursor.fetchone()
    if row:
        result["disk"] = {
            "timestamp": row[0],
            "total_disk_space_gb": row[1],
            "used_disk_space_gb": row[2],
            "free_disk_space_gb": row[3],
            "percent_used": row[4]
        }

    # Network Metrics (get latest per interface)
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

    # System Info
    cursor.execute("""
        SELECT timestamp, os, hostname, architecture, uptime_sec
        FROM system_info ORDER BY timestamp DESC LIMIT 1
    """)
    row = cursor.fetchone()
    if row:
        result["system"] = {
            "timestamp": row[0],
            "OS": row[1],
            "Hostname": row[2],
            "Architecture": row[3],
            "Uptime (sec)": row[4]
        }

    cursor.close()
    conn.close()

    return jsonify(result)


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
            total_cpu_usage FLOAT,
        )
    """)
    cursor.execute("""
        INSERT INTO cpu_metrics (timestamp, total_cores, physical_cores, total_cpu_usage)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
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
            percent_used FLOAT
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
