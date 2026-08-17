# Proxmox VE Monitor Plugin Setup Guide

This plugin monitors host resource metrics (CPU, Memory, Disk, Uptime) and guest (VM/LXC) statuses from a Proxmox VE (PVE) server.

## 1. Create API Token in Proxmox VE
For security, do not use your primary root password. Install utilizing a restricted PVE API Token:
1. Log in to your Proxmox VE Administration Web GUI.
2. In the left navigation, select **Datacenter**, then click **Permissions > API Tokens**.
3. Click **Add**.
4. Choose the target **User** (e.g., `root@pam` or a dedicated local user).
5. Enter a **Token ID** descriptor name (e.g., `HomePulse`).
6. Uncheck **Privilege Separation** unless you plan to assign permissions explicitly to the token itself.
7. Click **Add**. Copy the displayed **Token Secret** value immediately (it will not be shown again).

## 2. Assign Permissions (Required)
If you checked *Privilege Separation*, or if the user account requires role assignment:
1. Under **Datacenter**, go to **Permissions**.
2. Click **Add > API Token Permission**.
3. Set **Path** to `/` (required to read global cluster statistics, CPU, and guest lists).
4. Select the matching **API Token** from the dropdown (`user@realm!tokenid`).
5. Set **Role** to **PVEAuditor** (read-only audit parameters) or **PVEMonitor** (standard resource monitors).
6. Click **Add**.

## 3. Configuration Fields
Specify these fields in the HomePulse Dashboard configuration UI:
- **PVE API URL**: E.g. `https://192.168.0.100:8006/api2/json/`
- **PVE Node Name**: Name of the target PVE host node (default: `pve`).
- **PVE API Token ID**: Formatted as `username@realm!tokenid` (e.g. `root@pam!HomePulse`).
- **PVE API Token Secret**: The secret key you copied.
- **Sync Interval (s)**: Metric polling timer in seconds (default: `30`s).
