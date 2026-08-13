class TrueNasCard extends HTMLElement {
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
        .metrics {
          display: grid;
          grid-template-columns: repeat(2, 1fr);
          gap: 10px;
          margin-bottom: 15px;
        }
        .metric-item {
          display: flex;
          flex-direction: column;
        }
        .metric-label {
          font-size: 0.75rem;
          color: var(--text-secondary, #a1a1aa);
          margin-bottom: 4px;
        }
        .metric-value {
          font-size: 1.15rem;
          font-weight: 700;
        }
        .pools {
          border-top: 1px solid var(--border-soft, #27272a);
          padding-top: 12px;
          margin-bottom: 10px;
        }
        .pool-item {
          display: flex;
          align-items: center;
          justify-content: space-between;
          font-size: 0.85rem;
          margin-bottom: 6px;
        }
        .alert-badge {
          display: inline-flex;
          align-items: center;
          font-size: 0.75rem;
          font-weight: 600;
          padding: 2px 6px;
          border-radius: 4px;
          background-color: #ef4444;
          color: white;
        }
      </style>
      <div class="card">
        <div class="header">
          <div class="title-group">
            <img class="icon" src="assets/icon.svg" alt="TrueNAS Icon" />
            <h3 class="title">TrueNAS System Monitor</h3>
          </div>
          <span class="status online" id="status-badge">Online</span>
        </div>
        <div class="metrics">
          <div class="metric-item">
            <span class="metric-label">OS Version</span>
            <span class="metric-value" id="version-val">--</span>
          </div>
          <div class="metric-item">
            <span class="metric-label">Memory</span>
            <span class="metric-value" id="mem-val">-- GB</span>
          </div>
        </div>
        <div class="pools" id="pools-container">
          <!-- Pools list will render here -->
        </div>
        <div id="alerts-container" style="margin-top: 8px; display: none;">
          <span class="alert-badge" id="alerts-badge">0 Alerts</span>
        </div>
      </div>
    `;
    }
}
customElements.define('truenas-card', TrueNasCard);
