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
logger = logging.getLogger("unifi-network-monitor")

# Settings loaded from environment
UNIFI_IP = os.getenv("PLUGIN_UNIFI_IP", os.getenv("PLUGIN_UNIFI_URL", "192.168.1.1")).strip()
if not UNIFI_IP.startswith(("http://", "https://")):
    UNIFI_URL = f"https://{UNIFI_IP}/"
else:
    UNIFI_URL = UNIFI_IP

UNIFI_USER = os.getenv("PLUGIN_UNIFI_USER", "admin")
UNIFI_PASSWORD = os.getenv("PLUGIN_UNIFI_PASSWORD")
UNIFI_SITE_ID = os.getenv("PLUGIN_UNIFI_SITE_ID", "default")
INTERVAL = int(os.getenv("PLUGIN_INTERVAL", "30"))

# HomePulse API Gateway injected variables
HOMEPULSE_API_URL = os.getenv("HOMEPULSE_API_URL", "http://localhost:8000/api/plugins/gateway")
PLUGIN_ID = os.getenv("PLUGIN_ID", "unifi-network-monitor")
PLUGIN_TOKEN = os.getenv("PLUGIN_TOKEN")

# Headers for HomePulse API Gateway connection
GATEWAY_HEADERS = {
    "Authorization": f"Bearer {PLUGIN_TOKEN}",
    "Content-Type": "application/json"
}

# Requests session cache
session = None


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


def authenticate_unifi():
    """Authenticates to the UniFi Console/Controller returning an active Session."""
    global session
    logger.info("Logging into UniFi Console / Controller API for network monitoring...")
    base_url = UNIFI_URL.rstrip('/')
    
    sess = requests.Session()
    sess.verify = False
    
    login_url = f"{base_url}/api/auth/login"
    login_payload = {
        "username": UNIFI_USER,
        "password": UNIFI_PASSWORD
    }
    
    try:
        r = sess.post(login_url, json=login_payload, timeout=10)
        # Fallback to software controller login path if OS login path does not exist
        if r.status_code == 404:
            logger.info("UniFi OS login path 404, falling back to legacy login...")
            login_url = f"{base_url}/api/login"
            r = sess.post(login_url, json=login_payload, timeout=10)
            
        r.raise_for_status()
        
        token = r.headers.get("X-CSRF-Token")
        if token:
            sess.headers.update({"X-CSRF-Token": token})
            
        session = sess
        logger.info("Successfully established connection to UniFi Network API.")
        return session
    except Exception as e:
        logger.error(f"Authentication with UniFi Controller failed: {e}")
        raise e


def query_unifi_api(endpoint_path):
    """Retrieves JSON results from UniFi API with fallback authentication support."""
    global session
    if not session:
        session = authenticate_unifi()
        
    base_url = UNIFI_URL.rstrip('/')
    url = f"{base_url}/{endpoint_path.lstrip('/')}"
    
    try:
        r = session.get(url, timeout=10)
        if r.status_code in [401, 403]:
            logger.info("UniFi Session expired or unauthorized. Refreshing authentication...")
            session = authenticate_unifi()
            r = session.get(url, timeout=10)
            
        r.raise_for_status()
        return r.json()
    except Exception as e:
        logger.error(f"Failed to query UniFi Network API endpoint {endpoint_path}: {e}")
        raise e


def fetch_and_report_metrics():
    """Polls client and device statistics from the UniFi Network Controller app."""
    try:
        # 1. Fetch connected clients
        client_res = query_unifi_api(f"proxy/network/api/s/{UNIFI_SITE_ID}/stat/sta")
        # Direct fallback for standard controllers without proxy path
        if not isinstance(client_res, dict) or "data" not in client_res:
            client_res = query_unifi_api(f"api/s/{UNIFI_SITE_ID}/stat/sta")
            
        clients_data = client_res.get("data", []) if isinstance(client_res, dict) else []
        client_list = []
        
        for cli in clients_data:
            mac = cli.get("mac", "")
            ip = cli.get("ip", "")
            hostname = cli.get("hostname", cli.get("name", "Unknown"))
            is_wired = cli.get("is_wired", False)
            signal = cli.get("rssi", cli.get("signal", -1))
            
            client_list.append({
                "mac": mac,
                "ip": ip,
                "hostname": hostname,
                "is_wired": "WIRED" if is_wired else "WIRELESS",
                "signal": f"{signal} dBm" if not is_wired and signal != -1 else "N/A"
            })
            
        send_state_to_gateway("unifi-network-clients", "UniFi Network Clients", "sensor", len(client_list), {
            "clients": client_list
        })

        # 2. Fetch network hardware devices
        device_res = query_unifi_api(f"proxy/network/api/s/{UNIFI_SITE_ID}/stat/device")
        # Direct fallback
        if not isinstance(device_res, dict) or "data" not in device_res:
            device_res = query_unifi_api(f"api/s/{UNIFI_SITE_ID}/stat/device")
            
        devices_data = device_res.get("data", []) if isinstance(device_res, dict) else []
        device_list = []
        
        for dev in devices_data:
            name = dev.get("name", dev.get("model", "AP/Switch"))
            model = dev.get("model", "Unknown")
            state = dev.get("state", 1)  # 1 is typically connected/normal
            uptime = dev.get("uptime", 0)
            
            # Map state status
            status = "CONNECTED" if state == 1 else "DISCONNECTED"
            
            # Load stats (defensive check)
            sys_stats = dev.get("system-stats", {})
            cpu = sys_stats.get("cpu", 0.0)
            mem = sys_stats.get("mem", 0.0)
            
            # Convert values
            cpu_val = f"{round(float(cpu), 2)}%"
            mem_val = f"{round(float(mem), 2)}%"
            
            # Convert uptime to readable
            uptime_hours = round(uptime / 3600.0, 1)
            
            device_list.append({
                "name": name,
                "model": model,
                "state": status,
                "uptime": f"{uptime_hours} hrs",
                "cpu": cpu_val,
                "mem": mem_val
            })
            
        send_state_to_gateway("unifi-network-devices", "UniFi Network Devices", "sensor", len(device_list), {
            "devices": device_list
        })
        
        # Report overall healthy status
        send_state_to_gateway("status", "UniFi Network Connection Status", "binary_sensor", "ONLINE")
        
    except Exception as e:
        err_msg = f"Error querying UniFi Network Application: {e}"
        logger.error(err_msg)
        send_log_to_gateway("ERROR", err_msg)
        send_state_to_gateway("status", "UniFi Network Connection Status", "binary_sensor", "OFFLINE", {
            "error_message": str(e)
        })


def main():
    logger.info("Initializing UniFi Network Monitor Plugin loop...")
    
    if not UNIFI_PASSWORD:
        msg = "Missing required settings: PLUGIN_UNIFI_PASSWORD must be configured."
        logger.error(msg)
        send_log_to_gateway("FATAL", msg)
        send_state_to_gateway("status", "UniFi Network Connection Status", "binary_sensor", "OFFLINE", {
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
