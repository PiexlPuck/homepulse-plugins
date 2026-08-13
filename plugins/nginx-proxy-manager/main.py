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
logger = logging.getLogger("nginx-proxy-manager-monitor")

# Prefixed with PLUGIN_ loaded from environment
NPM_URL = os.getenv("PLUGIN_NPM_URL", "http://192.168.0.142:81/api")
IDENTITY = os.getenv("PLUGIN_IDENTITY", "admin@example.com")
SECRET = os.getenv("PLUGIN_SECRET")
INTERVAL = int(os.getenv("PLUGIN_INTERVAL", "30"))

# Core injected variables
HOMEPULSE_API_URL = os.getenv("HOMEPULSE_API_URL", "http://localhost:8000/api/plugins/gateway")
PLUGIN_ID = os.getenv("PLUGIN_ID", "nginx-proxy-manager")
PLUGIN_TOKEN = os.getenv("PLUGIN_TOKEN")

# Headers for HomePulse API Gateway connection
GATEWAY_HEADERS = {
    "Authorization": f"Bearer {PLUGIN_TOKEN}",
    "Content-Type": "application/json"
}

# Cache for Nginx Proxy Manager JWT token
npm_token = None
token_expires = None


def get_npm_token():
    """Gets or refreshes the JSON Web Token (JWT) from Nginx Proxy Manager."""
    global npm_token, token_expires
    
    # Check if cached token is still valid
    if npm_token and token_expires and datetime.now(timezone.utc) < token_expires:
        return npm_token

    logger.info("Requesting new JWT credentials token from NPM API...")
    url = f"{NPM_URL.rstrip('/')}/tokens"
    payload = {
        "identity": IDENTITY,
        "secret": SECRET
    }
    
    try:
        r = requests.post(url, json=payload, timeout=8)
        r.raise_for_status()
        res_json = r.json()
        
        npm_token = res_json.get("token")
        expires_str = res_json.get("expires")
        
        if expires_str:
            # Parse ISO timestamp expiration time
            expires_str = expires_str.replace("Z", "+00:00")
            token_expires = datetime.fromisoformat(expires_str)
        else:
            # Fallback to 1 hour expiration
            token_expires = datetime.now(timezone.utc) + requests.structures.timedelta(hours=1)
            
        logger.info("Successfully fetched NPM access token.")
        return npm_token
    except Exception as e:
        logger.error(f"Error authenticating to Nginx Proxy Manager: {e}")
        raise e


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


def query_npm_resource(endpoint_path):
    """Sends an authorized GET request to NPM API endpoint."""
    token = get_npm_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json"
    }
    url = f"{NPM_URL.rstrip('/')}/{endpoint_path.lstrip('/')}"
    r = requests.get(url, headers=headers, timeout=10)
    r.raise_for_status()
    return r.json()


def fetch_and_report_metrics():
    """Polls Nginx Proxy Manager APIs and forwards host stats to HomePulse."""
    try:
        logger.info(f"Querying NPM resources from API URL: {NPM_URL}")
        
        # 1. Fetch Proxy Hosts
        proxies = query_npm_resource("nginx/proxy-hosts")
        total_proxies = len(proxies)
        active_proxies = sum(1 for p in proxies if p.get("enabled") == 1 or p.get("enabled") is True)
        disabled_proxies = total_proxies - active_proxies
        
        # Formulate host status lists
        proxy_details = []
        for p in proxies:
            proxy_details.append({
                "id": p.get("id"),
                "domain_names": p.get("domain_names", []),
                "forward_host": p.get("forward_host"),
                "forward_port": p.get("forward_port"),
                "enabled": p.get("enabled"),
                "ssl_forced": p.get("ssl_forced")
            })

        # 2. Fetch Redirection Hosts
        redirects = query_npm_resource("nginx/redirection-hosts")
        total_redirects = len(redirects)

        # 3. Fetch Stream Hosts
        streams = query_npm_resource("nginx/streams")
        total_streams = len(streams)

        # Report NPM statuses
        send_state_to_gateway("npm-system-status", "NPM System Status", "binary_sensor", "ONLINE")
        
        send_state_to_gateway("npm-proxy-summary", "NPM Proxy Summary", "sensor", active_proxies, {
            "total_proxies": total_proxies,
            "active_proxies": active_proxies,
            "disabled_proxies": disabled_proxies,
            "hosts": proxy_details
        })
        
        send_state_to_gateway("npm-redirection-summary", "NPM Redirection Summary", "sensor", total_redirects)
        send_state_to_gateway("npm-stream-summary", "NPM Stream Summary", "sensor", total_streams)

        # Report overall healthy status
        send_state_to_gateway("status", "NPM Connection Status", "binary_sensor", "ONLINE")
        logger.info("Successfully fetched and forwarded NPM status configurations.")

    except requests.exceptions.RequestException as req_err:
        err_msg = f"Network connection error to Nginx Proxy Manager API: {req_err}"
        logger.error(err_msg)
        send_log_to_gateway("ERROR", err_msg)
        send_state_to_gateway("npm-system-status", "NPM System Status", "binary_sensor", "OFFLINE")
        send_state_to_gateway("status", "NPM Connection Status", "binary_sensor", "OFFLINE", {
            "error_message": err_msg
        })
    except Exception as e:
        err_msg = f"Unexpected error in Nginx Proxy Manager monitoring loop: {e}\n{traceback.format_exc()}"
        logger.error(err_msg)
        send_log_to_gateway("ERROR", err_msg)
        send_state_to_gateway("status", "NPM Connection Status", "binary_sensor", "OFFLINE", {
            "error_message": f"Plugin error: {e}"
        })


def main():
    logger.info("Initializing Nginx Proxy Manager Monitor Plugin loop...")

    # Simple validations for email credentials and passwords
    if not IDENTITY or not SECRET:
        msg = "Missing required authentication settings: PLUGIN_IDENTITY and PLUGIN_SECRET must be configured in environment."
        logger.error(msg)
        send_log_to_gateway("FATAL", msg)
        send_state_to_gateway("status", "NPM Connection Status", "binary_sensor", "OFFLINE", {
            "error_message": msg
        })
        sys.exit(1)

    while True:
        fetch_and_report_metrics()
        logger.info(f"Sleeping for {INTERVAL} seconds...")
        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()
