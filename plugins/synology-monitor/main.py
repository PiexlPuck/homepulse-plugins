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
logger = logging.getLogger("synology-monitor")

# Settings loaded from environment
SYNOLOGY_URL = os.getenv("PLUGIN_SYNOLOGY_URL", "https://192.168.0.100:5001/webapi/")
SYNOLOGY_USER = os.getenv("PLUGIN_SYNOLOGY_USER", "admin")
SYNOLOGY_PASSWORD = os.getenv("PLUGIN_SYNOLOGY_PASSWORD")
INTERVAL = int(os.getenv("PLUGIN_INTERVAL", "30"))

# HomePulse API Gateway injected variables
HOMEPULSE_API_URL = os.getenv("HOMEPULSE_API_URL", "http://localhost:8000/api/plugins/gateway")
PLUGIN_ID = os.getenv("PLUGIN_ID", "synology-monitor")
PLUGIN_TOKEN = os.getenv("PLUGIN_TOKEN")

# Headers for HomePulse API Gateway connection
GATEWAY_HEADERS = {
    "Authorization": f"Bearer {PLUGIN_TOKEN}",
    "Content-Type": "application/json"
}

# Cache for Synology Session ID
sid = None


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


def authenticate_dsm():
    """Authenticates to DSM WebAPI using auth.cgi/entry.cgi and grabs session ID (sid)."""
    global sid
    logger.info("Connecting to Synology API to log in...")
    base_url = SYNOLOGY_URL.rstrip('/')
    
    # We target first query.cgi to identify path of SYNO.API.Auth if needed, or query directly entry.cgi / auth.cgi
    # For modern DSM 6+, SYNO.API.Auth is available under entry.cgi or auth.cgi.
    login_url = f"{base_url}/entry.cgi"
    params = {
        "api": "SYNO.API.Auth",
        "version": "6",
        "method": "login",
        "account": SYNOLOGY_USER,
        "passwd": SYNOLOGY_PASSWORD,
        "session": "DSM",
        "format": "sid"
    }
    
    try:
        r = requests.get(login_url, params=params, verify=False, timeout=10)
        # Fallback to auth.cgi if entry.cgi fails or returns api not supported
        if r.status_code != 200 or not r.json().get("success"):
            logger.info("Login via entry.cgi was unsuccessful, attempting auth.cgi fallback...")
            fallback_url = f"{base_url}/auth.cgi"
            params["version"] = "3"
            r = requests.get(fallback_url, params=params, verify=False, timeout=10)
            
        r.raise_for_status()
        res = r.json()
        if not res.get("success"):
            error_info = res.get("error", {})
            code = error_info.get("code", "Unknown")
            raise ValueError(f"DSM Login failed with API Error Code: {code}")
            
        sid = res.get("data", {}).get("sid")
        if not sid:
            raise ValueError("No sid session token received in response.")
        logger.info("Successfully established authenticated session with Synology DSM.")
        return sid
    except Exception as e:
        logger.error(f"Failed to authenticate with Synology DSM: {e}")
        raise e


def query_dsm_api(api_name, method, version, custom_params=None):
    """Direct helper to query API namespaces using SID credentials."""
    global sid
    if not sid:
        sid = authenticate_dsm()
        
    base_url = SYNOLOGY_URL.rstrip('/')
    url = f"{base_url}/entry.cgi"
    
    params = {
        "api": api_name,
        "version": version,
        "method": method,
        "_sid": sid
    }
    if custom_params:
        params.update(custom_params)
        
    try:
        r = requests.get(url, params=params, verify=False, timeout=10)
        r.raise_for_status()
        res = r.json()
        
        # If session expired (errors like session not found, code 105), retry once
        if not res.get("success") and res.get("error", {}).get("code") in [105, 106, 107]:
            logger.info("DSM session expired or invalid. Re-authenticating...")
            sid = authenticate_dsm()
            params["_sid"] = sid
            r = requests.get(url, params=params, verify=False, timeout=10)
            r.raise_for_status()
            res = r.json()
            
        return res
    except Exception as e:
        logger.error(f"Error querying Synology API key {api_name}: {e}")
        raise e


def fetch_and_report_metrics():
    """Polls Synology system logs, core utilization, and volume indices."""
    try:
        # 1. Fetch system info status
        res_info = query_dsm_api("SYNO.Core.System", "info", "1")
        info_data = res_info.get("data", {}) if res_info.get("success") else {}
        
        model = info_data.get("model", "Synology NAS")
        firmware = info_data.get("firmware_ver", "Unknown")
        cpu_temp = info_data.get("cpu_temperature", 0)
        sys_status = info_data.get("sys_status", "safe")
        
        state_status = "ONLINE" if sys_status == "safe" else "WARNING"
        send_state_to_gateway("synology-system-status", "Synology System Status", "binary_sensor", state_status, {
            "model": model,
            "firmware_version": firmware,
            "cpu_temperature": cpu_temp
        })
        
        # 2. Fetch utilization ratios
        res_util = query_dsm_api("SYNO.Core.System.Utilization", "get", "1")
        util_data = res_util.get("data", {}) if res_util.get("success") else {}
        
        cpu_load = util_data.get("cpu", {}).get("user_load", 0) + util_data.get("cpu", {}).get("system_load", 0)
        cpu_load = round(float(cpu_load), 2)
        
        mem_pct = util_data.get("memory", {}).get("real_usage", 0.0)
        mem_avail = util_data.get("memory", {}).get("avail_real", 0)
        
        send_state_to_gateway("synology-cpu-usage", "Synology CPU Usage", "sensor", cpu_load, {"unit": "%"})
        send_state_to_gateway("synology-memory-usage", "Synology Memory Usage", "sensor", mem_pct, {
            "available_bytes": mem_avail,
            "unit": "%"
        })
        
        # 3. Fetch volumes information
        res_stg = query_dsm_api("SYNO.Storage.CGI.Storage", "load_info", "1")
        stg_data = res_stg.get("data", {}) if res_stg.get("success") else {}
        
        volumes = stg_data.get("volumes", [])
        volume_list = []
        
        for vol in volumes:
            vol_name = vol.get("desc", vol.get("volume_path", "volume"))
            status = vol.get("status", "normal").upper()
            total_bytes = int(vol.get("size", {}).get("total", 0))
            used_bytes = int(vol.get("size", {}).get("used", 0))
            free_bytes = total_bytes - used_bytes
            
            used_pct = round((used_bytes / total_bytes) * 100.0, 2) if total_bytes > 0 else 0.0
            
            # Format sizes in GB
            total_gb = round(total_bytes / (1024**3), 2)
            used_gb = round(used_bytes / (1024**3), 2)
            
            volume_list.append({
                "volume": vol_name,
                "status": status,
                "used_percent": f"{used_pct}%",
                "size_used": f"{used_gb} GB",
                "size_total": f"{total_gb} GB"
            })
            
        send_state_to_gateway("synology-storage-summary", "Synology Storage Summary", "sensor", len(volume_list), {
            "volumes": volume_list
        })
        
        # Report overall healthy status
        send_state_to_gateway("status", "Synology Connection Status", "binary_sensor", "ONLINE")
        
    except Exception as e:
        err_msg = f"Error gathering Synology DSM system telemetry: {e}"
        logger.error(err_msg)
        send_log_to_gateway("ERROR", err_msg)
        send_state_to_gateway("status", "Synology Connection Status", "binary_sensor", "OFFLINE", {
            "error_message": str(e)
        })


def main():
    logger.info("Initializing Synology Monitor Plugin loop...")
    
    if not SYNOLOGY_PASSWORD:
        msg = "Missing required authentication settings: PLUGIN_SYNOLOGY_PASSWORD must be defined."
        logger.error(msg)
        send_log_to_gateway("FATAL", msg)
        send_state_to_gateway("status", "Synology Connection Status", "binary_sensor", "OFFLINE", {
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
