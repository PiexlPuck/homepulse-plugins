# UniFi Access Monitor Plugin for HomePulse

This plugin connects to your UniFi Access application controller to track access control readers adoption and credentials events.

## 1. Prerequisites and Setup
To retrieve information, you must generate a local Integration API Key.

### Recommended Configuration
1. Log in to your UniFi Console.
2. Select the **Access Application**.
3. Go to **Settings** > **System** > **Integrations**.
4. Generate a new API Key (e.g. `HomePulse integration API Key`).
5. Copy the generated key.

## 2. Configuration Settings
Define the following environment variables (or configure them in the HomePulse interface):

| Setting | Env Variable | Type | Default | Description |
|---|---|---|---|---|
| `unifi_url` | `PLUGIN_UNIFI_URL` | String | `https://192.168.1.1/` | Base URL of UniFi OS Console |
| `unifi_api_key` | `PLUGIN_UNIFI_API_KEY` | Password | (required) | UniFi Access Integration API token |
| `interval` | `PLUGIN_INTERVAL` | Integer | `30` | Sync interval in seconds |

## 3. Metrics Forwarded
- **UniFi Access Devices** (`unifi-access-devices`): Dynamic data-table listing reader/hub devices name, model/type, IP, and adoption network status.
- **UniFi Access Events Log** (`unifi-access-events`): Dynamic data-table detailing recent entrance unlocks, access grants or denials, and door events with location, type, and user ID.
