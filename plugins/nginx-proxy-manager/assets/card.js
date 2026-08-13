class NpmMonitorCard extends HTMLElement {
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
        .statistics-grid {
          display: grid;
          grid-template-columns: repeat(3, 1fr);
          gap: 10px;
        }
        .stat-item {
          background-color: rgba(39, 39, 42, 0.2);
          border: 1px solid var(--border-soft, #27272a);
          border-radius: 6px;
          padding: 12px;
          text-align: center;
        }
        .stat-label {
          font-size: 0.75rem;
          color: var(--text-secondary, #a1a1aa);
          margin-bottom: 4px;
        }
        .stat-value {
          font-size: 1.35rem;
          font-weight: 700;
        }
        .details-section {
          border-top: 1px solid var(--border-soft, #27272a);
          padding-top: 12px;
          margin-top: 15px;
        }
        .details-row {
          display: flex;
          justify-content: space-between;
          font-size: 0.85rem;
          margin-bottom: 5px;
        }
      </style>
      <div class="card">
        <div class="header">
          <div class="title-group">
            <img class="icon" src="assets/icon.svg" alt="NPM Icon" />
            <h3 class="title">Nginx Proxy Manager</h3>
          </div>
          <span class="status online" id="npm-state">Online</span>
        </div>
        <div class="statistics-grid">
          <div class="stat-item">
            <span class="stat-label">Proxies</span>
            <span class="stat-value" id="proxies-val">--</span>
          </div>
          <div class="stat-item">
            <span class="stat-label">Redirects</span>
            <span class="stat-value" id="redirects-val">--</span>
          </div>
          <div class="stat-item">
            <span class="stat-label">Streams</span>
            <span class="stat-value" id="streams-val">--</span>
          </div>
        </div>
        <div class="details-section">
          <div class="details-row">
            <span style="color: var(--text-secondary, #a1a1aa);">Active Hosts</span>
            <span id="active-proxies-val">--</span>
          </div>
        </div>
      </div>
    `;
    }
}
customElements.define('npm-monitor-card', NpmMonitorCard);
