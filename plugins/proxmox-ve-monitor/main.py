import os
import sys
import time
import logging
import requests
import traceback
from datetime import datetime, timezone

# Setup basic stdout logger
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("proxmox-ve-monitor")

# Prefixed with PLUGIN_ loaded from environment
PVE_IP = os.getenv("PLUGIN_PVE_IP", os.getenv("PLUGIN_PVE_URL", "192.168.0.142")).strip()
if not PVE_IP.startswith(("http://", "https://")):
    if ":" not in PVE_IP:
        PVE_URL = f"https://{PVE_IP}:8006/api2/json/"
    else:
        PVE_URL = f"https://{PVE_IP}/api2/json/"
else:
    PVE_URL = PVE_IP
    if not PVE_URL.endswith("/api2/json/"):
        PVE_URL = PVE_URL.rstrip('/') + "/api2/json/"
PVE_USER = os.getenv("PLUGIN_PVE_USER", "root@pam")
PVE_TOKEN_NAME = os.getenv("PLUGIN_PVE_TOKEN_NAME", "HomePulse")
PVE_TOKEN_SECRET = os.getenv("PLUGIN_PVE_TOKEN_SECRET")
PVE_NODE = os.getenv("PLUGIN_PVE_NODE", "pve")
INTERVAL = int(os.getenv("PLUGIN_INTERVAL", "30"))

# Core injected variables
HOMEPULSE_API_URL = os.getenv("HOMEPULSE_API_URL", "http://localhost:8000/api/plugins/gateway")
PLUGIN_ID = os.getenv("PLUGIN_ID", "proxmox-ve-monitor")
PLUGIN_TOKEN = os.getenv("PLUGIN_TOKEN")

# Headers for Proxmox API connection (API Token Auth)
PVE_HEADERS = {
    "Authorization": f"PVEAPIToken={PVE_USER}!{PVE_TOKEN_NAME}={PVE_TOKEN_SECRET}",
    "Accept": "application/json"
}

# Headers for HomePulse API Gateway connection
GATEWAY_HEADERS = {
    "Authorization": f"Bearer {PLUGIN_TOKEN}",
    "Content-Type": "application/json"
}


def send_state_to_gateway(entity_key, name, type_val, value, attributes=None):
    """Sends a state configuration update payload to the main HomePulse Gateway."""
    url = f"{HOMEPULSE_API_URL.rstrip('/')}/state"
    payload = {
        "node_id": PLUGIN_ID,
        "entity_key": entity_key,
        "name": name,
        "type": type_val,
        "value": str(value),
        "attributes": attributes or {}
    }
    try:
        r = requests.post(url, json=payload, headers=GATEWAY_HEADERS, timeout=5)
        if r.status_code != 200:
            logger.error(f"Failed to push state for {entity_key}: HTTP {r.status_code} - {r.text}")
    except Exception as e:
        logger.error(f"Error sending telemetry state of {entity_key} to gateway: {e}")


def send_log_to_gateway(level, message):
    """Logs trace warning/errors back to central HomePulse logging system."""
    url = f"{HOMEPULSE_API_URL.rstrip('/')}/logs"
    payload = {
        "plugin_id": PLUGIN_ID,
        "level": level.upper(),
        "message": message,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    try:
        r = requests.post(url, json=payload, headers=GATEWAY_HEADERS, timeout=5)
        if r.status_code != 200:
            logger.error(f"Failed to post gateway logs: HTTP {r.status_code} - {r.text}")
    except Exception as e:
        logger.error(f"Error sending log to gateway: {e}")


def query_pve_endpoint(endpoint_path):
    """Queries the Proxmox REST API with token authorization."""
    url = f"{PVE_URL.rstrip('/')}/{endpoint_path.lstrip('/')}"
    r = requests.get(url, headers=PVE_HEADERS, verify=False, timeout=10)
    r.raise_for_status()
    return r.json().get("data", {})


def fetch_and_report_metrics():
    """Polls Proxmox VE API status routes and forwards metrics locally."""
    try:
        logger.info(f"Querying Proxmox status from node: {PVE_NODE}")
        
        # 1. Fetch Node Diagnostics
        node_status = query_pve_endpoint(f"nodes/{PVE_NODE}/status")
        
        cpu_usage = round(float(node_status.get("cpu", 0.0)) * 100.0, 2)
        memory = node_status.get("memory", {})
        mem_used = memory.get("used", 0)
        mem_total = memory.get("total", 0)
        mem_pct = round((mem_used / mem_total) * 100.0, 2) if mem_total > 0 else 0.0
        
        rootfs = node_status.get("rootfs", {})
        disk_used = rootfs.get("used", 0)
        disk_total = rootfs.get("total", 0)
        disk_pct = round((disk_used / disk_total) * 100.0, 2) if disk_total > 0 else 0.0
        
        uptime = node_status.get("uptime", 0)
        pve_ver = node_status.get("pveversion", "Unknown")

        # Report PVE host diagnostic telemetry
        send_state_to_gateway("pve-node-status", "Proxmox Node Status", "binary_sensor", "ONLINE", {
            "pve_version": pve_ver,
            "uptime_seconds": uptime
        })
        send_state_to_gateway("pve-node-cpu", "Proxmox CPU Usage", "sensor", cpu_usage, {"unit": "%"})
        send_state_to_gateway("pve-node-memory", "Proxmox Memory Usage", "sensor", mem_pct, {
            "used_bytes": mem_used,
            "total_bytes": mem_total,
            "unit": "%"
        })
        send_state_to_gateway("pve-node-disk", "Proxmox Disk Usage", "sensor", disk_pct, {
            "used_bytes": disk_used,
            "total_bytes": disk_total,
            "unit": "%"
        })

        # 2. Fetch VMs/LXC status List
        vms_reported = 0
        vms_running = 0
        
        try:
            qemu_list = query_pve_endpoint(f"nodes/{PVE_NODE}/qemu")
            for vm in qemu_list:
                vmid = vm.get("vmid")
                name = vm.get("name", f"VM {vmid}")
                status = vm.get("status", "stopped").upper()
                send_state_to_gateway(
                    f"pve-vm-{vmid}-status",
                    f"VM {name} Status",
                    "binary_sensor",
                    status,
                    {
                        "name": name,
                        "type": "qemu",
                        "memory": vm.get("maxmem", 0)
                    }
                )
                vms_reported += 1
                if status == "RUNNING":
                    vms_running += 1
        except Exception as qemu_err:
            logger.warning(f"Failed to query QEMU guests: {qemu_err}")
            send_log_to_gateway("WARNING", f"Failed to query QEMU guests list: {qemu_err}")

        try:
            lxc_list = query_pve_endpoint(f"nodes/{PVE_NODE}/lxc")
            for lxc in lxc_list:
                vmid = lxc.get("vmid")
                name = lxc.get("name", f"LXC {vmid}")
                status = lxc.get("status", "stopped").upper()
                send_state_to_gateway(
                    f"pve-lxc-{vmid}-status",
                    f"LXC {name} Status",
                    "binary_sensor",
                    status,
                    {
                        "name": name,
                        "type": "lxc",
                        "memory": lxc.get("maxmem", 0)
                    }
                )
                vms_reported += 1
                if status == "RUNNING":
                    vms_running += 1
        except Exception as lxc_err:
            logger.warning(f"Failed to query LXC guests: {lxc_err}")
            send_log_to_gateway("WARNING", f"Failed to query LXC guests list: {lxc_err}")

        send_state_to_gateway("pve-active-guests", "Proxmox Active Guests", "sensor", vms_reported, {
            "running": vms_running,
            "stopped": vms_reported - vms_running
        })

        # 3. Fetch upgradable packages
        try:
            apt_list = query_pve_endpoint(f"nodes/{PVE_NODE}/apt/versions")
            pending_upgrades = len([pkg for pkg in apt_list if pkg.get("Version") != pkg.get("OldVersion")])
            send_state_to_gateway("pve-pending-updates", "Proxmox Pending Updates", "sensor", pending_upgrades)
        except Exception as apt_err:
            logger.debug(f"Optional update status check failed: {apt_err}")

        # Report overall healthy status
        send_state_to_gateway("status", "Proxmox Connection Status", "binary_sensor", "ONLINE")

    except requests.exceptions.RequestException as req_err:
        err_msg = f"Network query error connecting to Proxmox VE: {req_err}"
        logger.error(err_msg)
        send_log_to_gateway("ERROR", err_msg)
        send_state_to_gateway("status", "Proxmox Connection Status", "binary_sensor", "OFFLINE", {
            "error_message": err_msg
        })
    except Exception as e:
        err_msg = f"Unhandled error in Proxmox monitoring loop: {e}\n{traceback.format_exc()}"
        logger.error(err_msg)
        send_log_to_gateway("ERROR", err_msg)
        send_state_to_gateway("status", "Proxmox Connection Status", "binary_sensor", "OFFLINE", {
            "error_message": f"Plugin error: {e}"
        })


def main():
    logger.info("Initializing Proxmox VE Monitor Plugin loop...")
    
    if not PVE_TOKEN_NAME or not PVE_TOKEN_SECRET:
        msg = "Missing required authentication settings: PLUGIN_PVE_TOKEN_NAME and PLUGIN_PVE_TOKEN_SECRET must be defined."
        logger.error(msg)
        send_log_to_gateway("FATAL", msg)
        send_state_to_gateway("status", "Proxmox Connection Status", "binary_sensor", "OFFLINE", {
            "error_message": msg
        })
        sys.exit(1)

    # Disable SSL Warnings for self-signed certificates
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    while True:
        fetch_and_report_metrics()
        logger.info(f"Sleeping for {INTERVAL} seconds...")
        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()
