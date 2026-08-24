# Nginx Proxy Manager (NPM) Monitor Plugin Setup Guide

This plugin monitors hosts statuses (Proxy, Redirection, Stream) and forwards telemetry from Nginx Proxy Manager.

## 1. User Credentials
This plugin connects using JWT tokens via the NPM administrator login:
1. Log in to your Nginx Proxy Manager Web UI (typically port `81`).
2. Verify or update your Admin User email and password under **Users > Edit**.
3. Use those credentials in your HomePulse plugin settings fields.

## 2. Configuration Fields
Specify these fields in the HomePulse Dashboard configuration UI:
- **NPM IP / Host**: The host IP address or hostname (default: `192.168.0.142`).
- **NPM Admin Email**: Administrative email login (default: `admin@example.com`).
- **NPM Admin Password**: Login password.
- **Sync Interval (s)**: Metric polling timer in seconds (default: `30`s).
