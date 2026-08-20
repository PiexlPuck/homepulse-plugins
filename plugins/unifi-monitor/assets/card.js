class UnifiMonitorCard extends HTMLElement {
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
          color: #3b82f6;
          background-color: rgba(59, 130, 246, 0.08);
          border: 1px solid rgba(59, 130, 246, 0.15);
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
        .apps-section {
          border-top: 1px solid var(--border-soft, #27272a);
          padding-top: 12px;
          margin-top: 15px;
        }
        .apps-title {
          font-size: 0.8rem;
          font-weight: 600;
          color: var(--text-secondary, #a1a1aa);
          margin: 0 0 8px 0;
          text-transform: uppercase;
          letter-spacing: 0.05em;
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
        .app-status {
          font-size: 0.7rem;
          font-weight: 600;
          padding: 2px 6px;
          border-radius: 4px;
        }
        .app-status.online {
          color: #10b981;
          background-color: rgba(16, 185, 129, 0.1);
        }
        .app-status.offline {
          color: #a1a1aa;
          background-color: rgba(161, 161, 170, 0.1);
        }
      </style>
      <div class="card">
        <div class="header">
          <div class="title-group">
            <img class="icon" src="assets/icon.svg" alt="UniFi" />
            <h3 class="title" id="console-name">UniFi Console</h3>
          </div>
          <span class="status online" id="sys-status">Online</span>
        </div>
        <div class="metrics-grid">
          <div class="metric-card">
            <div class="metric-label">CPU Load</div>
            <div class="metric-value" id="cpu-val">--%</div>
          </div>
          <div class="metric-card">
            <div class="metric-label">Memory Usage</div>
            <div class="metric-value" id="mem-val">--%</div>
          </div>
        </div>
        <div class="apps-section">
          <h4 class="apps-title">Active Applications</h4>
          <table>
            <thead>
              <tr>
                <th>Application</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody id="apps-tbody">
              <tr>
                <td colspan="2" style="text-align: center; color: var(--text-secondary, #a1a1aa);">Loading...</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    `;
    }
}
customElements.define('unifi-monitor-card', UnifiMonitorCard);
