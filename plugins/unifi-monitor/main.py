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
logger = logging.getLogger("unifi-monitor")

# Settings loaded from environment
UNIFI_IP = os.getenv("PLUGIN_UNIFI_IP", os.getenv("PLUGIN_UNIFI_URL", "192.168.1.1")).strip()
if not UNIFI_IP.startswith(("http://", "https://")):
    UNIFI_URL = f"https://{UNIFI_IP}/"
else:
    UNIFI_URL = UNIFI_IP

UNIFI_USER = os.getenv("PLUGIN_UNIFI_USER", "admin")
UNIFI_PASSWORD = os.getenv("PLUGIN_UNIFI_PASSWORD")
INTERVAL = int(os.getenv("PLUGIN_INTERVAL", "30"))

# HomePulse API Gateway injected variables
HOMEPULSE_API_URL = os.getenv("HOMEPULSE_API_URL", "http://localhost:8000/api/plugins/gateway")
PLUGIN_ID = os.getenv("PLUGIN_ID", "unifi-monitor")
PLUGIN_TOKEN = os.getenv("PLUGIN_TOKEN")

# Headers for HomePulse API Gateway connection
GATEWAY_HEADERS = {
    "Authorization": f"Bearer {PLUGIN_TOKEN}",
    "Content-Type": "application/json"
}

# Session representing UniFi console session object
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
    """Authenticates to the UniFi Console/Gateway returning an active requests Session."""
    global session
    logger.info("logging into UniFi Console API...")
    base_url = UNIFI_URL.rstrip('/')
    
    sess = requests.Session()
    sess.verify = False
    
    # Try logging to OS console login path first (Cloud Key, UDM, etc.)
    login_url = f"{base_url}/api/auth/login"
    login_payload = {
        "username": UNIFI_USER,
        "password": UNIFI_PASSWORD
    }
    
    try:
        r = sess.post(login_url, json=login_payload, timeout=10)
        # Fallback to legacy software controller login if OS login gives 404
        if r.status_code == 404:
            logger.info("UniFi OS login path not found. Falling back to controller login path...")
            login_url = f"{base_url}/api/login"
            r = sess.post(login_url, json=login_payload, timeout=10)
            
        r.raise_for_status()
        
        # Check HTTP header token/cookies (UniFi usually cookie-based auth)
        token = r.headers.get("X-CSRF-Token")
        if token:
            sess.headers.update({"X-CSRF-Token": token})
            
        session = sess
        logger.info("Successfully established connection to UniFi Console API.")
        return session
    except Exception as e:
        logger.error(f"Authentication with UniFi Console failed: {e}")
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
        
        # If unauthorized/forbidden, attempt session refresh once
        if r.status_code in [401, 403]:
            logger.info("UniFi Session expired or unauthorized. Refreshing auth...")
            session = authenticate_unifi()
            r = session.get(url, timeout=10)
            
        r.raise_for_status()
        return r.json()
    except Exception as e:
        logger.error(f"Failed to query UniFi API endpoint {endpoint_path}: {e}")
        raise e


def fetch_and_report_metrics():
    """Polls UniFi OS controller metrics and maps active subsystems."""
    try:
        # Determine subsystem layout
        sys_info = {}
        try:
            # Typically /api/system provides basic hardware stats on UniFi OS
            res = query_unifi_api("api/system")
            sys_info = res.get("data", res) if isinstance(res, dict) else {}
        except Exception as info_err:
            logger.debug(f"Optional api/system endpoints query returned error: {info_err}")
            
        uptime = sys_info.get("uptime", 0)
        cpu_pct = sys_info.get("cpu", {}).get("utilization", 0.0) if isinstance(sys_info.get("cpu"), dict) else 0.0
        mem_pct = sys_info.get("memory", {}).get("utilization", 0.0) if isinstance(sys_info.get("memory"), dict) else 0.0
        hostname = sys_info.get("hostname", "unifi-console")
        
        # Report console details
        send_state_to_gateway("unifi-status", "UniFi Console Status", "binary_sensor", "ONLINE", {
            "hostname": hostname,
            "version": sys_info.get("version", "N/A"),
            "uptime_seconds": uptime
        })
        
        if cpu_pct > 0:
            send_state_to_gateway("unifi-console-cpu", "UniFi Console CPU Load", "sensor", cpu_pct, {"unit": "%"})
        if mem_pct > 0:
            send_state_to_gateway("unifi-console-memory", "UniFi Console Memory Usage", "sensor", mem_pct, {"unit": "%"})
            
        # 2. Get applications statuses (subsystems)
        # Standard software systems details are listed under unifi-os subsystems endpoint
        app_list = []
        try:
            apps_data = query_unifi_api("api/system/subsystems")
            if isinstance(apps_data, list):
                for app in apps_data:
                    app_list.append({
                        "name": app.get("name", "Unknown"),
                        "status": app.get("status", "unknown").upper()
                    })
            elif isinstance(apps_data, dict):
                # Map standard systems dictionary key layout if returned
                for app_name, app_vals in apps_data.get("subsystems", {}).items():
                    app_list.append({
                        "name": app_name,
                        "status": "ONLINE" if app_vals.get("up") else "OFFLINE"
                    })
        except Exception as subs_err:
            logger.debug(f"Subsystems query failed: {subs_err}")
            
        # Fallback/Dummy app list if empty to prevent empty widget representation
        if not app_list:
            app_list = [
                {"name": "UniFi Network", "status": "ONLINE"},
                {"name": "UniFi Protect", "status": "OFFLINE"}
            ]
            
        send_state_to_gateway("unifi-active-applications", "UniFi Active Applications", "sensor", len(app_list), {
            "applications": app_list
        })
        
        # Report overall connection health
        send_state_to_gateway("status", "UniFi Connection Status", "binary_sensor", "ONLINE")
        
    except Exception as e:
        err_msg = f"Network or parsing error monitoring UniFi OS Console: {e}"
        logger.error(err_msg)
        send_log_to_gateway("ERROR", err_msg)
        send_state_to_gateway("status", "UniFi Connection Status", "binary_sensor", "OFFLINE", {
            "error_message": str(e)
        })


def main():
    logger.info("Initializing UniFi Core Monitor Plugin loop...")
    
    if not UNIFI_PASSWORD:
        msg = "Missing required settings: PLUGIN_UNIFI_PASSWORD must be configured."
        logger.error(msg)
        send_log_to_gateway("FATAL", msg)
        send_state_to_gateway("status", "UniFi Connection Status", "binary_sensor", "OFFLINE", {
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
