import os
import sys
import time
import logging
import requests
import traceback

# Setup basic stdout logger
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("proxmox-ve-monitor")

# Load environment configuration variables
PVE_URL = os.getenv("PVE_URL", "https://192.168.0.142:8006/api2/json/")
PVE_USER = os.getenv("PVE_USER", "root@pam")
PVE_TOKEN_ID = os.getenv("PVE_TOKEN_ID")
PVE_TOKEN_SECRET = os.getenv("PVE_TOKEN_SECRET")
PVE_NODE = os.getenv("PVE_NODE", "pve")
INTERVAL = int(os.getenv("INTERVAL", "30"))

# HomePulse API Gateway parameters
HOMEPULSE_GATEWAY_URL = os.getenv("HOMEPULSE_GATEWAY_URL", "http://localhost:8000")
PLUGIN_TOKEN = os.getenv("PLUGIN_TOKEN")

# Headers for Proxmox API connection (API Token Auth)
# PVE API Token header format: Authorization: PVEAPIToken=username@realm!tokenid=tokensecret
PVE_HEADERS = {
    "Authorization": f"PVEAPIToken={PVE_TOKEN_ID}={PVE_TOKEN_SECRET}",
    "Accept": "application/json"
}

# Headers for HomePulse API Gateway connection
GATEWAY_HEADERS = {
    "Authorization": f"Bearer {PLUGIN_TOKEN}",
    "Content-Type": "application/json"
}


def send_state_to_gateway(entity_key, value, attributes=None):
    """Sends a state configuration update payload to the main HomePulse Gateway."""
    url = f"{HOMEPULSE_GATEWAY_URL}/api/plugins/gateway/state"
    payload = {
        "entity_key": entity_key,
        "value": value,
        "attributes": attributes or {}
    }
    try:
        # Disable certificate check on local gateway communication
        r = requests.post(url, json=payload, headers=GATEWAY_HEADERS, timeout=5)
        if r.status_code != 200:
            logger.error(f"Failed to push state for {entity_key}: HTTP {r.status_code} - {r.text}")
    except Exception as e:
        logger.error(f"Error sending telemetry state of {entity_key} to gateway: {e}")


def send_log_to_gateway(level, message):
    """Logs trace warning/errors back to central HomePulse logging system."""
    url = f"{HOMEPULSE_GATEWAY_URL}/api/plugins/gateway/logs"
    payload = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "level": level.upper(),
        "message": message
    }
    try:
        r = requests.post(url, json=payload, headers=GATEWAY_HEADERS, timeout=5)
        if r.status_code != 200:
            logger.error(f"Failed to post gateway logs: HTTP {r.status_code} - {r.text}")
    except Exception as e:
        # Fallback to local stdout logging
        logger.error(f"Error sending log to gateway: {e}")


def send_health_status(status, error_message=""):
    """Reports overall plugin query health back to gateway."""
    url = f"{HOMEPULSE_GATEWAY_URL}/api/plugins/gateway/state"
    payload = {
        "status": status,
        "error_message": error_message
    }
    try:
        requests.post(url, json=payload, headers=GATEWAY_HEADERS, timeout=5)
    except Exception as e:
        logger.error(f"Error sending health status key: {e}")


def query_pve_endpoint(endpoint_path):
    """Queries the Proxmox REST API with token authorization."""
    url = f"{PVE_URL.rstrip('/')}/{endpoint_path.lstrip('/')}"
    # Suppress SSL warning checks since PVE nodes usually use self-signed local certs
    r = requests.get(url, headers=PVE_HEADERS, verify=False, timeout=10)
    r.raise_for_status()
    return r.json().get("data", {})


def fetch_and_report_metrics():
    """Polls Proxmox VE API status routes and forwards metrics locally."""
    try:
        logger.info(f"Querying Proxmox status from node: {PVE_NODE}")
        
        # 1. Fetch Node Diagnostics
        # Route: nodes/{node}/status
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
        send_state_to_gateway("pve-node-status", "ONLINE", {
            "pve_version": pve_ver,
            "uptime_seconds": uptime
        })
        send_state_to_gateway("pve-node-cpu", cpu_usage, {"unit": "%"})
        send_state_to_gateway("pve-node-memory", mem_pct, {
            "used_bytes": mem_used,
            "total_bytes": mem_total,
            "unit": "%"
        })
        send_state_to_gateway("pve-node-disk", disk_pct, {
            "used_bytes": disk_used,
            "total_bytes": disk_total,
            "unit": "%"
        })

        # 2. Fetch VMs/LXC status List
        # Route: nodes/{node}/qemu and nodes/{node}/lxc
        vms_reported = 0
        vms_running = 0
        
        try:
            qemu_list = query_pve_endpoint(f"nodes/{PVE_NODE}/qemu")
            for vm in qemu_list:
                vmid = vm.get("vmid")
                name = vm.get("name", f"VM {vmid}")
                status = vm.get("status", "stopped").upper()
                send_state_to_gateway(f"pve-vm-{vmid}-status", status, {
                    "name": name,
                    "type": "qemu",
                    "memory": vm.get("maxmem", 0)
                })
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
                send_state_to_gateway(f"pve-lxc-{vmid}-status", status, {
                    "name": name,
                    "type": "lxc",
                    "memory": lxc.get("maxmem", 0)
                })
                vms_reported += 1
                if status == "RUNNING":
                    vms_running += 1
        except Exception as lxc_err:
            logger.warning(f"Failed to query LXC guests: {lxc_err}")
            send_log_to_gateway("WARNING", f"Failed to query LXC guests list: {lxc_err}")

        send_state_to_gateway("pve-active-guests", vms_reported, {
            "running": vms_running,
            "stopped": vms_reported - vms_running
        })

        # 3. Fetch upgradable packages badging info (Optional check)
        try:
            apt_list = query_pve_endpoint(f"nodes/{PVE_NODE}/apt/versions")
            pending_upgrades = len([pkg for pkg in apt_list if pkg.get("Version") != pkg.get("OldVersion")])
            send_state_to_gateway("pve-pending-updates", pending_upgrades)
        except Exception as apt_err:
            # PVE API Token might lack Sys.Audit permission keys
            logger.debug(f"Optional update status check failed: {apt_err}")

        # If everything completes without errors, report clean health status
        send_health_status("healthy")
        logger.info("Successfully fetched and forwarded all Proxmox metrics.")

    except requests.exceptions.RequestException as req_err:
        err_msg = f"Network query error connecting to Proxmox VE: {req_err}"
        logger.error(err_msg)
        send_log_to_gateway("ERROR", err_msg)
        send_state_to_gateway("pve-node-status", "OFFLINE")
        send_health_status("degraded", err_msg)
    except Exception as e:
        err_msg = f"Unhandled error in Proxmox monitoring loop: {e}\n{traceback.format_exc()}"
        logger.error(err_msg)
        send_log_to_gateway("ERROR", err_msg)
        send_health_status("degraded", f"Internal monitor crash: {e}")


def main():
    logger.info("Initializing Proxmox VE Monitor Plugin loop...")
    
    # Simple validation checks for mandatory credential parameters
    if not PVE_TOKEN_ID or not PVE_TOKEN_SECRET:
        msg = "Missing required authentication settings: PVE_TOKEN_ID and PVE_TOKEN_SECRET environment variables must be defined."
        logger.error(msg)
        send_log_to_gateway("FATAL", msg)
        send_health_status("degraded", msg)
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
