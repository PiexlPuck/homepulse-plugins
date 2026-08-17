# Unraid OS Monitor Plugin Setup Guide

This plugin monitors array status, disk temperatures, Docker container lists (including autostart configuration), VM lists (including autostart configurations), shares count, CPU load details, and virtualization counts on Unraid servers.

## 1. Local GraphQL API Access
Unraid systems typically require a GraphQL backend API server configuration (such as Dynamix or standard Docker API setups) handling system queries:
1. Ensure the GraphQL support server is active and accessible on your local network.
2. Note the target URL (e.g., `http://<your-unraid-ip>/graphql`).
3. Generate or retrieve the secure **API Key** required for authentication header tokens.

## 2. Configuration Fields
Specify these fields in the HomePulse Dashboard configuration UI:
- **Unraid GraphQL API URL**: The full endpoint URL (default: `http://192.168.0.220/graphql`).
- **Unraid API Key**: The token key credential for GraphQL query headers.
- **Sync Interval (s)**: Metric polling timer in seconds (default: `30`s).
