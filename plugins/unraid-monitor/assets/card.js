class UnraidMonitorCard extends HTMLElement {
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
        .status.started {
          color: #10b981;
          background-color: rgba(16, 185, 129, 0.08);
          border: 1px solid rgba(16, 185, 129, 0.15);
        }
        .status.stopped {
          color: #f43f5e;
          background-color: rgba(244, 63, 94, 0.08);
          border: 1px solid rgba(244, 63, 94, 0.15);
        }
        .progress-container {
          margin-bottom: 15px;
        }
        .progress-label {
          display: flex;
          justify-content: space-between;
          font-size: 0.8rem;
          color: var(--text-secondary, #a1a1aa);
          margin-bottom: 5px;
        }
        .progress-bar {
          background-color: var(--bg-modifier, #27272a);
          height: 8px;
          border-radius: 4px;
          overflow: hidden;
        }
        .progress-fill {
          background-color: #10b981;
          height: 100%;
          width: 0%;
          transition: width 0.3s;
        }
        .stats-grid {
          display: grid;
          grid-template-columns: repeat(2, 1fr);
          gap: 10px;
          margin-bottom: 15px;
        }
        .stat-item {
          background-color: rgba(39, 39, 42, 0.3);
          border: 1px solid var(--border-soft, #27272a);
          border-radius: 6px;
          padding: 10px;
          text-align: center;
        }
        .stat-label {
          font-size: 0.75rem;
          color: var(--text-secondary, #a1a1aa);
        }
        .stat-val {
          font-size: 1.15rem;
          font-weight: 700;
          margin-top: 3px;
        }
      </style>
      <div class="card">
        <div class="header">
          <div class="title-group">
            <img class="icon" src="assets/icon.svg" alt="Unraid Icon" />
            <h3 class="title">Unraid Storage Server</h3>
          </div>
          <span class="status started" id="array-state">Started</span>
        </div>
        <div class="progress-container">
          <div class="progress-label">
            <span>Array Usage</span>
            <span id="array-pct">--%</span>
          </div>
          <div class="progress-bar">
            <div class="progress-fill" id="array-fill"></div>
          </div>
        </div>
        <div class="stats-grid">
          <div class="stat-item">
            <div class="stat-label">Containers</div>
            <div class="stat-val" id="containers-count">--</div>
          </div>
          <div class="stat-item">
            <div class="stat-label">Virtual Machines</div>
            <div class="stat-val" id="vms-count">--</div>
          </div>
        </div>
      </div>
    `;
    }
}
customElements.define('unraid-monitor-card', UnraidMonitorCard);
