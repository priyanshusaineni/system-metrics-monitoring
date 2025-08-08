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
    cursor.execute("SELECT * FROM cpu_metrics ORDER BY timestamp DESC LIMIT 1")
    row = cursor.fetchone()
    if row:
        result["cpu"] = {
            "timestamp": row[0],
            "Total Cores": row[1],
            "Physical Cores": row[2],
            "Total CPU Usage (%)": row[3],
            "Load Average (1m,5m,15m)": row[4],
        }

    # Memory Metrics
    cursor.execute("SELECT * FROM memory_metrics ORDER BY timestamp DESC LIMIT 1")
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
            "Swap Usage (%)": row[7],
        }

    # Disk Metrics
    cursor.execute("SELECT * FROM disk_metrics ORDER BY timestamp DESC LIMIT 1")
    row = cursor.fetchone()
    if row:
        result["disk"] = {
            "timestamp": row[0],
            "total_disk_space_gb": row[1],
            "used_disk_space_gb": row[2],
            "free_disk_space_gb": row[3],
            "percent_used": row[4],
        }

    # Network Metrics
    cursor.execute("SELECT * FROM network_metrics ORDER BY timestamp DESC LIMIT 1")
    row = cursor.fetchone()
    if row:
        result["network"] = {
            "timestamp": row[0],
            "bytes_sent": row[1],
            "bytes_recv": row[2],
            "packets_sent": row[3],
            "packets_recv": row[4],
            "errin": row[5],
            "errout": row[6],
            "dropin": row[7],
            "dropout": row[8],
        }

    # Process Metrics
    cursor.execute("SELECT * FROM process_metrics ORDER BY timestamp DESC LIMIT 1")
    row = cursor.fetchone()
    if row:
        result["process"] = {
            "timestamp": row[0],
            "Total Processes": row[1],
            "Zombie Processes": row[2],
            "Top 5 Processes (by CPU)": row[3],
        }

    # System Info
    cursor.execute("SELECT * FROM system_info ORDER BY timestamp DESC LIMIT 1")
    row = cursor.fetchone()
    if row:
        result["system"] = {
            "timestamp": row[0],
            "OS": row[1],
            "OS Version": row[2],
            "Hostname": row[3],
            "IP Address": row[4],
            "Architecture": row[5],
            "Uptime (sec)": row[6],
            "Logged In Users": row[7],
        }

    cursor.close()
    conn.close()

    return jsonify(result)

@app.route('/store', methods=['POST'])
def store_metrics():
    conn = get_db_connection()
    cursor = conn.cursor()

    timestamp = get_timestamp()
    
    # CPU Metrics
    cpu = get_cpu_metrics()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cpu_metrics (
            timestamp TEXT,
            total_cores INT,
            physical_cores INT,
            total_cpu_usage FLOAT,
            load_avg TEXT
        )
    """)
    cursor.execute("""
        INSERT INTO cpu_metrics (timestamp, total_cores, physical_cores, total_cpu_usage, load_avg)
        VALUES (%s, %s, %s, %s, %s)
    """, (timestamp, cpu["Total Cores"], cpu["Physical Cores"], cpu["Total CPU Usage (%)"], str(cpu["Load Average (1m,5m,15m)"])))

    # Memory Metrics
    memory = get_memory_metrics()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS memory_metrics (
            timestamp TEXT,
            total_ram_mb INT,
            used_ram_mb INT,
            free_ram_mb INT,
            ram_usage FLOAT,
            swap_total_mb INT,
            swap_used_mb INT,
            swap_usage FLOAT
        )
    """)
    cursor.execute("""
        INSERT INTO memory_metrics (timestamp, total_ram_mb, used_ram_mb, free_ram_mb, ram_usage, swap_total_mb, swap_used_mb, swap_usage)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    """, (timestamp, memory["Total RAM (MB)"], memory["Used RAM (MB)"], memory["Free RAM (MB)"], memory["RAM Usage (%)"],
          memory["Swap Total (MB)"], memory["Swap Used (MB)"], memory["Swap Usage (%)"]))

    # Disk Metrics
    disk = get_disk_metrics()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS disk_metrics (
            timestamp TEXT,
            total_gb FLOAT,
            used_gb FLOAT,
            free_gb FLOAT,
            percent_used TEXT
        )
    """)
    cursor.execute("""
        INSERT INTO disk_metrics (timestamp, total_gb, used_gb, free_gb, percent_used)
        VALUES (%s, %s, %s, %s, %s)
    """, (timestamp, disk["total_disk_space_gb"], disk["used_disk_space_gb"],
          disk["free_disk_space_gb"], disk["percent_used"]))

    # Network Metrics
    network = get_network_metrics()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS network_metrics (
            timestamp TEXT,
            bytes_sent BIGINT,
            bytes_recv BIGINT,
            packets_sent BIGINT,
            packets_recv BIGINT,
            errin INT,
            errout INT,
            dropin INT,
            dropout INT
        )
    """)
    cursor.execute("""
        INSERT INTO network_metrics (timestamp, bytes_sent, bytes_recv, packets_sent, packets_recv, errin, errout, dropin, dropout)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, (timestamp, network["bytes_sent"], network["bytes_recv"], network["packets_sent"],
          network["packets_recv"], network["errin"], network["errout"], network["dropin"], network["dropout"]))

    # Process Metrics
    process = get_process_metrics()
    top_procs = str(process["Top 5 Processes (by CPU)"])
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS process_metrics (
            timestamp TEXT,
            total_processes INT,
            zombie_processes INT,
            top_processes TEXT
        )
    """)
    cursor.execute("""
        INSERT INTO process_metrics (timestamp, total_processes, zombie_processes, top_processes)
        VALUES (%s, %s, %s, %s)
    """, (timestamp, process["Total Processes"], process["Zombie Processes"], top_procs))

    # System Info
    system = get_system_info()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS system_info (
            timestamp TEXT,
            os TEXT,
            version TEXT,
            hostname TEXT,
            ip TEXT,
            architecture TEXT,
            uptime_sec INT,
            logged_in_users INT
        )
    """)
    cursor.execute("""
        INSERT INTO system_info (timestamp, os, version, hostname, ip, architecture, uptime_sec, logged_in_users)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    """, (timestamp, system["OS"], system["OS Version"], system["Hostname"], system["IP Address"],
          system["Architecture"], system["Uptime (sec)"], system["Logged In Users"]))

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
