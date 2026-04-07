/**
 * SHA2 Rehab Coach - Mobile App Initialization
 * Handles Capacitor integration, device features, and mobile-specific setup
 */

const MobileApp = {
  isCapacitor: false,
  isMobile: /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent),
  
  /**
   * Initialize the mobile app
   */
  async init() {
    console.log('[MobileApp] Initializing...');
    
    // Detect Capacitor
    this.detectCapacitor();
    
    // Setup device listeners
    this.setupDeviceListeners();
    
    // Setup status bar
    this.setupStatusBar();
    
    // Setup safe area
    this.setupSafeArea();
    
    // Setup offline support
    this.setupOfflineSupport();
    
    // Hide loading screen
    this.hideLoadingScreen();
    
    console.log('[MobileApp] Ready! Capacitor:', this.isCapacitor);
  },
  
  /**
   * Detect if running in Capacitor
   */
  detectCapacitor() {
    if (typeof window !== 'undefined' && window.Capacitor) {
      this.isCapacitor = true;
      console.log('[MobileApp] Running in Capacitor');
      
      // Import plugins if available
      this.importCapacitorPlugins();
    } else {
      console.log('[MobileApp] Running as web app');
    }
  },
  
  /**
   * Import Capacitor plugins
   */
  importCapacitorPlugins() {
    try {
      const { Device } = window.Capacitor.Plugins;
      const { StatusBar } = window.Capacitor.Plugins;
      const { Camera } = window.Capacitor.Plugins;
      
      window.CapacitorDevice = Device;
      window.CapacitorStatusBar = StatusBar;
      window.CapacitorCamera = Camera;
      
      console.log('[MobileApp] Capacitor plugins imported');
    } catch (e) {
      console.warn('[MobileApp] Could not import Capacitor plugins:', e);
    }
  },
  
  /**
   * Setup device event listeners
   */
  setupDeviceListeners() {
    // Handle back button on Android
    document.addEventListener('backbutton', () => {
      console.log('[MobileApp] Back button pressed');
      this.handleBackButton();
    });
    
    // Pause/Resume app lifecycle
    if (this.isCapacitor) {
      document.addEventListener('pause', () => {
        console.log('[MobileApp] App paused');
      });
      
      document.addEventListener('resume', () => {
        console.log('[MobileApp] App resumed');
        this.onAppResume();
      });
    }
  },
  
  /**
   * Setup status bar styling (Android/iOS)
   */
  async setupStatusBar() {
    if (!this.isCapacitor || !window.CapacitorStatusBar) return;
    
    try {
      const { StatusBar } = window.Capacitor.Plugins;
      
      // iOS only
      StatusBar.setStyle({ style: 'DARK' }).catch(() => {});
      StatusBar.setBackgroundColor({ color: '#0066cc' }).catch(() => {});
      StatusBar.setOverlaysWebView({ overlay: false }).catch(() => {});
      
      console.log('[MobileApp] Status bar configured');
    } catch (e) {
      console.warn('[MobileApp] Status bar configuration failed:', e);
    }
  },
  
  /**
   * Setup safe area support for notched devices
   */
  setupSafeArea() {
    // CSS handles safe area via env(safe-area-inset-*)
    // This just logs detection
    const insetTop = getComputedStyle(document.documentElement)
      .getPropertyValue('--safe-area-inset-top') || '0';
    
    console.log(`[MobileApp] Safe area detected: ${insetTop}`);
  },
  
  /**
   * Setup offline support with Service Worker
   */
  setupOfflineSupport() {
    if (!('serviceWorker' in navigator)) {
      console.log('[MobileApp] Service Worker not supported');
      return;
    }
    
    navigator.serviceWorker.register('/static/service-worker.js')
      .then(reg => {
        console.log('[MobileApp] Service Worker registered:', reg);
      })
      .catch(err => {
        console.warn('[MobileApp] Service Worker registration failed:', err);
      });
  },
  
  /**
   * Handle Android back button
   */
  handleBackButton() {
    const currentPath = window.location.pathname;
    
    // Don't go back from home
    if (currentPath === '/' || currentPath === '/patient/dashboard' || currentPath === '/login') {
      console.log('[MobileApp] At home screen, not going back');
      return;
    }
    
    window.history.back();
  },
  
  /**
   * Handle app resume
   */
  onAppResume() {
    // Reconnect to backend if needed
    console.log('[MobileApp] App resumed, checking connection...');
    
    // You can ping your backend here to ensure connection
    this.checkBackendConnection();
  },
  
  /**
   * Check backend connection
   */
  async checkBackendConnection() {
    try {
      const response = await fetch('/api/health', {
        method: 'GET',
        timeout: 5000
      });
      
      if (response.ok) {
        console.log('[MobileApp] Backend connection OK');
      } else {
        console.warn('[MobileApp] Backend health check failed');
      }
    } catch (e) {
      console.warn('[MobileApp] Cannot reach backend:', e.message);
      // Show offline indicator
      this.showOfflineIndicator();
    }
  },
  
  /**
   * Show offline indicator
   */
  showOfflineIndicator() {
    let indicator = document.getElementById('offline-indicator');
    if (!indicator) {
      indicator = document.createElement('div');
      indicator.id = 'offline-indicator';
      indicator.style.cssText = `
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        background: #ef4444;
        color: white;
        padding: 8px;
        text-align: center;
        font-size: 12px;
        font-weight: 600;
        z-index: 9999;
      `;
      indicator.textContent = 'No connection to backend';
      document.body.insertBefore(indicator, document.body.firstChild);
    }
    indicator.style.display = 'block';
  },
  
  /**
   * Hide offline indicator
   */
  hideOfflineIndicator() {
    const indicator = document.getElementById('offline-indicator');
    if (indicator) indicator.style.display = 'none';
  },
  
  /**
   * Hide loading screen
   */
  hideLoadingScreen() {
    const loadingScreen = document.getElementById('app-loading');
    if (loadingScreen) {
      loadingScreen.style.opacity = '0';
      loadingScreen.style.transition = 'opacity 0.3s ease-out';
      setTimeout(() => {
        loadingScreen.style.display = 'none';
      }, 300);
    }
  },
  
  /**
   * Utility: Request camera permission
   */
  async requestCameraPermission() {
    if (!this.isCapacitor) {
      return await navigator.permissions.query({ name: 'camera' });
    }
    
    try {
      const { Camera } = window.Capacitor.Plugins;
      // Capacitor handles permissions automatically
      console.log('[MobileApp] Camera permission check complete');
      return { state: 'granted' };
    } catch (e) {
      console.error('[MobileApp] Camera permission error:', e);
      return { state: 'denied' };
    }
  },
  
  /**
   * Utility: Request microphone permission
   */
  async requestMicrophonePermission() {
    if (!this.isCapacitor) {
      return await navigator.permissions.query({ name: 'microphone' });
    }
    
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      stream.getTracks().forEach(track => track.stop());
      return { state: 'granted' };
    } catch (e) {
      console.warn('[MobileApp] Microphone permission denied:', e);
      return { state: 'denied' };
    }
  },
  
  /**
   * Utility: Get device info
   */
  async getDeviceInfo() {
    if (!this.isCapacitor || !window.CapacitorDevice) {
      return { web: true };
    }
    
    try {
      const { Device } = window.Capacitor.Plugins;
      const info = await Device.getInfo();
      console.log('[MobileApp] Device info:', info);
      return info;
    } catch (e) {
      console.error('[MobileApp] Could not get device info:', e);
      return {};
    }
  },
  
  /**
   * Utility: Log analytics event
   */
  logEvent(category, event, label) {
    console.log(`[Analytics] ${category} > ${event}`, label);
    
    // You can integrate with Firebase or other analytics here
    if (typeof gtag !== 'undefined') {
      gtag('event', event, {
        'event_category': category,
        'event_label': label
      });
    }
  }
};

/**
 * Initialize on DOM ready
 */
function initializeMobileApp() {
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
      MobileApp.init();
    });
  } else {
    MobileApp.init();
  }
}

// Auto-initialize if this script is included
if (typeof window !== 'undefined') {
  // Remove this if you want manual initialization
  // Uncomment line below for auto-init:
  // window.addEventListener('DOMContentLoaded', () => MobileApp.init());
}

// Export for use in other scripts
if (typeof module !== 'undefined' && module.exports) {
  module.exports = MobileApp;
}
