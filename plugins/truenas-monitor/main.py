import os
import sys
import time
import logging
import requests
import traceback
import ssl
import json
import websocket
from datetime import datetime, timezone

# Setup basic stdout logger
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("truenas-monitor")

# Prefixed with PLUGIN_ loaded from environment
TRUENAS_URL = os.getenv("PLUGIN_TRUENAS_URL", "http://192.168.0.100/api/v2.0/")
API_KEY = os.getenv("PLUGIN_API_KEY")
INTERVAL = int(os.getenv("PLUGIN_INTERVAL", "30"))

# Core injected variables
HOMEPULSE_API_URL = os.getenv("HOMEPULSE_API_URL", "http://localhost:8000/api/plugins/gateway")
PLUGIN_ID = os.getenv("PLUGIN_ID", "truenas-monitor")
PLUGIN_TOKEN = os.getenv("PLUGIN_TOKEN")

# Headers for HomePulse API Gateway connection
GATEWAY_HEADERS = {
    "Authorization": f"Bearer {PLUGIN_TOKEN}",
    "Content-Type": "application/json"
}

# Mapping legacy endpoint paths to WebSocket methods
ENDPOINT_METHOD_MAP = {
    "system/info": "system.info",
    "alert/list": "alert.list",
    "pool": "pool.query",
    "disk": "disk.query",
    "service": "service.query",
    "vm": "vm.query",
    "interface": "interface.query"
}

# Global active client variable
ws_client = None


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


class TrueNASWSClient:
    def __init__(self, url, api_key):
        self.url = url
        self.api_key = api_key
        self.ws = None
        self.request_id = 0

    def connect(self):
        from urllib.parse import urlparse
        parsed = urlparse(self.url)
        scheme = "wss" if parsed.scheme == "https" else "ws"
        netloc = parsed.netloc or parsed.path.split("/")[0]
        # Build clean ws/wss endpoint pointing to TrueNAS websocket middleware
        ws_endpoint = f"{scheme}://{netloc}/websocket"
        
        logger.info(f"Connecting to TrueNAS WebSocket: {ws_endpoint}")
        self.ws = websocket.create_connection(
            ws_endpoint,
            sslopt={"cert_reqs": ssl.CERT_NONE},
            timeout=10
        )
        
        # Initiate connection DDP handshake
        self.ws.send(json.dumps({"msg": "connect", "version": "1", "support": ["1"]}))
        resp = json.loads(self.ws.recv())
        if resp.get("msg") != "connected":
            raise Exception(f"WebSocket handshake failed, received: {resp}")
            
        # Authenticate with API key
        self.call("auth.login_with_api_key", [self.api_key])

    def call(self, method, params=None):
        self.request_id += 1
        req_id = str(self.request_id)
        payload = {
            "id": req_id,
            "msg": "method",
            "method": method,
            "params": params or []
        }
        self.ws.send(json.dumps(payload))
        
        while True:
            resp_str = self.ws.recv()
            resp = json.loads(resp_str)
            if resp.get("id") == req_id:
                if "error" in resp:
                    raise Exception(f"API Error calling {method}: {resp['error']}")
                return resp.get("result")

    def close(self):
        if self.ws:
            try:
                self.ws.close()
            except Exception:
                pass


def query_truenas_endpoint(endpoint_path):
    """Queries the TrueNAS WebSocket client using the legacy endpoint paths map."""
    global ws_client
    method = ENDPOINT_METHOD_MAP.get(endpoint_path, endpoint_path.replace("/", "."))
    return ws_client.call(method)


def fetch_and_report_metrics():
    """Polls TrueNAS API pathways over WebSockets and forwards telemetry states back."""
    global ws_client
    try:
        logger.info(f"Querying TrueNAS resources from API URL: {TRUENAS_URL}")
        ws_client = TrueNASWSClient(TRUENAS_URL, API_KEY)
        ws_client.connect()
        
        # 1. Fetch System Info properties
        sys_info = query_truenas_endpoint("system/info")
        version = sys_info.get("version", "Unknown")
        hostname = sys_info.get("hostname", "truenas")
        uptime = sys_info.get("uptime_seconds", 0)
        physmem = sys_info.get("physmem", 0)
        
        send_state_to_gateway("truenas-system-status", "TrueNAS System Status", "binary_sensor", "ONLINE", {
            "version": version,
            "hostname": hostname,
            "uptime_seconds": uptime,
            "physmem_bytes": physmem
        })

        # 2. Fetch Active System Warnings / Alerts
        try:
            alerts = query_truenas_endpoint("alert/list")
            top_alerts = []
            for alert in alerts[:5]:
                top_alerts.append({
                    "id": alert.get("id"),
                    "level": alert.get("level", "WARNING"),
                    "message": alert.get("formatted", ""),
                    "datetime": alert.get("datetime")
                })
            send_state_to_gateway("truenas-alerts-count", "TrueNAS Active Alerts", "sensor", len(alerts), {
                "active_alerts": top_alerts
            })
        except Exception as alert_err:
            logger.warning(f"Failed to query alerts: {alert_err}")
            send_log_to_gateway("WARNING", f"Failed to query alerts: {alert_err}")

        # 3. Fetch Storage Pools (ZFS status)
        try:
            pools = query_truenas_endpoint("pool")
            pool_list = []
            for pool in pools:
                name = pool.get("name", "unknown")
                status = pool.get("status", "UNKNOWN").upper()
                healthy = pool.get("healthy", False)
                state = "ONLINE" if healthy else "OFFLINE"
                
                send_state_to_gateway(
                    f"truenas-pool-{name}-healthy",
                    f"TrueNAS Pool {name} Health",
                    "binary_sensor",
                    state,
                    {"status": status}
                )
                pool_list.append({
                    "name": name,
                    "status": status,
                    "healthy": healthy
                })
            send_state_to_gateway("truenas-pools-summary", "TrueNAS Pools Summary", "sensor", len(pools), {
                "pools": pool_list
            })
        except Exception as pool_err:
            logger.warning(f"Failed to query storage pools: {pool_err}")
            send_log_to_gateway("WARNING", f"Failed to query storage pools: {pool_err}")

        # 4. Fetch Drives Inventory
        try:
            disks = query_truenas_endpoint("disk")
            disk_list = []
            for disk in disks:
                name = disk.get("name")
                if not name:
                    continue
                serial = disk.get("serial", "unknown")
                size = disk.get("size", 0)
                dtype = disk.get("type", "HDD")
                smart_ok = disk.get("smart_enabled", True)
                state = "ONLINE" if smart_ok else "OFFLINE"
                
                send_state_to_gateway(
                    f"truenas-disk-{name}-status",
                    f"TrueNAS Disk {name} Status",
                    "binary_sensor",
                    state,
                    {
                        "serial": serial,
                        "size_bytes": size,
                        "type": dtype
                    }
                )
                disk_list.append({
                    "name": name,
                    "serial": serial,
                    "size_bytes": size,
                    "type": dtype,
                    "smart_enabled": smart_ok
                })
            send_state_to_gateway("truenas-disks-count", "TrueNAS Disks Count", "sensor", len(disk_list))
        except Exception as disk_err:
            logger.warning(f"Failed to query disk list: {disk_err}")
            send_log_to_gateway("WARNING", f"Failed to query disk list: {disk_err}")

        # 5. Fetch Services Status
        try:
            logger.info("Querying system services status...")
            services = query_truenas_endpoint("service")
            if isinstance(services, list):
                for sname in ["smb", "nfs", "ssh", "iscsitarget", "webdav", "smartd"]:
                    match_srv = next((s for s in services if s.get("service") == sname), None)
                    if match_srv:
                        state = "ONLINE" if match_srv.get("state") == "RUNNING" else "OFFLINE"
                        send_state_to_gateway(
                            f"truenas-service-{sname}",
                            f"TrueNAS Service {sname.upper()}",
                            "binary_sensor",
                            state,
                            {
                                "state": match_srv.get("state", "UNKNOWN"),
                                "enable": match_srv.get("enable", False)
                            }
                        )
        except Exception as srv_err:
            logger.warning(f"Failed to query TrueNAS services: {srv_err}")

        # 6. Fetch Virtual Machines (VMs)
        try:
            logger.info("Querying virtual machines...")
            vms_list = query_truenas_endpoint("vm")
            if isinstance(vms_list, list):
                active_vms = sum(1 for v in vms_list if v.get("status", {}).get("state") == "RUNNING")
                send_state_to_gateway("truenas-vms-count", "TrueNAS VMs Count", "sensor", len(vms_list))
                send_state_to_gateway("truenas-vms-active", "TrueNAS Active VMs", "sensor", active_vms, {
                    "vms": [
                        {
                            "name": v.get("name"),
                            "state": v.get("status", {}).get("state"),
                            "cores": v.get("vcpus"),
                            "memory": v.get("memory")
                        } for v in vms_list
                    ]
                })
        except Exception as vm_err:
            logger.warning(f"Failed to query TrueNAS VMs: {vm_err}")

        # 7. Fetch Network Interfaces
        try:
            logger.info("Querying network interfaces...")
            interfaces = query_truenas_endpoint("interface")
            if isinstance(interfaces, list):
                for iface in interfaces:
                    name = iface.get("name", "unknown")
                    state = "ONLINE" if iface.get("state", {}).get("link_state") == "LINK_STATE_UP" else "OFFLINE"
                    aliases = [a.get("address") for a in iface.get("state", {}).get("aliases", []) if a.get("address")]
                    
                    send_state_to_gateway(
                        f"truenas-interface-{name}",
                        f"TrueNAS Interface {name}",
                        "binary_sensor",
                        state,
                        {
                            "link_state": iface.get("state", {}).get("link_state", "UNKNOWN"),
                            "speed": iface.get("state", {}).get("active_media_speed", "unknown"),
                            "ip_addresses": aliases
                        }
                    )
        except Exception as if_err:
            logger.warning(f"Failed to query TrueNAS interfaces: {if_err}")

        # Report overall healthy status
        send_state_to_gateway("status", "TrueNAS Connection Status", "binary_sensor", "ONLINE")
        logger.info("Successfully fetched and forwarded all TrueNAS monitoring metrics.")

    except Exception as e:
        err_msg = f"Error in TrueNAS monitoring loop: {e}"
        logger.error(f"{err_msg}\n{traceback.format_exc()}")
        send_log_to_gateway("ERROR", err_msg)
        send_state_to_gateway("status", "TrueNAS Connection Status", "binary_sensor", "OFFLINE", {
            "error_message": str(e)
        })
    finally:
        if ws_client:
            ws_client.close()
            ws_client = None


def main():
    logger.info("Initializing TrueNAS WebSocket Monitor loop...")
    
    if not API_KEY:
        msg = "Missing required authentication settings: PLUGIN_API_KEY must be defined."
        logger.error(msg)
        send_log_to_gateway("FATAL", msg)
        send_state_to_gateway("status", "TrueNAS Connection Status", "binary_sensor", "OFFLINE", {
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
