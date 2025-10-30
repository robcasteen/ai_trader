/**
 * Real-time event handling using Server-Sent Events (SSE)
 */

class EventManager {
    constructor() {
        this.eventSource = null;
        this.reconnectDelay = 1000;
        this.maxReconnectDelay = 30000;
        this.currentReconnectDelay = this.reconnectDelay;
        this.listeners = {};
        this.connected = false;
    }

    /**
     * Connect to the SSE endpoint
     */
    connect() {
        if (this.eventSource) {
            this.disconnect();
        }

        console.log('[Events] Connecting to event stream...');

        this.eventSource = new EventSource('/api/events');

        this.eventSource.onopen = () => {
            console.log('[Events] Connected to event stream');
            this.connected = true;
            this.currentReconnectDelay = this.reconnectDelay;
            this.updateConnectionStatus(true);
        };

        this.eventSource.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                this.handleEvent(data);
            } catch (e) {
                console.error('[Events] Error parsing event data:', e);
            }
        };

        this.eventSource.onerror = (error) => {
            console.error('[Events] EventSource error:', error);
            this.connected = false;
            this.updateConnectionStatus(false);

            // Reconnect with exponential backoff
            setTimeout(() => {
                console.log(`[Events] Reconnecting in ${this.currentReconnectDelay}ms...`);
                this.connect();
                this.currentReconnectDelay = Math.min(
                    this.currentReconnectDelay * 2,
                    this.maxReconnectDelay
                );
            }, this.currentReconnectDelay);
        };
    }

    /**
     * Disconnect from the event stream
     */
    disconnect() {
        if (this.eventSource) {
            this.eventSource.close();
            this.eventSource = null;
            this.connected = false;
            this.updateConnectionStatus(false);
        }
    }

    /**
     * Handle incoming events
     */
    handleEvent(event) {
        const eventType = event.type;

        console.log('[Events] Received event:', eventType, event);

        // Call registered listeners
        if (this.listeners[eventType]) {
            this.listeners[eventType].forEach(callback => {
                try {
                    callback(event.data);
                } catch (e) {
                    console.error(`[Events] Error in listener for ${eventType}:`, e);
                }
            });
        }

        // Call wildcard listeners
        if (this.listeners['*']) {
            this.listeners['*'].forEach(callback => {
                try {
                    callback(event);
                } catch (e) {
                    console.error('[Events] Error in wildcard listener:', e);
                }
            });
        }

        // Handle specific event types
        switch (eventType) {
            case 'connected':
                console.log('[Events] Server acknowledged connection');
                break;

            case 'trade_executed':
                this.handleTradeExecuted(event.data);
                break;

            case 'signal_generated':
                this.handleSignalGenerated(event.data);
                break;

            case 'balance_updated':
                this.handleBalanceUpdated(event.data);
                break;

            case 'config_changed':
                this.handleConfigChanged(event.data);
                break;

            case 'holdings_updated':
                this.handleHoldingsUpdated(event.data);
                break;

            case 'news_fetched':
                this.handleNewsFetched(event.data);
                break;

            case 'strategy_updated':
                this.handleStrategyUpdated(event.data);
                break;

            case 'error_occurred':
                this.handleErrorOccurred(event.data);
                break;

            case 'bot_status_changed':
                this.handleBotStatusChanged(event.data);
                break;
        }
    }

    /**
     * Register an event listener
     */
    on(eventType, callback) {
        if (!this.listeners[eventType]) {
            this.listeners[eventType] = [];
        }
        this.listeners[eventType].push(callback);
    }

    /**
     * Remove an event listener
     */
    off(eventType, callback) {
        if (this.listeners[eventType]) {
            this.listeners[eventType] = this.listeners[eventType].filter(cb => cb !== callback);
        }
    }

    /**
     * Update connection status indicator
     */
    updateConnectionStatus(connected) {
        const indicator = document.getElementById('connection-status');
        if (indicator) {
            if (connected) {
                indicator.className = 'status-indicator online';
                indicator.title = 'Connected to real-time updates';
            } else {
                indicator.className = 'status-indicator offline';
                indicator.title = 'Disconnected - attempting to reconnect...';
            }
        }
    }

    // Event handlers that trigger UI updates

    handleTradeExecuted(data) {
        console.log('[Events] Trade executed:', data);
        // Refresh trades table
        if (typeof window.refreshTrades === 'function') {
            window.refreshTrades();
        }
        // Show notification
        this.showNotification('trade', `${data.action} ${data.symbol} @ $${data.price}`, 'success');
    }

    handleSignalGenerated(data) {
        console.log('[Events] Signal generated:', data);
        // Refresh signals table
        if (typeof window.refreshSignals === 'function') {
            window.refreshSignals();
        }
    }

    handleBalanceUpdated(data) {
        console.log('[Events] Balance updated:', data);
        // Update balance display
        if (typeof window.refreshBalance === 'function') {
            window.refreshBalance();
        }
    }

    handleConfigChanged(data) {
        console.log('[Events] Config changed:', data);
        // Refresh status display
        if (typeof window.refreshStatus === 'function') {
            window.refreshStatus();
        }
    }

    handleHoldingsUpdated(data) {
        console.log('[Events] Holdings updated:', data);
        // Refresh holdings table
        if (typeof window.refreshHoldings === 'function') {
            window.refreshHoldings();
        }
    }

    handleNewsFetched(data) {
        console.log('[Events] News fetched:', data);
        // Refresh news feed
        if (typeof window.refreshNews === 'function') {
            window.refreshNews();
        }
    }

    handleStrategyUpdated(data) {
        console.log('[Events] Strategy updated:', data);
        // Refresh strategy display
        if (typeof window.refreshStrategy === 'function') {
            window.refreshStrategy();
        }
    }

    handleErrorOccurred(data) {
        console.error('[Events] Error occurred:', data);
        this.showNotification('error', data.message || 'An error occurred', 'danger');
    }

    handleBotStatusChanged(data) {
        console.log('[Events] Bot status changed:', data);
        // Update bot status indicator
        if (typeof window.updateBotStatus === 'function') {
            window.updateBotStatus(data);
        }
    }

    /**
     * Show a toast notification
     */
    showNotification(type, message, variant = 'info') {
        // Create notification element
        const notification = document.createElement('div');
        notification.className = `alert alert-${variant} alert-dismissible fade show notification`;
        notification.setAttribute('role', 'alert');
        notification.innerHTML = `
            <strong>${type.charAt(0).toUpperCase() + type.slice(1)}:</strong> ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
        `;

        // Add to notification container
        let container = document.getElementById('notification-container');
        if (!container) {
            container = document.createElement('div');
            container.id = 'notification-container';
            container.style.position = 'fixed';
            container.style.top = '20px';
            container.style.right = '20px';
            container.style.zIndex = '9999';
            container.style.maxWidth = '400px';
            document.body.appendChild(container);
        }

        container.appendChild(notification);

        // Auto-dismiss after 5 seconds
        setTimeout(() => {
            notification.classList.remove('show');
            setTimeout(() => notification.remove(), 300);
        }, 5000);
    }
}

// Create global event manager instance
window.eventManager = new EventManager();

// Connect when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.eventManager.connect();
});

// Reconnect when page becomes visible
document.addEventListener('visibilitychange', () => {
    if (!document.hidden && !window.eventManager.connected) {
        window.eventManager.connect();
    }
});
