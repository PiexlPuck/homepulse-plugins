# Synology Monitor Plugin for HomePulse

This plugin connects securely to Synology DSM WebAPI services to monitor resource utilization (CPU, memory, storage pools, system health metrics).

## 1. Prerequisites and Setup
To authenticate, you must use a Synology DSM local username and password.

### Recommended Configuration
1. Log in to your Synology DSM.
2. Open **Control Panel** > **User & Group**.
3. Create a dedicated system user (e.g., `homepulse_monitor`) with **Read-Only** access.
4. Ensure the user has permissions to access the DSM application. Wait, standard WebAPI calls require generic GUI logon, but no specific administrator privileges are needed for base utilization metrics.

## 2. Configuration Settings
Define the following environment variables (or configure them in the HomePulse plugin settings page):

| Setting | Env Variable | Type | Default | Description |
|---|---|---|---|---|
| `synology_ip` | `PLUGIN_SYNOLOGY_IP` | String | `192.168.0.100` | IP Address or Hostname of Synology DSM |
| `synology_user` | `PLUGIN_SYNOLOGY_USER` | String | `admin` | Local username |
| `synology_password` | `PLUGIN_SYNOLOGY_PASSWORD` | Password | (required) | Local password |
| `interval` | `PLUGIN_INTERVAL` | Integer | `30` | Sync interval in seconds |

## 3. Metrics Forwarded
- **Synology System Status** (`synology-system-status`): ONLINE/OFFLINE, hardware temperature, model name, firmware version.
- **Synology CPU Uptime** (`synology-cpu-usage`): System CPU usage percentage.
- **Synology Memory Usage** (`synology-memory-usage`): Total system RAM percentage used.
- **Synology Storage Summary** (`synology-storage-summary`): Dynamic data-table displaying volume status, capacity, and usage metrics.
