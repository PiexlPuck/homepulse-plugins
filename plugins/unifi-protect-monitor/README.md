# UniFi Protect Monitor Plugin for HomePulse

This plugin connects to your UniFi Protect application to track camera adoption/connection statuses and recording NVR disk status metrics.

## 1. Prerequisites and Setup
To retrieve information, you must generate a local Integration API Key.

### Recommended Configuration
1. Log in to your UniFi Console.
2. Select the **Protect Application**.
3. Go to **Settings** > **System** > **Integrations**.
4. Generate a new API Key (e.g. `HomePulse integration API Key`).
5. Copy the generated key. (Ensure you store it securely, as you will not be able to view it again).

## 2. Configuration Settings
Define the following environment variables (or configure them in the HomePulse interface):

| Setting | Env Variable | Type | Default | Description |
|---|---|---|---|---|
| `unifi_url` | `PLUGIN_UNIFI_URL` | String | `https://192.168.1.1/` | Base URL of UniFi OS Console |
| `unifi_api_key` | `PLUGIN_UNIFI_API_KEY` | Password | (required) | UniFi Protect Integration API key |
| `interval` | `PLUGIN_INTERVAL` | Integer | `30` | Sync interval in seconds |

## 3. Metrics Forwarded
- **UniFi Protect Cameras** (`unifi-protect-cameras`): Dynamic data-table of all cameras listing their user-defined name, model, connection state (online/offline), and MAC address.
- **UniFi Protect NVR Disks** (`unifi-protect-nvr`): Dynamic data-table of all active NVR disk bays showing disk name, model, storage capacity, and SMART status.
