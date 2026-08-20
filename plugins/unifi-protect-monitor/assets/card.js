class UnifiProtectMonitorCard extends HTMLElement {
    constructor() {
        super();
        this.attachShadow({ mode: 'open' });
    }

    connectedCallback() {
        this.shadowRoot.innerHTML = `
      <style>
        :host {
          display: block;
          font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
          color: var(--text-primary, #f4f4f5);
        }
        .card {
          background-color: var(--bg-secondary, #18181b);
          border: 1px solid var(--border-soft, #27272a);
          border-radius: 8px;
          padding: 18px;
          transition: border-color 0.2s;
        }
        .card:hover {
          border-color: var(--border-active, #3f3f46);
        }
        .header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          margin-bottom: 15px;
        }
        .title-group {
          display: flex;
          align-items: center;
          gap: 10px;
        }
        .title {
          font-size: 1.05rem;
          font-weight: 700;
          margin: 0;
        }
        .icon {
          width: 24px;
          height: 24px;
        }
        .status {
          font-size: 0.75rem;
          font-weight: 600;
          padding: 3px 8px;
          border-radius: 9999px;
          text-transform: uppercase;
        }
        .status.online {
          color: #10b981;
          background-color: rgba(16, 185, 129, 0.08);
          border: 1px solid rgba(16, 185, 129, 0.15);
        }
        .status.offline {
          color: #f43f5e;
          background-color: rgba(244, 63, 94, 0.08);
          border: 1px solid rgba(244, 63, 94, 0.15);
        }
        .metrics-grid {
          display: grid;
          grid-template-columns: repeat(2, 1fr);
          gap: 12px;
          margin-bottom: 15px;
        }
        .metric-card {
          background-color: rgba(39, 39, 42, 0.2);
          border: 1px solid var(--border-soft, #27272a);
          border-radius: 6px;
          padding: 12px;
        }
        .metric-label {
          font-size: 0.75rem;
          color: var(--text-secondary, #a1a1aa);
          margin-bottom: 4px;
        }
        .metric-value {
          font-size: 1.35rem;
          font-weight: 700;
        }
        .section-title {
          font-size: 0.8rem;
          font-weight: 600;
          color: var(--text-secondary, #a1a1aa);
          margin: 15px 0 8px 0;
          text-transform: uppercase;
          letter-spacing: 0.05em;
          border-top: 1px solid var(--border-soft, #27272a);
          padding-top: 12px;
        }
        table {
          width: 100%;
          border-collapse: collapse;
          font-size: 0.8rem;
        }
        th, td {
          padding: 6px;
          text-align: left;
          border-bottom: 1px solid var(--border-soft, #27272a);
        }
        th {
          color: var(--text-secondary, #a1a1aa);
          font-weight: 500;
        }
      </style>
      <div class="card">
        <div class="header">
          <div class="title-group">
            <img class="icon" src="assets/icon.svg" alt="UniFi Protect Logo" />
            <h3 class="title">UniFi Protect</h3>
          </div>
          <span class="status online" id="protect-status">Online</span>
        </div>
        <div class="metrics-grid">
          <div class="metric-card">
            <div class="metric-label">Online Cameras</div>
            <div class="metric-value" id="cams-count">--</div>
          </div>
          <div class="metric-card">
            <div class="metric-label">Disk Storage</div>
            <div class="metric-value" id="disk-count">--</div>
          </div>
        </div>
        <div class="section-title">Cameras Inventory</div>
        <table>
          <thead>
            <tr>
              <th>Camera Name</th>
              <th>Model</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody id="cams-tbody">
            <tr>
              <td colspan="3" style="text-align: center; color: var(--text-secondary, #a1a1aa);">Loading cameras...</td>
            </tr>
          </tbody>
        </table>
      </div>
    `;
    }
}
customElements.define('unifi-protect-monitor-card', UnifiProtectMonitorCard);
