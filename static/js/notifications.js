/**
 * WindSync Real-Time Notifications & Alerts System - Frontend Module v2.0
 * =====================================================================
 * 
 * Enhanced offline-first notification system with intelligent synchronization,
 * real-time capabilities, and comprehensive offline support.
 * 
 * Features:
 * - Advanced sync manager integration
 * - Priority-based sync queue processing
 * - Conflict resolution for notification states
 * - Enhanced connectivity detection
 * - Batch sync operations
 * - Performance optimizations
 * 
 * @author WindSync Development Team
 * @version 2.0.0
 */

class WindSyncNotifications {
    constructor(config = {}) {
        this.config = {
            dbName: 'WindSyncNotifications',
            dbVersion: 2,
            syncInterval: 30000, // 30 seconds
            maxRetries: 3,
            retryDelays: [1000, 5000, 15000], // Exponential backoff
            apiBaseUrl: window.location.origin,
            technicianId: config.technicianId || 'tech_007',
            enableAudio: config.enableAudio !== false,
            enableWebSocket: config.enableWebSocket !== false,
            developmentMode: config.developmentMode || false,
            batchSize: 10, // Batch sync operations
            ...config
        };
        
        this.db = null;
        this.isOnline = navigator.onLine;
        this.syncInProgress = false;
        this.websocket = null;
        this.initialized = false;
        
        // Enhanced sync management
        this.syncQueue = [];
        this.lastSyncTimestamp = null;
        this.syncStats = {
            totalSynced: 0,
            failedSyncs: 0,
            lastSyncTime: null
        };
        
        // Event listeners
        this.onlineCallbacks = [];
        this.offlineCallbacks = [];
        this.notificationCallbacks = [];
        this.syncCallbacks = [];
        
        // Audio context for alerts
        this.audioContext = null;
        this.audioBuffers = {};
        
        this.log('WindSync Notifications v2.0 initialized with config:', this.config);
    }
    
    /**
     * Initialize the notification system
     */
    async init() {
        if (this.initialized) {
            this.log('Notification system already initialized');
            return true;
        }
        
        try {
            // Initialize IndexedDB with upgraded schema
            await this.initDatabase();
            
            // Setup connectivity monitoring
            this.setupConnectivityMonitoring();
            
            // Initialize audio system
            if (this.config.enableAudio) {
                await this.initAudioSystem();
            }
            
            // Load last sync timestamp
            this.lastSyncTimestamp = await this.getSetting('lastSyncTimestamp');
            
            // Setup WebSocket if enabled and online
            if (this.config.enableWebSocket && this.isOnline) {
                this.setupWebSocket();
            }
            
            // Start periodic sync
            this.startPeriodicSync();
            
            // Initialize UI components
            this.initUI();
            
            // Perform initial sync
            if (this.isOnline) {
                await this.performSync();
            }
            
            this.initialized = true;
            this.log('Notification system v2.0 initialized successfully');
            return true;
            
        } catch (error) {
            this.error('Failed to initialize notification system:', error);
            return false;
        }
    }
    
    /**
     * Initialize IndexedDB with upgraded schema for sync features
     */
    async initDatabase() {
        return new Promise((resolve, reject) => {
            const request = indexedDB.open(this.config.dbName, this.config.dbVersion);
            
            request.onerror = () => {
                this.error('Failed to open IndexedDB:', request.error);
                reject(request.error);
            };
            
            request.onsuccess = () => {
                this.db = request.result;
                this.log('IndexedDB v2.0 initialized successfully');
                resolve();
            };
            
            request.onupgradeneeded = (event) => {
                const db = event.target.result;
                
                // Create/upgrade notifications store
                if (!db.objectStoreNames.contains('notifications')) {
                    const notificationStore = db.createObjectStore('notifications', {
                        keyPath: 'id'
                    });
                    notificationStore.createIndex('priority', 'priority');
                    notificationStore.createIndex('timestamp', 'created_at');
                    notificationStore.createIndex('read', 'read');
                    notificationStore.createIndex('category', 'category');
                    notificationStore.createIndex('technician', 'technician_id');
                }
                
                // Create/upgrade sync queue store
                if (!db.objectStoreNames.contains('syncQueue')) {
                    const syncStore = db.createObjectStore('syncQueue', {
                        keyPath: 'id',
                        autoIncrement: true
                    });
                    syncStore.createIndex('priority', 'priority');
                    syncStore.createIndex('timestamp', 'timestamp');
                    syncStore.createIndex('retryCount', 'retryCount');
                    syncStore.createIndex('action', 'action');
                }
                
                // Create settings store
                if (!db.objectStoreNames.contains('settings')) {
                    db.createObjectStore('settings', {
                        keyPath: 'key'
                    });
                }
                
                // Create sync stats store
                if (!db.objectStoreNames.contains('syncStats')) {
                    db.createObjectStore('syncStats', {
                        keyPath: 'key'
                    });
                }
                
                this.log('IndexedDB schema v2.0 created/updated');
            };
        });
    }
    
    /**
     * Enhanced connectivity monitoring with better detection
     */
    setupConnectivityMonitoring() {
        // Listen for online/offline events
        window.addEventListener('online', () => {
            this.handleConnectivityChange(true);
        });
        
        window.addEventListener('offline', () => {
            this.handleConnectivityChange(false);
        });
        
        // Enhanced connectivity check with multiple methods
        setInterval(() => {
            this.checkRealConnectivity();
        }, 10000);
        
        // Page visibility change handling
        document.addEventListener('visibilitychange', () => {
            if (!document.hidden && this.isOnline) {
                // Page became visible, trigger sync
                this.performSync();
            }
        });
    }
    
    /**
     * Handle connectivity state changes
     */
    async handleConnectivityChange(online) {
        const wasOnline = this.isOnline;
        this.isOnline = online;
        
        if (online && !wasOnline) {
            this.log('Connection restored');
            this.onlineCallbacks.forEach(callback => callback());
            
            // Trigger immediate sync when coming back online
            await this.performSync();
            
            // Setup WebSocket if enabled
            if (this.config.enableWebSocket) {
                this.setupWebSocket();
            }
            
            // Update UI
            this.updateConnectionStatus('online');
            
        } else if (!online && wasOnline) {
            this.log('Connection lost');
            this.offlineCallbacks.forEach(callback => callback());
            
            // Close WebSocket
            if (this.websocket) {
                this.websocket.close();
                this.websocket = null;
            }
            
            // Update UI
            this.updateConnectionStatus('offline');
        }
    }
    
    /**
     * Enhanced connectivity check with multiple validation methods
     */
    async checkRealConnectivity() {
        try {
            // Method 1: Try to fetch health endpoint
            const healthResponse = await fetch(`${this.config.apiBaseUrl}?api=health`, {
                method: 'GET',
                cache: 'no-cache',
                signal: AbortSignal.timeout(5000)
            });
            
            if (healthResponse.ok) {
                if (!this.isOnline) {
                    await this.handleConnectivityChange(true);
                }
                return true;
            }
            
            // Method 2: Try to fetch a small resource
            const testResponse = await fetch('/favicon.ico', {
                method: 'HEAD',
                cache: 'no-cache',
                signal: AbortSignal.timeout(3000)
            });
            
            const connected = testResponse.ok;
            
            if (this.isOnline !== connected) {
                await this.handleConnectivityChange(connected);
            }
            
            return connected;
            
        } catch (error) {
            if (this.isOnline) {
                await this.handleConnectivityChange(false);
            }
            return false;
        }
    }
    
    /**
     * Enhanced sync with priority-based processing and batching
     */
    async performSync() {
        if (this.syncInProgress || !this.isOnline) {
            return { status: 'skipped', reason: this.syncInProgress ? 'sync_in_progress' : 'offline' };
        }
        
        this.syncInProgress = true;
        this.updateConnectionStatus('syncing');
        
        const syncStartTime = Date.now();
        let syncResult = {
            status: 'success',
            newNotifications: 0,
            syncedActions: 0,
            errors: [],
            duration: 0
        };
        
        try {
            this.log('Starting enhanced sync...');
            
            // 1. Process outbound sync queue (priority-based)
            const queueResult = await this.processSyncQueue();
            syncResult.syncedActions = queueResult.processed;
            
            // 2. Fetch new notifications from server (incremental)
            const fetchResult = await this.fetchNewNotifications();
            syncResult.newNotifications = fetchResult.count;
            
            // 3. Update sync statistics
            await this.updateSyncStats(syncResult);
            
            // 4. Clean up old data
            await this.cleanupOldData();
            
            syncResult.duration = Date.now() - syncStartTime;
            this.log(`Sync completed: ${syncResult.newNotifications} new, ${syncResult.syncedActions} synced, ${syncResult.duration}ms`);
            
            // Trigger sync callbacks
            this.syncCallbacks.forEach(callback => callback(syncResult));
            
        } catch (error) {
            this.error('Sync failed:', error);
            syncResult.status = 'error';
            syncResult.errors.push(error.message);
        } finally {
            this.syncInProgress = false;
            this.updateConnectionStatus(this.isOnline ? 'online' : 'offline');
        }
        
        return syncResult;
    }
    
    /**
     * Process sync queue with priority-based ordering
     */
    async processSyncQueue() {
        const queueItems = await this.getSyncQueue();
        
        if (queueItems.length === 0) {
            return { processed: 0, failed: 0 };
        }
        
        // Sort by priority (1 = highest, 4 = lowest)
        queueItems.sort((a, b) => a.priority - b.priority);
        
        let processed = 0;
        let failed = 0;
        
        // Process in batches
        for (let i = 0; i < queueItems.length; i += this.config.batchSize) {
            const batch = queueItems.slice(i, i + this.config.batchSize);
            
            for (const item of batch) {
                try {
                    const success = await this.processSyncItem(item);
                    if (success) {
                        await this.removeSyncItem(item.id);
                        processed++;
                    } else {
                        failed++;
                        await this.updateSyncItemRetry(item);
                    }
                } catch (error) {
                    this.error(`Error processing sync item ${item.id}:`, error);
                    failed++;
                    await this.updateSyncItemRetry(item, error.message);
                }
            }
            
            // Small delay between batches to prevent overwhelming the server
            if (i + this.config.batchSize < queueItems.length) {
                await new Promise(resolve => setTimeout(resolve, 100));
            }
        }
        
        return { processed, failed };
    }
    
    /**
     * Process individual sync item
     */
    async processSyncItem(item) {
        const url = new URL(`${this.config.apiBaseUrl}`);
        
        switch (item.action) {
            case 'acknowledge':
                url.searchParams.set('api', 'acknowledge');
                url.searchParams.set('notification_id', item.notificationId);
                url.searchParams.set('technician_id', this.config.technicianId);
                break;
                
            case 'mark_read':
                url.searchParams.set('api', 'read');
                url.searchParams.set('notification_id', item.notificationId);
                url.searchParams.set('technician_id', this.config.technicianId);
                break;
                
            case 'create_notification':
                url.searchParams.set('api', 'create');
                Object.keys(item.data).forEach(key => {
                    url.searchParams.set(key, item.data[key]);
                });
                break;
                
            default:
                this.error(`Unknown sync action: ${item.action}`);
                return false;
        }
        
        try {
            const response = await fetch(url.toString());
            const result = await response.json();
            
            if (result.success) {
                this.log(`Sync item ${item.id} processed successfully`);
                return true;
            } else {
                this.error(`Sync item ${item.id} failed:`, result.error);
                return false;
            }
        } catch (error) {
            this.error(`Network error processing sync item ${item.id}:`, error);
            return false;
        }
    }
    
    /**
     * Enhanced notification fetching with incremental sync
     */
    async fetchNewNotifications() {
        try {
            const url = new URL(`${this.config.apiBaseUrl}`);
            url.searchParams.set('api', 'sync');
            url.searchParams.set('technician_id', this.config.technicianId);
            
            if (this.lastSyncTimestamp) {
                url.searchParams.set('last_sync', this.lastSyncTimestamp);
            }
            
            const response = await fetch(url.toString());
            const result = await response.json();
            
            if (!result.success) {
                throw new Error(result.error.message);
            }
            
            const notifications = result.data.notifications;
            let newCount = 0;
            
            // Store notifications locally and trigger display
            for (const notification of notifications) {
                const isNew = await this.storeNotificationLocally(notification);
                if (isNew) {
                    this.handleIncomingNotification(notification, false);
                    newCount++;
                }
            }
            
            // Update last sync timestamp
            this.lastSyncTimestamp = result.data.server_timestamp;
            await this.setSetting('lastSyncTimestamp', this.lastSyncTimestamp);
            
            this.log(`Fetched ${notifications.length} notifications, ${newCount} new`);
            
            return { count: newCount, total: notifications.length };
            
        } catch (error) {
            this.error('Failed to fetch new notifications:', error);
            throw error;
        }
    }
    
    /**
     * Queue sync action for offline processing
     */
    async queueSyncAction(action, notificationId, data = {}, priority = 3) {
        const syncItem = {
            action: action,
            notificationId: notificationId,
            data: data,
            priority: priority,
            timestamp: Date.now(),
            retryCount: 0,
            technicianId: this.config.technicianId
        };
        
        return new Promise((resolve, reject) => {
            const transaction = this.db.transaction(['syncQueue'], 'readwrite');
            const store = transaction.objectStore('syncQueue');
            
            const request = store.add(syncItem);
            
            request.onsuccess = () => {
                this.log(`Queued sync action: ${action} for notification ${notificationId}`);
                resolve(request.result);
            };
            
            request.onerror = () => reject(request.error);
        });
    }
    
    /**
     * Get sync queue items
     */
    async getSyncQueue() {
        return new Promise((resolve, reject) => {
            const transaction = this.db.transaction(['syncQueue'], 'readonly');
            const store = transaction.objectStore('syncQueue');
            const request = store.getAll();
            
            request.onsuccess = () => resolve(request.result);
            request.onerror = () => reject(request.error);
        });
    }
    
    /**
     * Remove sync item from queue
     */
    async removeSyncItem(itemId) {
        return new Promise((resolve, reject) => {
            const transaction = this.db.transaction(['syncQueue'], 'readwrite');
            const store = transaction.objectStore('syncQueue');
            const request = store.delete(itemId);
            
            request.onsuccess = () => resolve();
            request.onerror = () => reject(request.error);
        });
    }
    
    /**
     * Update sync item retry count
     */
    async updateSyncItemRetry(item, errorMessage = null) {
        item.retryCount++;
        item.lastError = errorMessage;
        item.lastAttempt = Date.now();
        
        return new Promise((resolve, reject) => {
            const transaction = this.db.transaction(['syncQueue'], 'readwrite');
            const store = transaction.objectStore('syncQueue');
            const request = store.put(item);
            
            request.onsuccess = () => resolve();
            request.onerror = () => reject(request.error);
        });
    }
    
    /**
     * Enhanced notification acknowledgment with offline support
     */
    async acknowledgeNotification(notificationId) {
        // Update local state immediately
        await this.updateNotificationLocally(notificationId, { 
            acknowledged: true, 
            acknowledged_at: new Date().toISOString() 
        });
        
        if (this.isOnline) {
            // Try to sync immediately
            try {
                const url = new URL(`${this.config.apiBaseUrl}`);
                url.searchParams.set('api', 'acknowledge');
                url.searchParams.set('notification_id', notificationId);
                url.searchParams.set('technician_id', this.config.technicianId);
                
                const response = await fetch(url.toString());
                const result = await response.json();
                
                if (result.success) {
                    this.log(`Notification ${notificationId} acknowledged successfully`);
                    return true;
                } else {
                    throw new Error(result.error.message);
                }
            } catch (error) {
                this.error('Failed to acknowledge online, queuing for sync:', error);
                await this.queueSyncAction('acknowledge', notificationId, {}, 2); // High priority
            }
        } else {
            // Queue for later sync
            await this.queueSyncAction('acknowledge', notificationId, {}, 2); // High priority
        }
        
        return true;
    }
    
    /**
     * Enhanced mark as read with offline support
     */
    async markAsRead(notificationId) {
        // Update local state immediately
        await this.updateNotificationLocally(notificationId, { 
            read: true, 
            read_at: new Date().toISOString() 
        });
        
        if (this.isOnline) {
            // Try to sync immediately
            try {
                const url = new URL(`${this.config.apiBaseUrl}`);
                url.searchParams.set('api', 'read');
                url.searchParams.set('notification_id', notificationId);
                url.searchParams.set('technician_id', this.config.technicianId);
                
                const response = await fetch(url.toString());
                const result = await response.json();
                
                if (result.success) {
                    this.log(`Notification ${notificationId} marked as read successfully`);
                    return true;
                } else {
                    throw new Error(result.error.message);
                }
            } catch (error) {
                this.error('Failed to mark as read online, queuing for sync:', error);
                await this.queueSyncAction('mark_read', notificationId, {}, 3); // Medium priority
            }
        } else {
            // Queue for later sync
            await this.queueSyncAction('mark_read', notificationId, {}, 3); // Medium priority
        }
        
        return true;
    }
    
    /**
     * Update notification in local storage
     */
    async updateNotificationLocally(notificationId, updates) {
        return new Promise((resolve, reject) => {
            const transaction = this.db.transaction(['notifications'], 'readwrite');
            const store = transaction.objectStore('notifications');
            
            const getRequest = store.get(notificationId);
            
            getRequest.onsuccess = () => {
                const notification = getRequest.result;
                if (notification) {
                    Object.assign(notification, updates);
                    
                    const putRequest = store.put(notification);
                    putRequest.onsuccess = () => resolve(true);
                    putRequest.onerror = () => reject(putRequest.error);
                } else {
                    resolve(false);
                }
            };
            
            getRequest.onerror = () => reject(getRequest.error);
        });
    }
    
    /**
     * Store notification in local IndexedDB
     */
    async storeNotificationLocally(notification) {
        return new Promise((resolve, reject) => {
            const transaction = this.db.transaction(['notifications'], 'readwrite');
            const store = transaction.objectStore('notifications');
            
            // Check if notification already exists
            const getRequest = store.get(notification.id);
            
            getRequest.onsuccess = () => {
                const existing = getRequest.result;
                const isNew = !existing;
                
                // Add local metadata
                notification.localTimestamp = Date.now();
                notification.read = notification.read_at ? true : false;
                notification.acknowledged = notification.acknowledged_at ? true : false;
                
                const putRequest = store.put(notification);
                putRequest.onsuccess = () => resolve(isNew);
                putRequest.onerror = () => reject(putRequest.error);
            };
            
            getRequest.onerror = () => reject(getRequest.error);
        });
    }
    
    /**
     * Handle incoming notification (from WebSocket or sync)
     */
    async handleIncomingNotification(notification, shouldSync = true) {
        // Store locally
        await this.storeNotificationLocally(notification);
        
        // Display notification
        this.displayNotification(notification);
        
        // Play audio alert if enabled
        if (this.config.enableAudio && notification.priority) {
            this.playAudioAlert(notification.priority);
        }
        
        // Trigger callbacks
        this.notificationCallbacks.forEach(callback => callback(notification));
        
        // Update UI
        this.updateNotificationBadge();
        
        this.log('Handled incoming notification:', notification.title);
    }
    
    /**
     * Display notification to user
     */
    displayNotification(notification) {
        // Create notification element
        const notificationElement = this.createNotificationElement(notification);
        
        // Add to notification center
        this.addToNotificationCenter(notificationElement);
        
        // Show modal for critical notifications
        if (notification.priority === 'critical' && notification.requires_acknowledgment) {
            this.showCriticalAlertModal(notification);
        }
        
        // Show browser notification if supported and permitted
        if ('Notification' in window && Notification.permission === 'granted') {
            new Notification(notification.title, {
                body: notification.message,
                icon: '/static/images/windsync-icon.png',
                tag: `notification-${notification.id}`
            });
        }
    }
    
    /**
     * Update sync statistics
     */
    async updateSyncStats(syncResult) {
        this.syncStats.totalSynced += syncResult.syncedActions;
        this.syncStats.lastSyncTime = Date.now();
        
        if (syncResult.status === 'error') {
            this.syncStats.failedSyncs++;
        }
        
        await this.setSyncStat('syncStats', this.syncStats);
    }
    
    /**
     * Update connection status in UI
     */
    updateConnectionStatus(status) {
        const statusElement = document.getElementById('windsync-connection-status');
        if (statusElement) {
            statusElement.className = `connection-status ${status}`;
            
            const statusText = {
                'online': '🟢 Online',
                'offline': '🔴 Offline',
                'syncing': '🔄 Syncing...'
            };
            
            statusElement.textContent = statusText[status] || status;
        }
    }
    
    /**
     * Enhanced UI initialization with sync status
     */
    initUI() {
        // Create notification badge
        this.createNotificationBadge();
        
        // Create notification center
        this.createNotificationCenter();
        
        // Create critical alert modal
        this.createCriticalAlertModal();
        
        // Create connection status indicator
        this.createConnectionStatus();
        
        // Add CSS styles
        this.injectStyles();
        
        this.log('Enhanced UI components initialized');
    }
    
    /**
     * Create connection status indicator
     */
    createConnectionStatus() {
        const status = document.createElement('div');
        status.id = 'windsync-connection-status';
        status.className = `connection-status ${this.isOnline ? 'online' : 'offline'}`;
        status.textContent = this.isOnline ? '🟢 Online' : '🔴 Offline';
        
        document.body.appendChild(status);
    }
    
    /**
     * Initialize audio system for alerts
     */
    async initAudioSystem() {
        try {
            this.audioContext = new (window.AudioContext || window.webkitAudioContext)();
            
            // Load audio files for different priorities
            const audioFiles = {
                critical: '/static/audio/critical_alert.wav',
                high: '/static/audio/high_alert.wav',
                medium: '/static/audio/medium_alert.wav'
            };
            
            for (const [priority, url] of Object.entries(audioFiles)) {
                try {
                    const response = await fetch(url);
                    if (response.ok) {
                        const arrayBuffer = await response.arrayBuffer();
                        this.audioBuffers[priority] = await this.audioContext.decodeAudioData(arrayBuffer);
                    }
                } catch (error) {
                    this.log(`Could not load audio file for ${priority}:`, error);
                }
            }
            
            this.log('Audio system initialized');
            
        } catch (error) {
            this.log('Audio system not available:', error);
            this.config.enableAudio = false;
        }
    }
    
    /**
     * Setup WebSocket connection for real-time notifications
     */
    setupWebSocket() {
        if (this.websocket && this.websocket.readyState === WebSocket.OPEN) {
            return; // Already connected
        }
        
        try {
            const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const wsUrl = `${wsProtocol}//${window.location.host}/ws/notifications/${this.config.technicianId}`;
            
            this.websocket = new WebSocket(wsUrl);
            
            this.websocket.onopen = () => {
                this.log('WebSocket connected');
            };
            
            this.websocket.onmessage = (event) => {
                try {
                    const notification = JSON.parse(event.data);
                    this.handleIncomingNotification(notification);
                } catch (error) {
                    this.error('Error parsing WebSocket message:', error);
                }
            };
            
            this.websocket.onclose = () => {
                this.log('WebSocket disconnected');
                this.websocket = null;
                
                // Attempt to reconnect if online
                if (this.isOnline) {
                    setTimeout(() => {
                        this.setupWebSocket();
                    }, 5000);
                }
            };
            
            this.websocket.onerror = (error) => {
                this.error('WebSocket error:', error);
            };
            
        } catch (error) {
            this.error('Failed to setup WebSocket:', error);
        }
    }
    
    /**
     * Start periodic synchronization
     */
    startPeriodicSync() {
        setInterval(() => {
            if (this.isOnline && !this.syncInProgress) {
                this.performSync();
            }
        }, this.config.syncInterval);
    }
    
    /**
     * Play audio alert for notification
     */
    playAudioAlert(priority) {
        if (!this.config.enableAudio || !this.audioContext || !this.audioBuffers[priority]) {
            return;
        }
        
        try {
            const source = this.audioContext.createBufferSource();
            source.buffer = this.audioBuffers[priority];
            source.connect(this.audioContext.destination);
            source.start();
        } catch (error) {
            this.error('Failed to play audio alert:', error);
        }
    }
    
    /**
     * Create notification badge for sidebar
     */
    createNotificationBadge() {
        const badge = document.createElement('div');
        badge.id = 'windsync-notification-badge';
        badge.className = 'notification-badge';
        badge.innerHTML = `
            <div class="notification-icon" onclick="windSyncNotifications.toggleNotificationCenter()">
                <span class="icon">🔔</span>
                <span class="count" id="notification-count">0</span>
            </div>
        `;
        
        // Try to add to Streamlit sidebar
        const sidebar = document.querySelector('.css-1d391kg, [data-testid="stSidebar"]');
        if (sidebar) {
            sidebar.insertBefore(badge, sidebar.firstChild);
        } else {
            // Fallback: add to body
            document.body.appendChild(badge);
        }
    }
    
    /**
     * Create notification center modal
     */
    createNotificationCenter() {
        const center = document.createElement('div');
        center.id = 'windsync-notification-center';
        center.className = 'notification-center hidden';
        center.innerHTML = `
            <div class="notification-center-content">
                <div class="notification-center-header">
                    <h3>Notifications</h3>
                    <button onclick="windSyncNotifications.toggleNotificationCenter()" class="close-btn">×</button>
                </div>
                <div class="notification-center-body">
                    <div id="notification-list" class="notification-list">
                        <div class="no-notifications">No notifications</div>
                    </div>
                </div>
            </div>
        `;
        
        document.body.appendChild(center);
    }
    
    /**
     * Create critical alert modal
     */
    createCriticalAlertModal() {
        const modal = document.createElement('div');
        modal.id = 'windsync-critical-alert';
        modal.className = 'critical-alert-modal hidden';
        modal.innerHTML = `
            <div class="critical-alert-content">
                <div class="critical-alert-header">
                    <h2>🚨 CRITICAL ALERT</h2>
                </div>
                <div class="critical-alert-body">
                    <h3 id="critical-alert-title"></h3>
                    <p id="critical-alert-message"></p>
                </div>
                <div class="critical-alert-footer">
                    <button id="critical-alert-acknowledge" class="acknowledge-btn">
                        ACKNOWLEDGE
                    </button>
                </div>
            </div>
        `;
        
        document.body.appendChild(modal);
    }
    
    /**
     * Inject CSS styles
     */
    injectStyles() {
        const styles = `
            .notification-badge {
                position: fixed;
                top: 20px;
                right: 20px;
                z-index: 1000;
                cursor: pointer;
            }
            
            .notification-icon {
                position: relative;
                background: #ff4444;
                color: white;
                border-radius: 50%;
                width: 40px;
                height: 40px;
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 18px;
            }
            
            .notification-count {
                position: absolute;
                top: -5px;
                right: -5px;
                background: #ff0000;
                color: white;
                border-radius: 50%;
                width: 20px;
                height: 20px;
                font-size: 12px;
                display: none;
                align-items: center;
                justify-content: center;
            }
            
            .notification-center {
                position: fixed;
                top: 0;
                right: 0;
                width: 400px;
                height: 100vh;
                background: white;
                box-shadow: -2px 0 10px rgba(0,0,0,0.1);
                z-index: 1001;
                transform: translateX(100%);
                transition: transform 0.3s ease;
            }
            
            .notification-center:not(.hidden) {
                transform: translateX(0);
            }
            
            .critical-alert-modal {
                position: fixed;
                top: 0;
                left: 0;
                width: 100vw;
                height: 100vh;
                background: rgba(0,0,0,0.8);
                z-index: 1002;
                display: flex;
                align-items: center;
                justify-content: center;
            }
            
            .critical-alert-content {
                background: white;
                border-radius: 8px;
                padding: 20px;
                max-width: 500px;
                width: 90%;
                border: 3px solid #ff0000;
            }
            
            .connection-status {
                position: fixed;
                bottom: 20px;
                right: 20px;
                padding: 8px 12px;
                border-radius: 4px;
                font-size: 12px;
                z-index: 999;
            }
            
            .connection-status.online {
                background: #d4edda;
                color: #155724;
                border: 1px solid #c3e6cb;
            }
            
            .connection-status.offline {
                background: #f8d7da;
                color: #721c24;
                border: 1px solid #f5c6cb;
            }
            
            .connection-status.syncing {
                background: #fff3cd;
                color: #856404;
                border: 1px solid #ffeaa7;
            }
            
            .hidden {
                display: none !important;
            }
        `;
        
        const styleSheet = document.createElement('style');
        styleSheet.textContent = styles;
        document.head.appendChild(styleSheet);
    }
    
    /**
     * Enhanced cleanup with sync queue cleanup
     */
    async cleanupOldData() {
        const cutoffDate = new Date();
        cutoffDate.setDate(cutoffDate.getDate() - 30); // 30 days ago
        
        // Clean up old notifications
        const transaction = this.db.transaction(['notifications', 'syncQueue'], 'readwrite');
        
        // Remove old notifications
        const notificationStore = transaction.objectStore('notifications');
        const notificationIndex = notificationStore.index('timestamp');
        const notificationRange = IDBKeyRange.upperBound(cutoffDate.toISOString());
        
        notificationIndex.openCursor(notificationRange).onsuccess = (event) => {
            const cursor = event.target.result;
            if (cursor) {
                cursor.delete();
                cursor.continue();
            }
        };
        
        // Remove old failed sync items (after max retries)
        const syncStore = transaction.objectStore('syncQueue');
        syncStore.openCursor().onsuccess = (event) => {
            const cursor = event.target.result;
            if (cursor) {
                const item = cursor.value;
                if (item.retryCount >= this.config.maxRetries) {
                    cursor.delete();
                }
                cursor.continue();
            }
        };
    }
    
    /**
     * Get/set sync statistics
     */
    async setSyncStat(key, value) {
        return new Promise((resolve, reject) => {
            const transaction = this.db.transaction(['syncStats'], 'readwrite');
            const store = transaction.objectStore('syncStats');
            const request = store.put({ key, value });
            
            request.onsuccess = () => resolve();
            request.onerror = () => reject(request.error);
        });
    }
    
    async getSyncStat(key) {
        return new Promise((resolve, reject) => {
            const transaction = this.db.transaction(['syncStats'], 'readonly');
            const store = transaction.objectStore('syncStats');
            const request = store.get(key);
            
            request.onsuccess = () => {
                resolve(request.result ? request.result.value : null);
            };
            request.onerror = () => reject(request.error);
        });
    }
    
    /**
     * Get sync statistics for display
     */
    async getSyncStatistics() {
        const stats = await this.getSyncStat('syncStats') || this.syncStats;
        const queueItems = await this.getSyncQueue();
        
        return {
            ...stats,
            queuedItems: queueItems.length,
            isOnline: this.isOnline,
            syncInProgress: this.syncInProgress,
            lastSyncTimestamp: this.lastSyncTimestamp
        };
    }
    
    /**
     * Toggle notification center visibility
     */
    toggleNotificationCenter() {
        const center = document.getElementById('windsync-notification-center');
        if (center) {
            center.classList.toggle('hidden');
        }
    }
    
    /**
     * Update notification badge count
     */
    async updateNotificationBadge() {
        try {
            const notifications = await this.getLocalNotifications();
            const unreadCount = notifications.filter(n => !n.read).length;
            
            const countElement = document.getElementById('notification-count');
            if (countElement) {
                countElement.textContent = unreadCount;
                countElement.style.display = unreadCount > 0 ? 'flex' : 'none';
            }
        } catch (error) {
            this.error('Failed to update notification badge:', error);
        }
    }
    
    /**
     * Get local notifications
     */
    async getLocalNotifications() {
        return new Promise((resolve, reject) => {
            const transaction = this.db.transaction(['notifications'], 'readonly');
            const store = transaction.objectStore('notifications');
            const request = store.getAll();
            
            request.onsuccess = () => resolve(request.result);
            request.onerror = () => reject(request.error);
        });
    }
    
    /**
     * Create notification element for display
     */
    createNotificationElement(notification) {
        const element = document.createElement('div');
        element.className = `notification-item priority-${notification.priority}`;
        element.innerHTML = `
            <div class="notification-header">
                <span class="notification-title">${notification.title}</span>
                <span class="notification-time">${new Date(notification.created_at).toLocaleTimeString()}</span>
            </div>
            <div class="notification-message">${notification.message}</div>
            <div class="notification-actions">
                ${!notification.read ? '<button onclick="windSyncNotifications.markAsRead(' + notification.id + ')">Mark Read</button>' : ''}
                ${notification.requires_acknowledgment && !notification.acknowledged ? '<button onclick="windSyncNotifications.acknowledgeNotification(' + notification.id + ')">Acknowledge</button>' : ''}
            </div>
        `;
        return element;
    }
    
    /**
     * Add notification to notification center
     */
    addToNotificationCenter(notificationElement) {
        const notificationList = document.getElementById('notification-list');
        if (notificationList) {
            const noNotifications = notificationList.querySelector('.no-notifications');
            if (noNotifications) {
                noNotifications.remove();
            }
            notificationList.insertBefore(notificationElement, notificationList.firstChild);
        }
    }
    
    /**
     * Show critical alert modal
     */
    showCriticalAlertModal(notification) {
        const modal = document.getElementById('windsync-critical-alert');
        const title = document.getElementById('critical-alert-title');
        const message = document.getElementById('critical-alert-message');
        const acknowledgeBtn = document.getElementById('critical-alert-acknowledge');
        
        if (modal && title && message && acknowledgeBtn) {
            title.textContent = notification.title;
            message.textContent = notification.message;
            
            acknowledgeBtn.onclick = () => {
                this.acknowledgeNotification(notification.id);
                modal.classList.add('hidden');
            };
            
            modal.classList.remove('hidden');
        }
    }
    
    /**
     * Utility functions
     */
    log(...args) {
        if (this.config.developmentMode) {
            console.log('[WindSync Notifications v2.0]', ...args);
        }
    }
    
    error(...args) {
        console.error('[WindSync Notifications v2.0]', ...args);
    }
    
    async getSetting(key) {
        return new Promise((resolve, reject) => {
            const transaction = this.db.transaction(['settings'], 'readonly');
            const store = transaction.objectStore('settings');
            const request = store.get(key);
            
            request.onsuccess = () => {
                resolve(request.result ? request.result.value : null);
            };
            request.onerror = () => reject(request.error);
        });
    }
    
    async setSetting(key, value) {
        return new Promise((resolve, reject) => {
            const transaction = this.db.transaction(['settings'], 'readwrite');
            const store = transaction.objectStore('settings');
            const request = store.put({ key, value });
            
            request.onsuccess = () => resolve();
            request.onerror = () => reject(request.error);
        });
    }
}

// Global instance
let windSyncNotifications = null;

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', async () => {
    windSyncNotifications = new WindSyncNotifications({
        developmentMode: true // Set to false in production
    });
    
    await windSyncNotifications.init();
});

// Export for module use
if (typeof module !== 'undefined' && module.exports) {
    module.exports = WindSyncNotifications;
}