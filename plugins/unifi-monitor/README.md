# UniFi Core Console Monitor Plugin for HomePulse

This plugin connects directly to UniFi OS consoles (UDM, UDR, Cloud Keys) to track base hardware stats (CPU, RAM, uptime) and active application containers (Network, Protect, Access, Talk, Connect).

## 1. Prerequisites and Setup
To retrieve information from the console, you can use local admin credentials.

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
| `interval` | `PLUGIN_INTERVAL` | Integer | `30` | Sync interval in seconds |

## 3. Metrics Forwarded
- **UniFi Console Status** (`unifi-status`): ONLINE/OFFLINE, hostname, firmware system versions.
- **UniFi Console CPU Load** (`unifi-console-cpu`): CPU utilization percentage.
- **UniFi Console Memory Usage** (`unifi-console-memory`): Memory utilization percentage.
- **UniFi Active Applications** (`unifi-active-applications`): Dynamic data-table of all running applications on the console and their statuses.
