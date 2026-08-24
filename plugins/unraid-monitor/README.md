# Unraid OS Monitor Plugin Setup Guide

This plugin monitors array status, disk temperatures, Docker container lists (including autostart configuration), VM lists (including autostart configurations), shares count, CPU load details, and virtualization counts on Unraid servers.

## 1. Local GraphQL API Access
Depending on your Unraid OS version, the GraphQL endpoint is enabled differently:

* **Unraid OS 7.2+ (Native)**: 
  1. Log in to the Unraid WebGUI.
  2. Navigate to **Settings > Management Access > API Keys**.
  3. Generate an API Key and copy its value.
* **Unraid OS 6.10 to 7.1**:
  1. Install the official **Unraid Connect** (formerly *My Servers*) plugin from the Apps tab.
  2. Ensure the local GraphQL service is running and accessible on your local network.
  3. Generate or retrieve the connection's secure **API Key** credentials.

## 2. Configuration Fields
Specify these fields in the HomePulse Dashboard configuration UI:
- **Unraid IP / Host**: The host IP address or hostname (default: `192.168.0.220`).
- **Unraid API Key**: The token key credential for GraphQL query headers.
- **Sync Interval (s)**: Metric polling timer in seconds (default: `30`s).
