# UniFi Talk Monitor Plugin for HomePulse

This plugin connects and monitors the UniFi Talk VoIP service, verifying that active local SIP endpoints are registered and displaying configured phone line status listings.

## 1. Prerequisites and Setup

Ubiquiti does not offer a public REST API for UniFi Talk. This plugin integrates using two workarounds:
- **Port Auditing**: Automatically probes the FreeSWITCH SIP signaling port `5060` or `5080` to determine daemon container health status.
- **Provider Webhooks** (optional): Receives SIP registration event calls from external providers (e.g. Twilio, Flowroute, Telnyx).

## 2. Configuration Settings
Define the following environment variables (or configure them in the HomePulse interface):

| Setting | Env Variable | Type | Default | Description |
|---|---|---|---|---|
| `sip_webhook_url` | `PLUGIN_SIP_WEBHOOK_URL` | String | | Optional External SIP Provider Webhook forwarding URL endpoint |
| `interval` | `PLUGIN_INTERVAL` | Integer | `30` | Sync interval in seconds |

## 3. Metrics Forwarded
- **UniFi Talk Status** (`unifi-talk-status`): ONLINE/OFFLINE based on local SIP port queries.
- **UniFi Talk Active Lines** (`unifi-talk-active-lines`): Dynamic data-table of active call tracks, showing line number, assigned team name, and status (e.g., IDLE, BUSY, RINGING).
