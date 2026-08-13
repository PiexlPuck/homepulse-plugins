# HomePulse Plugins

This repository is designed to host community-built and official plugins for **HomePulse**, a modular dashboard and monitoring system.

## About Plugins

HomePulse features a manifest-driven plugin loading architecture:
- Each folder under `/plugins` represents an isolated plugin.
- A plugin must include a `manifest.json` defining metadata and config schemas, and a `main.py` entrypoint.
- Individual plugins run in decoupled environments with distinct `requirements.txt` dependencies.

## Target Services

Add-on plugins will monitor infrastructure, hypervisors, and web services, including:
- **Virtualization & Hypervisors**: Proxmox VE (PVE), Proxmox Mail Gateway (PMG), Proxmox Backup Server (PBS), Unraid, TrueNAS (CORE & SCALE), TrueCommand
- **Services & Proxies**: Nginx (Standalone & Proxy Manager), Dockhand (Docker monitoring)

## Installation

Installation and lifecycle management of these plugins is handled automatically by the main **HomePulse** application configuration panel.
