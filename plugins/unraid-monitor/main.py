import os
import sys
import time
import logging
import requests
import traceback
from datetime import datetime, timezone

# Setup stdout logger
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("unraid-monitor")

# Prefixed with PLUGIN_ loaded from environment
UNRAID_IP = os.getenv("PLUGIN_UNRAID_IP", os.getenv("PLUGIN_UNRAID_URL", "192.168.0.220")).strip()
if not UNRAID_IP.startswith(("http://", "https://")):
    UNRAID_URL = f"http://{UNRAID_IP}/graphql"
else:
    UNRAID_URL = UNRAID_IP
    if not UNRAID_URL.endswith("/graphql"):
        UNRAID_URL = UNRAID_URL.rstrip('/') + "/graphql"
API_KEY = os.getenv("PLUGIN_API_KEY")
INTERVAL = int(os.getenv("PLUGIN_INTERVAL", "30"))

# Core injected variables
HOMEPULSE_API_URL = os.getenv("HOMEPULSE_API_URL", "http://localhost:8000/api/plugins/gateway")
PLUGIN_ID = os.getenv("PLUGIN_ID", "unraid-monitor")
PLUGIN_TOKEN = os.getenv("PLUGIN_TOKEN")

# Headers for Unraid Native GraphQL connection
UNRAID_HEADERS = {
    "x-api-key": API_KEY,
    "Content-Type": "application/json"
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


def query_unraid_graphql(query_string):
    """Sends a POST request containing a GraphQL query to Unraid OS."""
    payload = {"query": query_string}
    r = requests.post(UNRAID_URL, json=payload, headers=UNRAID_HEADERS, timeout=10)
    r.raise_for_status()
    res_json = r.json()
    if "errors" in res_json:
        raise ValueError(f"GraphQL Errors present: {res_json['errors']}")
    return res_json.get("data", {})


def fetch_and_report_metrics():
    """Polls Unraid OS GraphQL queries and forwards metrics to HomePulse."""
    try:
        logger.info(f"Querying Unraid GraphQL endpoint: {UNRAID_URL}")

        # Combined GraphQL query to pull system status, array details, containers, and disks
        query_str = """
        query {
          system {
            hostname
            version
            uptime
            cpu {
              model
              cores
            }
            memory {
              total
              free
            }
          }
          array {
            state
            capacity {
              kilobytes {
                free
                used
                total
              }
            }
            disks {
              name
              size
              status
              temp
            }
          }
          dockerContainers {
            id
            names
            state
            status
            autoStart
          }
          vms {
            id
            name
            state
            autoStart
          }
        }
        """
        
        data = query_unraid_graphql(query_str)
        
        # 1. Parse System Metrics
        system = data.get("system", {})
        if system:
            hostname = system.get("hostname", "unraid")
            version = system.get("version", "Unknown")
            uptime = system.get("uptime", 0)
            
            mem = system.get("memory", {})
            mem_total = mem.get("total", 0)
            mem_free = mem.get("free", 0)
            mem_used = mem_total - mem_free
            mem_pct = round((mem_used / mem_total) * 100.0, 2) if mem_total > 0 else 0.0
            
            send_state_to_gateway("unraid-system-status", "Unraid System Status", "binary_sensor", "ONLINE", {
                "hostname": hostname,
                "version": version,
                "uptime_seconds": uptime,
                "cpu_cores": system.get("cpu", {}).get("cores", 1),
                "cpu_model": system.get("cpu", {}).get("model", "Unknown")
            })
            
            send_state_to_gateway("unraid-memory", "Unraid Memory Usage", "sensor", mem_pct, {
                "used_bytes": mem_used,
                "total_bytes": mem_total,
                "unit": "%"
            })

        # 2. Parse Array Metrics
        arrayStatus = data.get("array", {})
        if arrayStatus:
            state = arrayStatus.get("state", "UNKNOWN").upper()
            capacity = arrayStatus.get("capacity", {})
            kb = capacity.get("kilobytes", {})
            arr_free = int(kb.get("free", 0)) * 1024
            arr_used = int(kb.get("used", 0)) * 1024
            arr_total = int(kb.get("total", 0)) * 1024
            arr_pct = round((arr_used / arr_total) * 100.0, 2) if arr_total > 0 else 0.0
            
            send_state_to_gateway("unraid-array-status", "Unraid Array Status", "sensor", state)
            send_state_to_gateway("unraid-array-capacity", "Unraid Array Capacity", "sensor", arr_pct, {
                "free_bytes": arr_free,
                "used_bytes": arr_used,
                "total_bytes": arr_total,
                "unit": "%"
            })
            
            # Disk temps and status check
            disks = arrayStatus.get("disks", [])
            for disk in disks:
                disk_name = disk.get("name", "unknown")
                disk_size = disk.get("size", 0)
                disk_status = disk.get("status", "NORMAL").upper()
                disk_temp = disk.get("temp", 0)
                
                send_state_to_gateway(
                    f"unraid-disk-{disk_name}-temp",
                    f"Unraid Disk {disk_name} Temperature",
                    "sensor",
                    disk_temp,
                    {
                        "size": disk_size,
                        "status": disk_status,
                        "unit": "°C"
                    }
                )

        # 3. Parse Docker Containers
        containers = data.get("dockerContainers", [])
        if containers:
            running_containers = sum(1 for c in containers if c.get("state", "").lower() == "running")
            container_list = [
                {
                    "names": c.get("names", []),
                    "state": c.get("state"),
                    "status": c.get("status"),
                    "auto_start": c.get("autoStart", False)
                } for c in containers
            ]
            send_state_to_gateway("unraid-active-containers", "Unraid Active Containers", "sensor", running_containers, {
                "total": len(containers),
                "containers": container_list
            })

        # 4. Parse Virtual Machines (VMs)
        vms = data.get("vms", [])
        if vms:
            running_vms = sum(1 for v in vms if v.get("state", "").lower() == "running")
            vm_list = [
                {
                    "name": v.get("name"),
                    "state": v.get("state"),
                    "auto_start": v.get("autoStart", False)
                } for v in vms
            ]
            send_state_to_gateway("unraid-active-vms", "Unraid Active VMs", "sensor", running_vms, {
                "total": len(vms),
                "vms": vm_list
            })

        # 5. Optional Share List Query (GraphQL defensive fetch)
        try:
            shares_query = """
            query {
              shares {
                name
              }
            }
            """
            shares_data = query_unraid_graphql(shares_query)
            shares_list = shares_data.get("shares", [])
            if isinstance(shares_list, list):
                send_state_to_gateway("unraid-shares-count", "Unraid Shares Count", "sensor", len(shares_list), {
                    "shares": [s.get("name") for s in shares_list if s.get("name")]
                })
        except Exception as share_err:
            logger.debug(f"Optional Unraid shares query ignored/unsupported: {share_err}")

        # Report overall healthy status
        send_state_to_gateway("status", "Unraid Connection Status", "binary_sensor", "ONLINE")
        logger.info("Successfully fetched and forwarded Unraid metrics.")

    except requests.exceptions.RequestException as req_err:
        err_msg = f"Network connection error to Unraid GraphQL API: {req_err}"
        logger.error(err_msg)
        send_log_to_gateway("ERROR", err_msg)
        send_state_to_gateway("unraid-system-status", "Unraid System Status", "binary_sensor", "OFFLINE")
        send_state_to_gateway("status", "Unraid Connection Status", "binary_sensor", "OFFLINE", {
            "error_message": err_msg
        })
    except Exception as e:
        err_msg = f"Unexpected error in Unraid monitoring loop: {e}\n{traceback.format_exc()}"
        logger.error(err_msg)
        send_log_to_gateway("ERROR", err_msg)
        send_state_to_gateway("status", "Unraid Connection Status", "binary_sensor", "OFFLINE", {
            "error_message": f"Plugin error: {e}"
        })


def main():
    logger.info("Initializing Unraid API Monitor Plugin loop...")

    # Simple validations for authorization key existence
    if not API_KEY:
        msg = "Missing required authentication settings: PLUGIN_API_KEY must be configured in environment."
        logger.error(msg)
        send_log_to_gateway("FATAL", msg)
        send_state_to_gateway("status", "Unraid Connection Status", "binary_sensor", "OFFLINE", {
            "error_message": msg
        })
        sys.exit(1)

    while True:
        fetch_and_report_metrics()
        logger.info(f"Sleeping for {INTERVAL} seconds...")
        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()
