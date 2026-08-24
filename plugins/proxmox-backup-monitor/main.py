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
PBS_IP = os.getenv("PLUGIN_PBS_IP", os.getenv("PLUGIN_PBS_URL", "192.168.0.142")).strip()
if not PBS_IP.startswith(("http://", "https://")):
    if ":" not in PBS_IP:
        PBS_URL = f"https://{PBS_IP}:8007/api2/json/"
    else:
        PBS_URL = f"https://{PBS_IP}/api2/json/"
else:
    PBS_URL = PBS_IP
    if not PBS_URL.endswith("/api2/json/"):
        PBS_URL = PBS_URL.rstrip('/') + "/api2/json/"
PBS_NODE = os.getenv("PLUGIN_PBS_NODE", "localhost")
PBS_USER = os.getenv("PLUGIN_PBS_USER", "root@pam")
PBS_TOKEN_NAME = os.getenv("PLUGIN_PBS_TOKEN_NAME", "HomePulse")
PBS_TOKEN_SECRET = os.getenv("PLUGIN_PBS_TOKEN_SECRET")
INTERVAL = int(os.getenv("PLUGIN_INTERVAL", "30"))

# Core injected variables
HOMEPULSE_API_URL = os.getenv("HOMEPULSE_API_URL", "http://localhost:8000/api/plugins/gateway")
PLUGIN_ID = os.getenv("PLUGIN_ID", "proxmox-backup-monitor")
PLUGIN_TOKEN = os.getenv("PLUGIN_TOKEN")

# Headers for Proxmox Backup Server API connection (API Token Auth)
# Header Format: Authorization: PBSAPIToken=username@realm!tokenid:tokensecret
PBS_HEADERS = {
    "Authorization": f"PBSAPIToken={PBS_USER}!{PBS_TOKEN_NAME}:{PBS_TOKEN_SECRET}",
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

        # 3. Query Disks List
        try:
            logger.info("Querying host disk list status...")
            disks_list = query_pbs_endpoint(f"nodes/{PBS_NODE}/disks/list")
            if isinstance(disks_list, list):
                send_state_to_gateway("pbs-disks-summary", "PBS Disks Summary", "sensor", len(disks_list), {
                    "disks": disks_list
                })
                for disk in disks_list:
                    d_name = disk.get("name", "unknown")
                    d_model = disk.get("model", "Unknown")
                    d_size = disk.get("size", 0)
                    d_type = disk.get("disk-type", "unknown")
                    d_status = disk.get("status", "unknown")
                    d_wearout = disk.get("wearout")
                    
                    state_val = "ONLINE" if str(d_status).lower() == "passed" else "OFFLINE"
                    send_state_to_gateway(
                        f"pbs-disk-{d_name}",
                        f"PBS Disk {d_name}",
                        "binary_sensor",
                        state_val,
                        {
                            "model": d_model,
                            "size_bytes": d_size,
                            "disk_type": d_type,
                            "wearout_percent": d_wearout if d_wearout is not None else "N/A",
                            "status": d_status
                        }
                    )
        except Exception as disk_err:
            logger.warning(f"Failed to query disks list: {disk_err}")
            send_log_to_gateway("WARNING", f"Failed to query host disks list: {disk_err}")

        # 4. Query Tasks
        try:
            logger.info("Querying system task history...")
            tasks_list = query_pbs_endpoint(f"nodes/{PBS_NODE}/tasks")
            if isinstance(tasks_list, list):
                active_tasks = [t for t in tasks_list if t.get("endtime") is None]
                send_state_to_gateway("pbs-active-tasks-count", "PBS Active Tasks Count", "sensor", len(active_tasks), {
                    "active_tasks": active_tasks[:10]
                })
                
                sorted_tasks = sorted(tasks_list, key=lambda x: x.get("starttime", 0), reverse=True)
                backup_tasks = [t for t in sorted_tasks if t.get("worker_type") == "backup"]
                
                if backup_tasks:
                    last_backup = backup_tasks[0]
                    lb_status = last_backup.get("status")
                    lb_endtime = last_backup.get("endtime")
                    
                    if lb_endtime is None:
                        backup_val = "RUNNING"
                    elif lb_status == "OK":
                        backup_val = "OK"
                    else:
                        backup_val = f"ERROR ({lb_status or 'Unknown'})"
                        
                    send_state_to_gateway("pbs-last-backup-status", "PBS Last Backup Status", "sensor", backup_val, {
                        "upid": last_backup.get("upid"),
                        "worker_id": last_backup.get("worker_id"),
                        "starttime": datetime.fromtimestamp(last_backup.get("starttime", 0), timezone.utc).isoformat() if last_backup.get("starttime") else "N/A",
                        "endtime": datetime.fromtimestamp(lb_endtime, timezone.utc).isoformat() if lb_endtime else "N/A"
                    })
                else:
                    send_state_to_gateway("pbs-last-backup-status", "PBS Last Backup Status", "sensor", "UNKNOWN", {
                        "message": "No backup tasks found in history."
                    })
        except Exception as task_err:
            logger.warning(f"Failed to query tasks list: {task_err}")
            send_log_to_gateway("WARNING", f"Failed to query host task history: {task_err}")

        # 5. Query Services
        try:
            logger.info("Querying core backup service states...")
            services_list = query_pbs_endpoint(f"nodes/{PBS_NODE}/services")
            if isinstance(services_list, list):
                for sname in ["proxmox-backup", "proxmox-backup-proxy"]:
                    match_service = next((s for s in services_list if s.get("service") == sname), None)
                    if match_service:
                        state_val = "ONLINE" if match_service.get("state") == "running" else "OFFLINE"
                        send_state_to_gateway(
                            f"pbs-service-{sname}",
                            f"PBS Service {match_service.get('desc', sname)}",
                            "binary_sensor",
                            state_val,
                            {
                                "unit-state": match_service.get("unit-state", "unknown"),
                                "state": match_service.get("state", "unknown")
                            }
                        )
        except Exception as serv_err:
            logger.warning(f"Failed to query services list: {serv_err}")
            send_log_to_gateway("WARNING", f"Failed to query host services: {serv_err}")

        # 6. Query Subscription Status
        try:
            logger.info("Querying system support subscription key status...")
            sub = query_pbs_endpoint(f"nodes/{PBS_NODE}/subscription")
            sub_status = sub.get("status", "UNKNOWN").upper()
            send_state_to_gateway("pbs-subscription-status", "PBS Subscription Status", "sensor", sub_status, {
                "message": sub.get("message", "N/A"),
                "serverid": sub.get("serverid", "N/A")
            })
        except Exception as sub_err:
            logger.warning(f"Failed to query subscription: {sub_err}")

        # 7. Query Sync Configuration List
        try:
            logger.info("Querying remote sync job configuration rules...")
            syncs = query_pbs_endpoint("config/sync")
            if isinstance(syncs, list):
                send_state_to_gateway("pbs-sync-jobs-count", "PBS Sync Jobs Count", "sensor", len(syncs), {
                    "sync_jobs": syncs
                })
        except Exception as sync_err:
            logger.warning(f"Failed to query sync configurations: {sync_err}")

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
    
    if not PBS_TOKEN_NAME or not PBS_TOKEN_SECRET:
        msg = "Missing required authentication settings: PLUGIN_PBS_TOKEN_NAME and PLUGIN_PBS_TOKEN_SECRET must be defined."
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
