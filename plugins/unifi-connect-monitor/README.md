# UniFi Connect Monitor Plugin for HomePulse

This plugin connects and queries statistics about UniFi Connect screens/displays, LED panels, and EV chargers adoption and connection statuses.

## 1. Prerequisites and Setup
To retrieve information, you must use local administrator credentials.

### Recommended Configuration
1. Log in to your UniFi Site Manager or the local Console IP.
2. Go to **OS Settings** > **Admins & Users**.
3. Create a dedicated local user (e.g. `homepulse_monitor`). We recommend granting **Viewer** (Read-Only) permissions instead of administrative permissions.

## 2. Configuration Settings
Define the following environment variables (or configure them in the HomePulse interface):

| Setting | Env Variable | Type | Default | Description |
|---|---|---|---|---|
| `unifi_ip` | `PLUGIN_UNIFI_IP` | String | `192.168.1.1` | IP Address or Hostname of UniFi OS Console |
| `unifi_user` | `PLUGIN_UNIFI_USER` | String | `admin` | Local username |
| `unifi_password` | `PLUGIN_UNIFI_PASSWORD` | Password | (required) | Local password |
| `interval` | `PLUGIN_INTERVAL` | Integer | `30` | Sync interval in seconds |

## 3. Metrics Forwarded
- **UniFi Connect Displays** (`unifi-connect-displays`): Dynamic data-table listing displays ID, name, hardware model, connection status, and uptime.
