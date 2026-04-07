/**
 * SHA2 Mobile Debug Console
 * Intercepts and logs all API calls, errors, and events for debugging
 */

const MobileDebug = {
  logs: [],
  maxLogs: 100,
  
  /**
   * Initialize debug system
   */
  init() {
    console.log('%c[DEBUG] Mobile Debug Console Initialized', 'color: #00ff00; font-weight: bold;');
    
    // Log device info
    this.logDeviceInfo();
    
    // Intercept fetch calls
    this.interceptFetch();
    
    // Intercept console
    this.interceptConsole();
    
    // Error handling
    this.setupErrorHandling();
    
    // Create debug overlay
    this.createDebugOverlay();
  },
  
  /**
   * Log device and environment info
   */
  logDeviceInfo() {
    const info = {
      userAgent: navigator.userAgent,
      viewport: `${window.innerWidth}x${window.innerHeight}`,
      isMobile: /Android|iPhone|iPad/.test(navigator.userAgent),
      timestamp: new Date().toISOString(),
      location: window.location.href,
      protocol: window.location.protocol,
      host: window.location.host
    };
    
    console.log('[DEBUG] Device Info:', info);
    this.addLog('Device Info', info);
  },
  
  /**
   * Intercept all fetch calls
   */
  interceptFetch() {
    const originalFetch = window.fetch;
    
    window.fetch = function(...args) {
      const [resource, config] = args;
      const timestamp = new Date().toISOString();
      
      console.log(`[API] ${config?.method || 'GET'} ${resource} @ ${timestamp}`);
      
      return originalFetch.apply(this, args)
        .then(response => {
          const status = response.status;
          const statusText = response.statusText;
          const message = `${status} ${statusText}`;
          
          console.log(`[API] ✓ Response: ${message}`);
          
          MobileDebug.addLog(`API: ${config?.method || 'GET'} ${resource}`, {
            status,
            statusText,
            timestamp
          });
          
          return response;
        })
        .catch(error => {
          console.error(`[API] ✗ Error: ${resource}`, error);
          
          MobileDebug.addLog(`API ERROR: ${resource}`, {
            error: error.message,
            timestamp
          });
          
          throw error;
        });
    };
    
    console.log('[DEBUG] Fetch interception enabled');
  },
  
  /**
   * Intercept console methods
   */
  interceptConsole() {
    const originalLog = console.log;
    const originalWarn = console.warn;
    const originalError = console.error;
    
    console.log = function(...args) {
      originalLog.apply(console, args);
      MobileDebug.addLog('LOG', args);
    };
    
    console.warn = function(...args) {
      originalWarn.apply(console, args);
      MobileDebug.addLog('WARN', args);
    };
    
    console.error = function(...args) {
      originalError.apply(console, args);
      MobileDebug.addLog('ERROR', args);
    };
  },
  
  /**
   * Setup global error handling
   */
  setupErrorHandling() {
    window.addEventListener('error', (event) => {
      console.error('[GLOBAL ERROR]', event.error);
      MobileDebug.addLog('GLOBAL ERROR', {
        message: event.message,
        filename: event.filename,
        lineno: event.lineno,
        colno: event.colno
      });
    });
    
    window.addEventListener('unhandledrejection', (event) => {
      console.error('[UNHANDLED REJECTION]', event.reason);
      MobileDebug.addLog('UNHANDLED REJECTION', {
        reason: event.reason
      });
    });
  },
  
  /**
   * Add log entry
   */
  addLog(type, data) {
    this.logs.push({
      type,
      data,
      timestamp: new Date().toISOString()
    });
    
    // Keep only last N logs
    if (this.logs.length > this.maxLogs) {
      this.logs.shift();
    }
  },
  
  /**
   * Create debug overlay UI
   */
  createDebugOverlay() {
    // Only on mobile devices
    if (!(/Android|iPhone|iPad/.test(navigator.userAgent))) return;
    
    const overlay = document.createElement('div');
    overlay.id = 'mobile-debug-overlay';
    overlay.style.cssText = `
      position: fixed;
      bottom: 20px;
      right: 20px;
      background: rgba(0, 0, 0, 0.9);
      color: #00ff00;
      padding: 10px 15px;
      border-radius: 8px;
      font-size: 11px;
      font-family: monospace;
      max-width: 250px;
      max-height: 200px;
      overflow-y: auto;
      z-index: 99999;
      border: 2px solid #00ff00;
      box-shadow: 0 0 10px rgba(0, 255, 0, 0.5);
      cursor: pointer;
    `;
    
    // Update every 2 seconds
    setInterval(() => {
      overlay.innerHTML = `
        <div style="margin-bottom: 8px; font-weight: bold; border-bottom: 1px solid #00ff00; padding-bottom: 5px;">
          📱 DEBUG LOG (${this.logs.length})
        </div>
        ${this.logs.slice(-5).map(log => `
          <div style="margin-bottom: 5px; opacity: ${log.type === 'ERROR' ? 1 : 0.8};">
            <span style="color: ${log.type === 'ERROR' ? '#ff0000' : '#ffff00'};">[${log.type}]</span>
            ${typeof log.data === 'string' ? log.data : JSON.stringify(log.data).substring(0, 50)}
          </div>
        `).join('')}
      `;
    }, 2000);
    
    // Toggle visibility on click
    overlay.addEventListener('click', () => {
      overlay.style.display = overlay.style.display === 'none' ? 'block' : 'none';
    });
    
    document.body.appendChild(overlay);
    console.log('[DEBUG] Debug overlay created');
  },
  
  /**
   * Export logs as JSON
   */
  exportLogs() {
    return JSON.stringify(this.logs, null, 2);
  },
  
  /**
   * Print all logs to console
   */
  printAllLogs() {
    console.table(this.logs);
  }
};

// Auto-init when DOM ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => MobileDebug.init());
} else {
  MobileDebug.init();
}
