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
logger = logging.getLogger("unifi-protect-monitor")

# Settings loaded from environment
UNIFI_IP = os.getenv("PLUGIN_UNIFI_IP", os.getenv("PLUGIN_UNIFI_URL", "192.168.1.1")).strip()
if not UNIFI_IP.startswith(("http://", "https://")):
    UNIFI_URL = f"https://{UNIFI_IP}/"
else:
    UNIFI_URL = UNIFI_IP

UNIFI_API_KEY = os.getenv("PLUGIN_UNIFI_API_KEY")
INTERVAL = int(os.getenv("PLUGIN_INTERVAL", "30"))

# HomePulse API Gateway injected variables
HOMEPULSE_API_URL = os.getenv("HOMEPULSE_API_URL", "http://localhost:8000/api/plugins/gateway")
PLUGIN_ID = os.getenv("PLUGIN_ID", "unifi-protect-monitor")
PLUGIN_TOKEN = os.getenv("PLUGIN_TOKEN")

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


def query_protect_api(endpoint_path):
    """Helper tool querying UniFi Protect local proxy integration API."""
    base_url = UNIFI_URL.rstrip('/')
    url = f"{base_url}/proxy/protect/integration/v1/{endpoint_path.lstrip('/')}"
    
    headers = {
        "X-API-KEY": UNIFI_API_KEY,
        "Accept": "application/json"
    }
    
    r = requests.get(url, headers=headers, verify=False, timeout=10)
    r.raise_for_status()
    return r.json()


def fetch_and_report_metrics():
    """Polls UniFi Protect camera arrays and disk arrays statuses."""
    try:
        # 1. Fetch Cameras
        cameras = query_protect_api("cameras")
        cam_list = []
        for cam in cameras:
            if isinstance(cam, dict):
                cam_list.append({
                    "id": cam.get("id", "N/A"),
                    "name": cam.get("name", "Unknown Camera"),
                    "model": cam.get("model", "N/A"),
                    "connectionState": cam.get("connectionState", "disconnected").upper(),
                    "mac": cam.get("mac", "N/A")
                })
        
        send_state_to_gateway("unifi-protect-cameras", "UniFi Protect Cameras", "sensor", len(cam_list), {
            "cameras": cam_list
        })

        # 2. Fetch NVR System (disks)
        nvr = query_protect_api("nvr")
        disks = nvr.get("storage", {}).get("devices", [])
        disk_list = []
        for disk in disks:
            if isinstance(disk, dict):
                disk_name = disk.get("name", "Disk")
                model = disk.get("model", "Unknown")
                size_bytes = disk.get("size", 0)
                status = disk.get("status", "unknown").upper()
                
                # Format size
                size_tb = round(size_bytes / (1024**4), 2)
                
                disk_list.append({
                    "name": disk_name,
                    "model": model,
                    "size": f"{size_tb} TB",
                    "status": status
                })
                
        send_state_to_gateway("unifi-protect-nvr", "UniFi Protect NVR Disks", "sensor", len(disk_list), {
            "disks": disk_list
        })

        # Report overall healthy status
        send_state_to_gateway("status", "UniFi Protect Connection Status", "binary_sensor", "ONLINE")

    except Exception as e:
        err_msg = f"Error querying UniFi Protect Application: {e}"
        logger.error(err_msg)
        send_log_to_gateway("ERROR", err_msg)
        send_state_to_gateway("status", "UniFi Protect Connection Status", "binary_sensor", "OFFLINE", {
            "error_message": str(e)
        })


def main():
    logger.info("Initializing UniFi Protect Monitor Plugin loop...")
    
    if not UNIFI_API_KEY:
        msg = "Missing required settings: PLUGIN_UNIFI_API_KEY must be configured."
        logger.error(msg)
        send_log_to_gateway("FATAL", msg)
        send_state_to_gateway("status", "UniFi Protect Connection Status", "binary_sensor", "OFFLINE", {
            "error_message": msg
        })
        sys.exit(1)

    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    while True:
        fetch_and_report_metrics()
        logger.info(f"Sleeping for {INTERVAL} seconds...")
        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()
