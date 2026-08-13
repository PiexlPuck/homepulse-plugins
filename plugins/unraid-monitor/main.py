import os
import sys
import time
import logging
import requests
import traceback

# Setup stdout logger
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("unraid-monitor")

# Load environment configuration variables
UNRAID_URL = os.getenv("UNRAID_URL", "http://192.168.0.220/graphql")
API_KEY = os.getenv("API_KEY")
INTERVAL = int(os.getenv("INTERVAL", "30"))

# HomePulse API Gateway parameters
HOMEPULSE_GATEWAY_URL = os.getenv("HOMEPULSE_GATEWAY_URL", "http://localhost:8000")
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


def send_state_to_gateway(entity_key, value, attributes=None):
    """Sends a state configuration update payload to the main HomePulse Gateway."""
    url = f"{HOMEPULSE_GATEWAY_URL}/api/plugins/gateway/state"
    payload = {
        "entity_key": entity_key,
        "value": value,
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
              free
              used
              total
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
          }
          vms {
            id
            name
            state
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
            
            # Memory parsing (inputs returned in bytes or kb depending on OS spec)
            mem = system.get("memory", {})
            mem_total = mem.get("total", 0)
            mem_free = mem.get("free", 0)
            mem_used = mem_total - mem_free
            mem_pct = round((mem_used / mem_total) * 100.0, 2) if mem_total > 0 else 0.0
            
            send_state_to_gateway("unraid-system-status", "ONLINE", {
                "hostname": hostname,
                "version": version,
                "uptime_seconds": uptime
            })
            
            send_state_to_gateway("unraid-memory", mem_pct, {
                "used_bytes": mem_used,
                "total_bytes": mem_total,
                "unit": "%"
            })

        # 2. Parse Array Metrics
        arrayStatus = data.get("array", {})
        if arrayStatus:
            state = arrayStatus.get("state", "UNKNOWN").upper()
            capacity = arrayStatus.get("capacity", {})
            arr_free = capacity.get("free", 0)
            arr_used = capacity.get("used", 0)
            arr_total = capacity.get("total", 0)
            arr_pct = round((arr_used / arr_total) * 100.0, 2) if arr_total > 0 else 0.0
            
            send_state_to_gateway("unraid-array-status", state)
            send_state_to_gateway("unraid-array-capacity", arr_pct, {
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
                
                send_state_to_gateway(f"unraid-disk-{disk_name}-temp", disk_temp, {
                    "size": disk_size,
                    "status": disk_status,
                    "unit": "°C"
                })

        # 3. Parse Docker Containers
        containers = data.get("dockerContainers", [])
        if containers:
            running_containers = sum(1 for c in containers if c.get("state", "").lower() == "running")
            send_state_to_gateway("unraid-active-containers", running_containers, {
                "total": len(containers)
            })

        # 4. Parse Virtual Machines (VMs)
        vms = data.get("vms", [])
        if vms:
            running_vms = sum(1 for v in vms if v.get("state", "").lower() == "running")
            send_state_to_gateway("unraid-active-vms", running_vms, {
                "total": len(vms)
            })

        send_health_status("healthy")
        logger.info("Successfully fetched and forwarded Unraid metrics.")

    except requests.exceptions.RequestException as req_err:
        err_msg = f"Network connection error to Unraid GraphQL API: {req_err}"
        logger.error(err_msg)
        send_log_to_gateway("ERROR", err_msg)
        send_state_to_gateway("unraid-system-status", "OFFLINE")
        send_health_status("degraded", err_msg)
    except Exception as e:
        err_msg = f"Unexpected error in Unraid monitoring loop: {e}\n{traceback.format_exc()}"
        logger.error(err_msg)
        send_log_to_gateway("ERROR", err_msg)
        send_health_status("degraded", f"Unraid monitor error: {e}")


def main():
    logger.info("Initializing Unraid API Monitor Plugin loop...")

    # Simple validations for authorization key existence
    if not API_KEY:
        msg = "Missing required authentication settings: API_KEY must be configured in environment."
        logger.error(msg)
        send_log_to_gateway("FATAL", msg)
        send_health_status("degraded", msg)
        sys.exit(1)

    while True:
        fetch_and_report_metrics()
        logger.info(f"Sleeping for {INTERVAL} seconds...")
        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()
