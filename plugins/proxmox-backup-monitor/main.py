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
logger = logging.getLogger("proxmox-backup-monitor")

# Prefixed with PLUGIN_ loaded from environment
PBS_URL = os.getenv("PLUGIN_PBS_URL", "https://192.168.0.142:8007/api2/json/")
PBS_NODE = os.getenv("PLUGIN_PBS_NODE", "localhost")
PBS_TOKEN_ID = os.getenv("PLUGIN_PBS_TOKEN_ID")
PBS_TOKEN_SECRET = os.getenv("PLUGIN_PBS_TOKEN_SECRET")
INTERVAL = int(os.getenv("PLUGIN_INTERVAL", "30"))

# Core injected variables
HOMEPULSE_API_URL = os.getenv("HOMEPULSE_API_URL", "http://localhost:8000/api/plugins/gateway")
PLUGIN_ID = os.getenv("PLUGIN_ID", "proxmox-backup-monitor")
PLUGIN_TOKEN = os.getenv("PLUGIN_TOKEN")

# Headers for Proxmox Backup Server API connection (API Token Auth)
# Header Format: Authorization: PBSAPIToken=username@realm!tokenid:tokensecret
PBS_HEADERS = {
    "Authorization": f"PBSAPIToken={PBS_TOKEN_ID}:{PBS_TOKEN_SECRET}",
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


def query_pbs_endpoint(endpoint_path):
    """Queries the Proxmox Backup Server REST API with token authorization."""
    url = f"{PBS_URL.rstrip('/')}/{endpoint_path.lstrip('/')}"
    r = requests.get(url, headers=PBS_HEADERS, verify=False, timeout=10)
    r.raise_for_status()
    return r.json().get("data", {})


def fetch_and_report_metrics():
    """Polls Proxmox Backup Server API routes and forwards metrics locally."""
    try:
        logger.info(f"Querying Proxmox Backup Server status from node: {PBS_NODE}")
        
        # 1. Fetch Node Diagnostics status info
        node_status = query_pbs_endpoint(f"nodes/{PBS_NODE}/status")
        
        # CPU parsing
        cpu_val = node_status.get("cpu", 0.0)
        cpu_usage = round(float(cpu_val) * 100.0, 2)
        
        # Memory parsing
        memory = node_status.get("memory", {})
        mem_used = memory.get("used", 0)
        mem_total = memory.get("total", 0)
        mem_pct = round((mem_used / mem_total) * 100.0, 2) if mem_total > 0 else 0.0
        
        # Swap parsing
        swap = node_status.get("swap", {})
        swap_used = swap.get("used", 0)
        swap_total = swap.get("total", 0)
        swap_pct = round((swap_used / swap_total) * 100.0, 2) if swap_total > 0 else 0.0
        
        uptime = node_status.get("uptime", 0)

        # Report PBS host diagnostics
        send_state_to_gateway("pbs-node-status", "PBS Node Status", "binary_sensor", "ONLINE", {
            "uptime_seconds": uptime
        })
        send_state_to_gateway("pbs-node-cpu", "PBS CPU Usage", "sensor", cpu_usage, {"unit": "%"})
        send_state_to_gateway("pbs-node-memory", "PBS Memory Usage", "sensor", mem_pct, {
            "used_bytes": mem_used,
            "total_bytes": mem_total,
            "unit": "%"
        })
        send_state_to_gateway("pbs-node-swap", "PBS Swap Usage", "sensor", swap_pct, {
            "used_bytes": swap_used,
            "total_bytes": swap_total,
            "unit": "%"
        })

        # 2. Fetch Datastores
        datastores = query_pbs_endpoint("admin/datastore")
        
        # Summary attributes
        datastore_list = []
        for ds in datastores:
            store = ds.get("store")
            if not store:
                continue
                
            total = ds.get("total", 0)
            used = ds.get("used", 0)
            avail = ds.get("avail", 0)
            capacity_pct = round((used / total) * 100.0, 2) if total > 0 else 0.0
            
            # Fetch garbage collection status path
            gc_status_val = "UNKNOWN"
            gc_attribs = {}
            try:
                gc_data = query_pbs_endpoint(f"admin/datastore/{store}/gc")
                last_run_state = gc_data.get("last-run-state")
                if last_run_state:
                    gc_status_val = "OK" if last_run_state.upper() == "OK" else "FAILED"
                
                gc_attribs = {
                    "last_run_state": last_run_state or "Never Run",
                    "removed_bytes": gc_data.get("removed-bytes", 0),
                    "still_anchor": gc_data.get("still-anchor", 0),
                    "removed_chunks": gc_data.get("removed-chunks", 0),
                    "pending_bytes": gc_data.get("pending-bytes", 0),
                    "disk_bytes": gc_data.get("disk-bytes", 0)
                }
            except Exception as gc_err:
                logger.warning(f"Failed to query GC status for datastore {store}: {gc_err}")
                send_log_to_gateway("WARNING", f"Failed to query GC status for datastore {store}: {gc_err}")
            
            # Send datastore metrics
            send_state_to_gateway(
                f"pbs-datastore-{store}-status",
                f"PBS Datastore {store} Status",
                "binary_sensor",
                "ONLINE",
                {
                    "total_bytes": total,
                    "used_bytes": used,
                    "avail_bytes": avail
                }
            )
            send_state_to_gateway(
                f"pbs-datastore-{store}-capacity",
                f"PBS Datastore {store} Capacity",
                "sensor",
                capacity_pct,
                {"unit": "%"}
            )
            send_state_to_gateway(
                f"pbs-datastore-{store}-gc-status",
                f"PBS Datastore {store} GC Status",
                "binary_sensor",
                gc_status_val,
                gc_attribs
            )
            
            datastore_list.append({
                "store": store,
                "total": total,
                "used": used,
                "avail": avail,
                "capacity_pct": capacity_pct,
                "gc_status": gc_status_val
            })

        # Push status representing summary datastores list
        send_state_to_gateway("pbs-datastores-summary", "PBS Datastores Summary", "sensor", len(datastore_list), {
            "datastores": datastore_list
        })

        # Report overall healthy status
        send_state_to_gateway("status", "PBS Connection Status", "binary_sensor", "ONLINE")
        logger.info("Successfully fetched and forwarded all Proxmox Backup Server metrics.")

    except requests.exceptions.RequestException as req_err:
        err_msg = f"Network query error connecting to Proxmox Backup Server: {req_err}"
        logger.error(err_msg)
        send_log_to_gateway("ERROR", err_msg)
        send_state_to_gateway("status", "PBS Connection Status", "binary_sensor", "OFFLINE", {
            "error_message": err_msg
        })
    except Exception as e:
        err_msg = f"Unhandled error in Proxmox Backup Server monitoring loop: {e}\n{traceback.format_exc()}"
        logger.error(err_msg)
        send_log_to_gateway("ERROR", err_msg)
        send_state_to_gateway("status", "PBS Connection Status", "binary_sensor", "OFFLINE", {
            "error_message": f"Plugin error: {e}"
        })


def main():
    logger.info("Initializing Proxmox Backup Server Monitor loop...")
    
    if not PBS_TOKEN_ID or not PBS_TOKEN_SECRET:
        msg = "Missing required authentication settings: PLUGIN_PBS_TOKEN_ID and PLUGIN_PBS_TOKEN_SECRET must be defined."
        logger.error(msg)
        send_log_to_gateway("FATAL", msg)
        send_state_to_gateway("status", "PBS Connection Status", "binary_sensor", "OFFLINE", {
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
