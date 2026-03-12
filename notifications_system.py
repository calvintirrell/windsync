"""
WindSync Real-Time Notifications & Alerts System
================================================

A modular notification system designed for field technicians with offline-first capabilities.
Handles critical safety alerts, task updates, and equipment notifications with intelligent
synchronization for intermittent connectivity environments.

Author: WindSync Development Team
Version: 1.0.0
"""

import sqlite3
import json
import datetime
from typing import Dict, List, Optional, Any, Union
from enum import Enum
from dataclasses import dataclass, asdict
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class NotificationPriority(Enum):
    """Notification priority levels"""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class NotificationCategory(Enum):
    """Notification categories"""
    SAFETY = "safety"
    TASK = "task"
    EQUIPMENT = "equipment"
    SYSTEM = "system"


@dataclass
class NotificationData:
    """Data structure for notifications"""
    title: str
    message: str
    priority: NotificationPriority
    category: NotificationCategory
    technician_id: str
    metadata: Optional[Dict[str, Any]] = None
    requires_acknowledgment: bool = False
    expires_at: Optional[datetime.datetime] = None
    created_by: str = "system"
    id: Optional[int] = None
    created_at: Optional[datetime.datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        data = asdict(self)
        # Convert enums to strings
        data['priority'] = self.priority.value
        data['category'] = self.category.value
        # Convert datetime objects to ISO strings
        if self.created_at:
            data['created_at'] = self.created_at.isoformat()
        if self.expires_at:
            data['expires_at'] = self.expires_at.isoformat()
        return data


class NotificationConfig:
    """Configuration class for notification system"""
    
    def __init__(self, 
                 db_file: str = "windsync.db",
                 enable_websocket: bool = True,
                 websocket_port: int = 8765,
                 sync_interval: int = 30,
                 max_retries: int = 3,
                 development_mode: bool = False):
        self.db_file = db_file
        self.enable_websocket = enable_websocket
        self.websocket_port = websocket_port
        self.sync_interval = sync_interval
        self.max_retries = max_retries
        self.development_mode = development_mode
        
        # Priority-based retry delays (seconds)
        self.retry_delays = {
            NotificationPriority.CRITICAL: [1, 5, 15],
            NotificationPriority.HIGH: [5, 15, 60],
            NotificationPriority.MEDIUM: [15, 60, 300],
            NotificationPriority.LOW: [60, 300, 900]
        }
        
        # Audio alert settings
        self.audio_alerts = {
            NotificationPriority.CRITICAL: "critical_alert.wav",
            NotificationPriority.HIGH: "high_alert.wav",
            NotificationPriority.MEDIUM: "medium_alert.wav",
            NotificationPriority.LOW: None  # No audio for low priority
        }


class NotificationDatabase:
    """Database operations for notifications"""
    
    def __init__(self, config: NotificationConfig):
        self.config = config
        self.db_file = config.db_file
        self._ensure_tables()
    
    def _ensure_tables(self):
        """Create notification tables if they don't exist"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            # Notifications table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS notifications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    message TEXT NOT NULL,
                    priority TEXT NOT NULL CHECK (priority IN ('critical', 'high', 'medium', 'low')),
                    category TEXT NOT NULL CHECK (category IN ('safety', 'task', 'equipment', 'system')),
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    expires_at DATETIME,
                    created_by TEXT DEFAULT 'system',
                    metadata TEXT,
                    requires_acknowledgment BOOLEAN DEFAULT FALSE
                )
            """)
            
            # Notification recipients table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS notification_recipients (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    notification_id INTEGER,
                    technician_id TEXT,
                    delivered_at DATETIME,
                    read_at DATETIME,
                    acknowledged_at DATETIME,
                    delivery_attempts INTEGER DEFAULT 0,
                    FOREIGN KEY (notification_id) REFERENCES notifications (id),
                    FOREIGN KEY (technician_id) REFERENCES technicians (id)
                )
            """)
            
            # Notification templates table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS notification_templates (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    title_template TEXT NOT NULL,
                    message_template TEXT NOT NULL,
                    priority TEXT NOT NULL,
                    category TEXT NOT NULL,
                    requires_acknowledgment BOOLEAN DEFAULT FALSE,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            conn.commit()
            logger.info("Notification database tables created/verified successfully")
            
        except Exception as e:
            logger.error(f"Error creating notification tables: {e}")
            raise
        finally:
            conn.close()
    
    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection with row factory"""
        conn = sqlite3.connect(self.db_file, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn
    
    def create_notification(self, notification: NotificationData) -> int:
        """Create a new notification and return its ID"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            # Insert notification
            cursor.execute("""
                INSERT INTO notifications (title, message, priority, category, metadata, 
                                         requires_acknowledgment, expires_at, created_by)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                notification.title,
                notification.message,
                notification.priority.value,
                notification.category.value,
                json.dumps(notification.metadata or {}),
                notification.requires_acknowledgment,
                notification.expires_at,
                notification.created_by
            ))
            
            notification_id = cursor.lastrowid
            
            # Insert recipient
            cursor.execute("""
                INSERT INTO notification_recipients (notification_id, technician_id)
                VALUES (?, ?)
            """, (notification_id, notification.technician_id))
            
            conn.commit()
            logger.info(f"Created notification {notification_id} for technician {notification.technician_id}")
            return notification_id
            
        except Exception as e:
            logger.error(f"Error creating notification: {e}")
            conn.rollback()
            raise
        finally:
            conn.close()
    
    def get_notifications_for_technician(self, 
                                       technician_id: str, 
                                       since_timestamp: Optional[datetime.datetime] = None,
                                       limit: int = 100) -> List[Dict[str, Any]]:
        """Get notifications for a specific technician"""
        conn = self._get_connection()
        
        try:
            query = """
                SELECT n.*, nr.delivered_at, nr.read_at, nr.acknowledged_at, nr.delivery_attempts
                FROM notifications n
                JOIN notification_recipients nr ON n.id = nr.notification_id
                WHERE nr.technician_id = ?
            """
            params = [technician_id]
            
            if since_timestamp:
                query += " AND n.created_at > ?"
                params.append(since_timestamp.isoformat())
            
            # Filter out expired notifications
            query += " AND (n.expires_at IS NULL OR n.expires_at > datetime('now'))"
            query += " ORDER BY n.created_at DESC LIMIT ?"
            params.append(limit)
            
            cursor = conn.cursor()
            cursor.execute(query, params)
            
            notifications = []
            for row in cursor.fetchall():
                notification = dict(row)
                # Parse metadata JSON
                if notification['metadata']:
                    notification['metadata'] = json.loads(notification['metadata'])
                notifications.append(notification)
            
            return notifications
            
        except Exception as e:
            logger.error(f"Error fetching notifications for technician {technician_id}: {e}")
            raise
        finally:
            conn.close()
    
    def acknowledge_notification(self, notification_id: int, technician_id: str) -> bool:
        """Mark notification as acknowledged"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                UPDATE notification_recipients 
                SET acknowledged_at = CURRENT_TIMESTAMP
                WHERE notification_id = ? AND technician_id = ?
            """, (notification_id, technician_id))
            
            success = cursor.rowcount > 0
            conn.commit()
            
            if success:
                logger.info(f"Notification {notification_id} acknowledged by {technician_id}")
            else:
                logger.warning(f"Failed to acknowledge notification {notification_id} for {technician_id}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error acknowledging notification: {e}")
            conn.rollback()
            raise
        finally:
            conn.close()
    
    def mark_as_read(self, notification_id: int, technician_id: str) -> bool:
        """Mark notification as read"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                UPDATE notification_recipients 
                SET read_at = CURRENT_TIMESTAMP
                WHERE notification_id = ? AND technician_id = ? AND read_at IS NULL
            """, (notification_id, technician_id))
            
            success = cursor.rowcount > 0
            conn.commit()
            
            if success:
                logger.info(f"Notification {notification_id} marked as read by {technician_id}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error marking notification as read: {e}")
            conn.rollback()
            raise
        finally:
            conn.close()


class NotificationManager:
    """Main notification system controller"""
    
    def __init__(self, config: Optional[NotificationConfig] = None):
        self.config = config or NotificationConfig()
        self.db = NotificationDatabase(self.config)
        self._initialized = False
        
        logger.info(f"NotificationManager initialized with config: {self.config.__dict__}")
    
    def initialize(self) -> bool:
        """Initialize the notification system"""
        try:
            # Ensure database tables exist
            self.db._ensure_tables()
            
            # Initialize notification templates if in development mode
            if self.config.development_mode:
                self._create_default_templates()
            
            self._initialized = True
            logger.info("Notification system initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize notification system: {e}")
            return False
    
    def cleanup(self):
        """Cleanup notification system resources"""
        # Close any open connections, stop background tasks, etc.
        logger.info("Notification system cleanup completed")
    
    def create_alert(self, 
                    title: str, 
                    message: str, 
                    priority: Union[str, NotificationPriority], 
                    technician_id: str,
                    category: Union[str, NotificationCategory] = NotificationCategory.SYSTEM,
                    metadata: Optional[Dict[str, Any]] = None,
                    requires_acknowledgment: Optional[bool] = None) -> int:
        """
        Create a new notification alert
        
        Args:
            title: Alert title
            message: Alert message
            priority: Priority level (critical, high, medium, low)
            technician_id: Target technician ID
            category: Notification category (safety, task, equipment, system)
            metadata: Additional context data
            requires_acknowledgment: Whether acknowledgment is required (auto-determined if None)
        
        Returns:
            Notification ID
        """
        if not self._initialized:
            raise RuntimeError("Notification system not initialized. Call initialize() first.")
        
        # Convert string parameters to enums
        if isinstance(priority, str):
            priority = NotificationPriority(priority.lower())
        if isinstance(category, str):
            category = NotificationCategory(category.lower())
        
        # Auto-determine acknowledgment requirement
        if requires_acknowledgment is None:
            requires_acknowledgment = priority in [NotificationPriority.CRITICAL, NotificationPriority.HIGH]
        
        notification = NotificationData(
            title=title,
            message=message,
            priority=priority,
            category=category,
            technician_id=technician_id,
            metadata=metadata,
            requires_acknowledgment=requires_acknowledgment
        )
        
        notification_id = self.db.create_notification(notification)
        
        # TODO: Trigger real-time delivery if WebSocket available
        # TODO: Queue for offline sync if needed
        
        return notification_id
    
    def get_notifications(self, 
                         technician_id: str, 
                         since: Optional[datetime.datetime] = None) -> List[Dict[str, Any]]:
        """Get notifications for a technician"""
        if not self._initialized:
            raise RuntimeError("Notification system not initialized. Call initialize() first.")
        
        return self.db.get_notifications_for_technician(technician_id, since)
    
    def acknowledge_notification(self, notification_id: int, technician_id: str) -> bool:
        """Acknowledge a notification"""
        if not self._initialized:
            raise RuntimeError("Notification system not initialized. Call initialize() first.")
        
        return self.db.acknowledge_notification(notification_id, technician_id)
    
    def mark_as_read(self, notification_id: int, technician_id: str) -> bool:
        """Mark notification as read"""
        if not self._initialized:
            raise RuntimeError("Notification system not initialized. Call initialize() first.")
        
        return self.db.mark_as_read(notification_id, technician_id)
    
    def get_unread_count(self, technician_id: str) -> int:
        """Get count of unread notifications for a technician"""
        notifications = self.get_notifications(technician_id)
        return len([n for n in notifications if not n['read_at']])
    
    def _create_default_templates(self):
        """Create default notification templates for development"""
        templates = [
            {
                'name': 'equipment_failure',
                'title_template': 'Equipment Failure: {asset_name}',
                'message_template': 'Critical failure detected on {asset_name}. Immediate attention required.',
                'priority': 'critical',
                'category': 'equipment',
                'requires_acknowledgment': True
            },
            {
                'name': 'weather_warning',
                'title_template': 'Weather Alert: {warning_type}',
                'message_template': '{warning_type} warning in effect. Wind speeds: {wind_speed} mph. Consider safety protocols.',
                'priority': 'high',
                'category': 'safety',
                'requires_acknowledgment': True
            },
            {
                'name': 'task_assignment',
                'title_template': 'New Task Assigned: {task_title}',
                'message_template': 'You have been assigned a new {priority} priority task: {task_title}',
                'priority': 'medium',
                'category': 'task',
                'requires_acknowledgment': False
            }
        ]
        
        conn = self.db._get_connection()
        cursor = conn.cursor()
        
        try:
            for template in templates:
                cursor.execute("""
                    INSERT OR IGNORE INTO notification_templates 
                    (name, title_template, message_template, priority, category, requires_acknowledgment)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    template['name'],
                    template['title_template'],
                    template['message_template'],
                    template['priority'],
                    template['category'],
                    template['requires_acknowledgment']
                ))
            
            conn.commit()
            logger.info("Default notification templates created")
            
        except Exception as e:
            logger.error(f"Error creating default templates: {e}")
            conn.rollback()
        finally:
            conn.close()


# Convenience functions for easy integration
def create_notification_manager(development_mode: bool = False) -> NotificationManager:
    """Create and initialize a notification manager"""
    config = NotificationConfig(development_mode=development_mode)
    manager = NotificationManager(config)
    manager.initialize()
    return manager


def create_safety_alert(manager: NotificationManager, 
                       title: str, 
                       message: str, 
                       technician_id: str,
                       metadata: Optional[Dict[str, Any]] = None) -> int:
    """Create a critical safety alert"""
    return manager.create_alert(
        title=title,
        message=message,
        priority=NotificationPriority.CRITICAL,
        technician_id=technician_id,
        category=NotificationCategory.SAFETY,
        metadata=metadata,
        requires_acknowledgment=True
    )


def create_task_update(manager: NotificationManager,
                      title: str,
                      message: str,
                      technician_id: str,
                      priority: str = "medium",
                      metadata: Optional[Dict[str, Any]] = None) -> int:
    """Create a task update notification"""
    return manager.create_alert(
        title=title,
        message=message,
        priority=priority,
        technician_id=technician_id,
        category=NotificationCategory.TASK,
        metadata=metadata
    )


def create_equipment_alert(manager: NotificationManager,
                          title: str,
                          message: str,
                          technician_id: str,
                          priority: str = "high",
                          metadata: Optional[Dict[str, Any]] = None) -> int:
    """Create an equipment alert notification"""
    return manager.create_alert(
        title=title,
        message=message,
        priority=priority,
        technician_id=technician_id,
        category=NotificationCategory.EQUIPMENT,
        metadata=metadata
    )


# Example usage and testing
if __name__ == "__main__":
    # Development/testing mode
    print("WindSync Notification System - Development Mode")
    
    # Create notification manager
    manager = create_notification_manager(development_mode=True)
    
    # Test creating notifications
    test_technician = "tech_007"
    
    # Create a safety alert
    safety_id = create_safety_alert(
        manager,
        "High Wind Warning",
        "Wind speeds exceeding 25 mph detected. Suspend tower work immediately.",
        test_technician,
        {"wind_speed": 28, "location": "North Ridge"}
    )
    print(f"Created safety alert: {safety_id}")
    
    # Create a task update
    task_id = create_task_update(
        manager,
        "Work Order Updated",
        "Priority changed to HIGH for gearbox inspection on WTG-A01",
        test_technician,
        "high",
        {"work_order_id": 123, "asset_id": "WTG-A01"}
    )
    print(f"Created task update: {task_id}")
    
    # Get notifications
    notifications = manager.get_notifications(test_technician)
    print(f"Retrieved {len(notifications)} notifications for {test_technician}")
    
    for notification in notifications:
        print(f"- {notification['title']} ({notification['priority']})")
    
    print("Notification system test completed successfully!")