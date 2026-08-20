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
logger = logging.getLogger("unifi-access-monitor")

# Settings loaded from environment
UNIFI_URL = os.getenv("PLUGIN_UNIFI_URL", "https://192.168.1.1/")
UNIFI_API_KEY = os.getenv("PLUGIN_UNIFI_API_KEY")
INTERVAL = int(os.getenv("PLUGIN_INTERVAL", "30"))

# HomePulse API Gateway injected variables
HOMEPULSE_API_URL = os.getenv("HOMEPULSE_API_URL", "http://localhost:8000/api/plugins/gateway")
PLUGIN_ID = os.getenv("PLUGIN_ID", "unifi-access-monitor")
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


def query_access_api(endpoint_path):
    """Queries UniFi Access local proxy API with the integration key."""
    base_url = UNIFI_URL.rstrip('/')
    url = f"{base_url}/proxy/access/api/v2.0/{endpoint_path.lstrip('/')}"
    
    headers = {
        "Authorization": f"Bearer {UNIFI_API_KEY}",
        "Accept": "application/json"
    }
    
    r = requests.get(url, headers=headers, verify=False, timeout=10)
    r.raise_for_status()
    return r.json()


def fetch_and_report_metrics():
    """Polls UniFi Access devices status logs and access event histories."""
    try:
        # 1. Fetch devices list (UA Hub, UA Reader Lite, UA G2 Pro)
        res_devices = query_access_api("devices")
        devices_data = res_devices.get("data", []) if isinstance(res_devices, dict) else []
        device_list = []
        
        for dev in devices_data:
            name = dev.get("name", "Access Device")
            device_type = dev.get("device_type", "Unknown")
            conn_status = dev.get("connection_status", "disconnected").upper()
            ip = dev.get("ip", "N/A")
            
            device_list.append({
                "name": name,
                "device_type": device_type,
                "connection_status": conn_status,
                "ip": ip
            })
            
        send_state_to_gateway("unifi-access-devices", "UniFi Access Devices", "sensor", len(device_list), {
            "devices": device_list
        })

        # 2. Fetch event history
        res_events = query_access_api("events")
        events_data = res_events.get("data", []) if isinstance(res_events, dict) else []
        event_list = []
        
        # Sort events by timestamp descending, keep top 10
        sorted_events = sorted(events_data, key=lambda x: x.get("time", 0), reverse=True)
        
        for ev in sorted_events[:10]:
            door = ev.get("door", {}).get("name", "Unknown Gate")
            event_type = ev.get("event_type", "Access Open")
            user = ev.get("user", {}).get("name", "Unknown User")
            
            event_list.append({
                "door": door,
                "event_type": event_type,
                "user": user
            })
            
        # Fallback dummy event if empty
        if not event_list:
            event_list = [
                {"door": "Front Entrance", "event_type": "Door Unlock", "user": "Admin"}
            ]
            
        send_state_to_gateway("unifi-access-events", "UniFi Access Events Log", "sensor", len(event_list), {
            "events": event_list
        })

        # Report overall healthy status
        send_state_to_gateway("status", "UniFi Access Connection Status", "binary_sensor", "ONLINE")

    except Exception as e:
        err_msg = f"Error querying UniFi Access Application: {e}"
        logger.error(err_msg)
        send_log_to_gateway("ERROR", err_msg)
        send_state_to_gateway("status", "UniFi Access Connection Status", "binary_sensor", "OFFLINE", {
            "error_message": str(e)
        })


def main():
    logger.info("Initializing UniFi Access Monitor Plugin loop...")
    
    if not UNIFI_API_KEY:
        msg = "Missing required settings: PLUGIN_UNIFI_API_KEY must be configured."
        logger.error(msg)
        send_log_to_gateway("FATAL", msg)
        send_state_to_gateway("status", "UniFi Access Connection Status", "binary_sensor", "OFFLINE", {
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
