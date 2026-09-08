// Live Interview Controls Module
// Handles global controls, transparency, window management, and presets

export class LiveControls {
    constructor() {
        this.transparencyConfig = {
            bgTransparency: 0.80, // Background transparency (0-1) - 80% opacity
            contentTransparency: 0.20, // Content transparency (0-1) - 80% opacity
            codeTransparency: 0.50 // Code block transparency (0-1) - 50% opacity for readability
        };
        
        this.setupGlobalFunctions();
    }

    // Transparency configuration methods
    setBackgroundTransparency(transparency) {
        this.transparencyConfig.bgTransparency = Math.max(0, Math.min(1, transparency));
        this.updateCSSTransparency();
    }

    setContentTransparency(transparency) {
        this.transparencyConfig.contentTransparency = Math.max(0, Math.min(1, transparency));
        this.updateCSSTransparency();
    }

    setCodeTransparency(transparency) {
        this.transparencyConfig.codeTransparency = Math.max(0, Math.min(1, transparency));
        this.updateCSSTransparency();
    }

    // Update CSS transparency variables
    updateCSSTransparency() {
        const root = document.documentElement;
        root.style.setProperty('--bg-transparency', this.transparencyConfig.bgTransparency);
        root.style.setProperty('--content-transparency', this.transparencyConfig.contentTransparency);
        root.style.setProperty('--code-transparency', this.transparencyConfig.codeTransparency);
    }

    // Windows-level transparency controls
    async setWindowTransparency(transparency) {
        try {
            const response = await fetch('/api/transparency', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ transparency: transparency })
            });
            const result = await response.json();
            if (result.success) {
                console.log(`🪟 ${result.message}`);
                return true;
            } else {
                console.error('❌ Failed to set window transparency');
                return false;
            }
        } catch (error) {
            console.error('❌ Error setting window transparency:', error);
            return false;
        }
    }

    async setWindowTransparencyPercent(percent) {
        try {
            const response = await fetch('/api/transparency/percent', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ percent: percent })
            });
            const result = await response.json();
            if (result.success) {
                console.log(`🪟 ${result.message}`);
                return true;
            } else {
                console.error('❌ Failed to set window transparency');
                return false;
            }
        } catch (error) {
            console.error('❌ Error setting window transparency:', error);
            return false;
        }
    }

    // Always-on-top controls
    async setAlwaysOnTop(onTop = true) {
        try {
            const response = await fetch('/api/window/always-on-top', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ on_top: onTop })
            });
            const result = await response.json();
            if (result.success) {
                console.log(`📌 ${result.message}`);
                return true;
            }
            return false;
        } catch (error) {
            console.error('❌ Error setting always on top:', error);
            return false;
        }
    }

    // Window transparency presets
    async setInterviewMode() {
        try {
            const response = await fetch('/api/transparency/presets/transparent', {
                method: 'POST'
            });
            const result = await response.json();
            if (result.success) {
                console.log('🎯 Interview mode activated - window is now 40% opaque');
                return true;
            }
            return false;
        } catch (error) {
            console.error('❌ Error setting interview mode:', error);
            return false;
        }
    }

    async setSemiTransparentMode() {
        try {
            const response = await fetch('/api/transparency/presets/semi-transparent', {
                method: 'POST'
            });
            const result = await response.json();
            if (result.success) {
                console.log('🌫️ Semi-transparent mode activated - window is now 70% opaque');
                return true;
            }
            return false;
        } catch (error) {
            console.error('❌ Error setting semi-transparent mode:', error);
            return false;
        }
    }

    async setOpaqueMode() {
        try {
            const response = await fetch('/api/transparency/presets/opaque', {
                method: 'POST'
            });
            const result = await response.json();
            if (result.success) {
                console.log('🎨 Opaque mode activated - window is now 100% opaque');
                return true;
            }
            return false;
        } catch (error) {
            console.error('❌ Error setting opaque mode:', error);
            return false;
        }
    }

    async getTransparencyInfo() {
        try {
            const response = await fetch('/api/transparency');
            const info = await response.json();
            console.log('🪟 Window Transparency Info:', info);
            return info;
        } catch (error) {
            console.error('❌ Error getting transparency info:', error);
            return null;
        }
    }

    // CSS Transparency presets
    setMinimalMode() {
        this.setBackgroundTransparency(0.95);
        this.setContentTransparency(0.05);
        this.setCodeTransparency(0.25);
        console.log('👤 Minimal mode activated');
    }

    setGhostMode() {
        this.setBackgroundTransparency(0.98);
        this.setContentTransparency(0.02);
        this.setCodeTransparency(0.15);
        console.log('👻 Ghost mode activated - maximum transparency');
    }

    setStealthMode() {
        this.setBackgroundTransparency(0.90);
        this.setContentTransparency(0.10);
        this.setCodeTransparency(0.35);
        console.log('🥷 Stealth mode activated');
    }

    setDefaultTransparency() {
        this.setBackgroundTransparency(0.80);
        this.setContentTransparency(0.20);
        this.setCodeTransparency(0.50);
        console.log('🎨 Default transparency restored (80% opacity)');
    }

    // Setup global window functions
    setupGlobalFunctions() {
        // Basic transparency controls
        window.setBackgroundTransparency = (transparency) => {
            this.setBackgroundTransparency(transparency);
            console.log(`🌙 Background transparency set to ${transparency}`);
        };

        window.setContentTransparency = (transparency) => {
            this.setContentTransparency(transparency);
            console.log(`🖼️ Content transparency set to ${transparency}`);
        };

        window.setCodeTransparency = (transparency) => {
            this.setCodeTransparency(transparency);
            console.log(`💻 Code transparency set to ${transparency}`);
        };

        // CSS Transparency presets
        window.setMinimalMode = () => this.setMinimalMode();
        window.setGhostMode = () => this.setGhostMode();
        window.setStealthMode = () => this.setStealthMode();
        window.setDefaultTransparency = () => this.setDefaultTransparency();

        // Windows-level transparency
        window.setWindowTransparency = (transparency) => this.setWindowTransparency(transparency);
        window.setWindowTransparencyPercent = (percent) => this.setWindowTransparencyPercent(percent);

        // Window transparency presets
        window.setInterviewMode = () => this.setInterviewMode();
        window.setSemiTransparentMode = () => this.setSemiTransparentMode();
        window.setOpaqueMode = () => this.setOpaqueMode();
        window.getTransparencyInfo = () => this.getTransparencyInfo();

        // Always-on-top controls
        window.setAlwaysOnTop = (onTop = true) => this.setAlwaysOnTop(onTop);
        window.enableAlwaysOnTop = () => this.setAlwaysOnTop(true);
        window.disableAlwaysOnTop = () => this.setAlwaysOnTop(false);
    }

    // Initialize transparency settings
    initialize() {
        this.updateCSSTransparency();
        console.log('🎛️ Live controls initialized');
    }

    // Get current configuration
    getConfig() {
        return { ...this.transparencyConfig };
    }
} 