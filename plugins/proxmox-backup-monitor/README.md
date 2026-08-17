# Proxmox Backup Server (PBS) Monitor Plugin Setup Guide

This plugin monitors physical host metrics (CPU, Memory, Swap, Uptime), datastore sizes, Garbage Collection (GC) status, physical disks (wearout & health status), recent task logs (active counts & last backup status), core daemon service status, remote sync replication configs, and subscription keys.

## 1. Create API Token in Proxmox Backup Server
1. Log in to your Proxmox Backup Server Web GUI on port `8007`.
2. Navigate to **Configuration > Access Control > API Tokens**.
3. Click **Add**.
4. Select the target **User** (e.g. `root@pam`).
5. Set a **Token ID** (e.g., `HomePulse`).
6. Click **Add**. Copy and save the displayed **Token Secret** value immediately.

## 2. API Token Permissions (Required)
For security, PBS tokens do not inherit any permissions by default. You must explicitly configure access rights:
1. Under **Configuration > Access Control**, click the **Permissions** tab.
2. Click **Add > API Token Permission**.
3. Set fields as follows:
   - **Path**: `/` (required to read global server statistics, CPU, and all datastores).
   - **Token**: `root@pam!HomePulse` (select your corresponding created token name).
   - **Role**: **Audit** (grants read-only permission suitable for monitoring).
4. Click **Add**.

## 3. Configuration Fields
Specify these fields in the HomePulse Dashboard configuration UI:
- **Proxmox Backup Server URL**: E.g. `https://192.168.15.100:8007/api2/json/`
- **PBS Node Name**: Hostname of the target PBS node (default: `localhost`).
- **API Token ID**: Formatted as `username@realm!tokenid` (e.g. `root@pam!HomePulse`).
- **API Token Secret**: The secret key you copied.
- **Sync Interval (s)**: Metric polling timer in seconds (default: `30`s).

## Note on Separator Format
Proxmox Backup Server uses a **colon (`:`)** separator character to authenticate API token headers, which differs from PVE's usage of equals sign (`=`):
`Authorization: PBSAPIToken=username@realm!tokenid:tokensecret`
