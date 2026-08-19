# TrueNAS Monitor Plugin Setup Guide

This plugin monitors server specs, active alerts, drive statuses, ZFS pool health, system services running state, VM counts, and network interfaces on TrueNAS systems. It connects using the **JSON-RPC 2.0 over WebSocket** middleware interface, compatible with both **TrueNAS Core** and **TrueNAS SCALE** (including deprecation safety for version 26.04+).

## 1. Retrieve API Key inside TrueNAS Web UI
You must generate a bearer API Token inside the Web UI:

### For TrueNAS Core
1. Log in to your TrueNAS Core administration page.
2. In the left navigation, select **System > API Keys**.
3. Click **Add** (API key icon).
4. Assign a descriptive **Name** (e.g., `HomePulse`).
5. Click **Submit**. Copy and save the generated **API Key** value.

### For TrueNAS SCALE
1. Log in to your TrueNAS SCALE administration page.
2. Go to **Credentials > API Keys** in the navigation panel.
3. Click the **Add** button in the top right.
4. Enter a metadata **Name** name (e.g., `HomePulse`).
5. Click **Save** and copy the displayed **API Key**.

> [!IMPORTANT]  
> TrueNAS enforces secure HTTPS for remote API keys. It is highly recommended to configure an SSL certificate on the TrueNAS web server and target `https://` URLs to protect credentials over encrypted `wss://` connections.

## 2. Configuration Fields
Specify these fields in the HomePulse Dashboard configuration UI:
- **TrueNAS REST API URL**: The host URL (default: `http://192.168.0.100/api/v2.0/` or `https://192.168.0.100/`). The plugin automatically resolves this address to point to the `/websocket` communication path.
- **TrueNAS API Key**: The token key credential generated inside the TrueNAS interface.
- **Sync Interval (s)**: Metric polling timer in seconds (default: `30`s).
