# UniFi Network Monitor Plugin for HomePulse

This plugin connects to the UniFi Network application running on your console to retrieve statistics about connected network clients and adoption state of UniFi hardware devices.

## 1. Prerequisites and Setup
To retrieve information, you can use local admin credentials.

### Recommended Configuration
1. Log in to your UniFi Site Manager or the local Console IP.
2. Go to **OS Settings** > **Admins & Users**.
3. Create a dedicated local user (e.g. `homepulse_monitor`). We recommend granting **Viewer** (Read-Only) permissions instead of administrative permissions.

## 2. Configuration Settings
Define the following environment variables (or configure them in the HomePulse interface):

| Setting | Env Variable | Type | Default | Description |
|---|---|---|---|---|
| `unifi_url` | `PLUGIN_UNIFI_URL` | String | `https://192.168.1.1/` | Base URL of UniFi OS Console / Controller |
| `unifi_user` | `PLUGIN_UNIFI_USER` | String | `admin` | Local username |
| `unifi_password` | `PLUGIN_UNIFI_PASSWORD` | Password | (required) | Local password |
| `unifi_site_id` | `PLUGIN_UNIFI_SITE_ID` | String | `default` | Site identifier (always `default` unless multi-site controller) |
| `interval` | `PLUGIN_INTERVAL` | Integer | `30` | Sync interval in seconds |

## 3. Metrics Forwarded
- **UniFi Network Clients** (`unifi-network-clients`): Dynamic data-table of all active client stations listing MAC address, IP, hostname, connection type (wired/wireless), and RSSI signal level.
- **UniFi Network Devices** (`unifi-network-devices`): Dynamic data-table of all switches, APs, gateway adoption metrics with name, model, state, uptime, CPU and memory load status.
