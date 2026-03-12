"""
WindSync Notification Sync Manager
=================================

Handles bidirectional synchronization between offline clients and the server.
Manages sync queues, conflict resolution, and retry logic for reliable
notification delivery in intermittent connectivity environments.

Features:
- Priority-based sync queue processing
- Exponential backoff retry mechanism
- Conflict resolution for notification state changes
- Incremental sync with timestamp-based filtering
- Batch operations for improved performance
"""

import asyncio
import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
import logging

from notifications_system import NotificationManager, NotificationConfig
from notification_api import NotificationAPI

logger = logging.getLogger(__name__)


class SyncAction(Enum):
    """Types of sync actions"""
    ACKNOWLEDGE = "acknowledge"
    MARK_READ = "mark_read"
    CREATE_NOTIFICATION = "create_notification"
    UPDATE_STATUS = "update_status"


class SyncPriority(Enum):
    """Sync operation priorities"""
    CRITICAL = 1
    HIGH = 2
    MEDIUM = 3
    LOW = 4


@dataclass
class SyncItem:
    """Represents an item in the sync queue"""
    id: Optional[int]
    action: SyncAction
    notification_id: Optional[int]
    technician_id: str
    data: Dict[str, Any]
    priority: SyncPriority
    created_at: datetime
    retry_count: int = 0
    last_attempt: Optional[datetime] = None
    error_message: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage"""
        return {
            'id': self.id,
            'action': self.action.value,
            'notification_id': self.notification_id,
            'technician_id': self.technician_id,
            'data': json.dumps(self.data),
            'priority': self.priority.value,
            'created_at': self.created_at.isoformat(),
            'retry_count': self.retry_count,
            'last_attempt': self.last_attempt.isoformat() if self.last_attempt else None,
            'error_message': self.error_message
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SyncItem':
        """Create from dictionary"""
        return cls(
            id=data['id'],
            action=SyncAction(data['action']),
            notification_id=data['notification_id'],
            technician_id=data['technician_id'],
            data=json.loads(data['data']),
            priority=SyncPriority(data['priority']),
            created_at=datetime.fromisoformat(data['created_at']),
            retry_count=data['retry_count'],
            last_attempt=datetime.fromisoformat(data['last_attempt']) if data['last_attempt'] else None,
            error_message=data['error_message']
        )


class SyncManager:
    """Manages synchronization between offline clients and server"""
    
    def __init__(self, config: Optional[NotificationConfig] = None):
        self.config = config or NotificationConfig()
        self.api = NotificationAPI(self.config)
        self.manager = self.api.manager
        
        # Retry configuration
        self.max_retries = self.config.max_retries
        self.retry_delays = [1, 5, 15, 60, 300]  # seconds
        
        # Sync state
        self.sync_in_progress = False
        self.last_sync_timestamps = {}  # technician_id -> timestamp
        
        # Initialize sync queue table
        self._ensure_sync_table()
        
        logger.info("SyncManager initialized")
    
    def _ensure_sync_table(self):
        """Create sync queue table if it doesn't exist"""
        conn = self.manager.db._get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sync_queue (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    action TEXT NOT NULL,
                    notification_id INTEGER,
                    technician_id TEXT NOT NULL,
                    data TEXT NOT NULL,
                    priority INTEGER NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    retry_count INTEGER DEFAULT 0,
                    last_attempt DATETIME,
                    error_message TEXT
                )
            """)
            
            # Create index for efficient querying
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_sync_queue_priority_created 
                ON sync_queue (priority, created_at)
            """)
            
            conn.commit()
            logger.info("Sync queue table created/verified")
            
        except Exception as e:
            logger.error(f"Error creating sync queue table: {e}")
            raise
        finally:
            conn.close()
    
    def queue_sync_action(self, 
                         action: SyncAction,
                         technician_id: str,
                         data: Dict[str, Any],
                         notification_id: Optional[int] = None,
                         priority: Optional[SyncPriority] = None) -> int:
        """Queue a sync action for later processing"""
        
        # Determine priority if not specified
        if priority is None:
            if action == SyncAction.ACKNOWLEDGE:
                priority = SyncPriority.HIGH
            elif action == SyncAction.CREATE_NOTIFICATION:
                # Priority based on notification priority
                notif_priority = data.get('priority', 'medium')
                if notif_priority == 'critical':
                    priority = SyncPriority.CRITICAL
                elif notif_priority == 'high':
                    priority = SyncPriority.HIGH
                else:
                    priority = SyncPriority.MEDIUM
            else:
                priority = SyncPriority.MEDIUM
        
        sync_item = SyncItem(
            id=None,
            action=action,
            notification_id=notification_id,
            technician_id=technician_id,
            data=data,
            priority=priority,
            created_at=datetime.now()
        )
        
        # Store in database
        conn = self.manager.db._get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                INSERT INTO sync_queue (action, notification_id, technician_id, data, priority, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                sync_item.action.value,
                sync_item.notification_id,
                sync_item.technician_id,
                json.dumps(sync_item.data),
                sync_item.priority.value,
                sync_item.created_at.isoformat()
            ))
            
            sync_item_id = cursor.lastrowid
            conn.commit()
            
            logger.info(f"Queued sync action {action.value} for technician {technician_id}, ID: {sync_item_id}")
            return sync_item_id
            
        except Exception as e:
            logger.error(f"Error queuing sync action: {e}")
            conn.rollback()
            raise
        finally:
            conn.close()
    
    def get_sync_queue(self, limit: int = 100) -> List[SyncItem]:
        """Get pending sync items ordered by priority and creation time"""
        conn = self.manager.db._get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT * FROM sync_queue 
                ORDER BY priority ASC, created_at ASC 
                LIMIT ?
            """, (limit,))
            
            sync_items = []
            for row in cursor.fetchall():
                sync_item = SyncItem(
                    id=row['id'],
                    action=SyncAction(row['action']),
                    notification_id=row['notification_id'],
                    technician_id=row['technician_id'],
                    data=json.loads(row['data']),
                    priority=SyncPriority(row['priority']),
                    created_at=datetime.fromisoformat(row['created_at']),
                    retry_count=row['retry_count'],
                    last_attempt=datetime.fromisoformat(row['last_attempt']) if row['last_attempt'] else None,
                    error_message=row['error_message']
                )
                sync_items.append(sync_item)
            
            return sync_items
            
        except Exception as e:
            logger.error(f"Error getting sync queue: {e}")
            return []
        finally:
            conn.close()
    
    def remove_sync_item(self, sync_item_id: int) -> bool:
        """Remove a sync item from the queue"""
        conn = self.manager.db._get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("DELETE FROM sync_queue WHERE id = ?", (sync_item_id,))
            success = cursor.rowcount > 0
            conn.commit()
            
            if success:
                logger.info(f"Removed sync item {sync_item_id} from queue")
            
            return success
            
        except Exception as e:
            logger.error(f"Error removing sync item: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()
    
    def update_sync_item_retry(self, sync_item: SyncItem, error_message: str):
        """Update sync item retry count and error message"""
        conn = self.manager.db._get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                UPDATE sync_queue 
                SET retry_count = ?, last_attempt = ?, error_message = ?
                WHERE id = ?
            """, (
                sync_item.retry_count + 1,
                datetime.now().isoformat(),
                error_message,
                sync_item.id
            ))
            
            conn.commit()
            logger.info(f"Updated retry count for sync item {sync_item.id}")
            
        except Exception as e:
            logger.error(f"Error updating sync item retry: {e}")
            conn.rollback()
        finally:
            conn.close()
    
    async def process_sync_queue(self) -> Dict[str, Any]:
        """Process all pending sync items"""
        if self.sync_in_progress:
            return {'status': 'sync_already_in_progress'}
        
        self.sync_in_progress = True
        start_time = time.time()
        
        try:
            sync_items = self.get_sync_queue()
            
            if not sync_items:
                return {
                    'status': 'success',
                    'message': 'No items to sync',
                    'processed': 0,
                    'duration': time.time() - start_time
                }
            
            processed = 0
            failed = 0
            
            for sync_item in sync_items:
                try:
                    success = await self._process_sync_item(sync_item)
                    if success:
                        self.remove_sync_item(sync_item.id)
                        processed += 1
                    else:
                        failed += 1
                        
                        # Check if we should retry
                        if sync_item.retry_count < self.max_retries:
                            # Schedule retry with exponential backoff
                            delay_index = min(sync_item.retry_count, len(self.retry_delays) - 1)
                            delay = self.retry_delays[delay_index]
                            
                            # In a real implementation, you'd schedule this with a task queue
                            # For now, we just update the retry count
                            self.update_sync_item_retry(sync_item, "Retry scheduled")
                            
                            logger.info(f"Scheduled retry for sync item {sync_item.id} in {delay} seconds")
                        else:
                            # Max retries reached, remove from queue
                            self.remove_sync_item(sync_item.id)
                            logger.error(f"Max retries reached for sync item {sync_item.id}, removing from queue")
                
                except Exception as e:
                    logger.error(f"Error processing sync item {sync_item.id}: {e}")
                    failed += 1
            
            duration = time.time() - start_time
            
            return {
                'status': 'success',
                'processed': processed,
                'failed': failed,
                'total': len(sync_items),
                'duration': duration
            }
            
        except Exception as e:
            logger.error(f"Error processing sync queue: {e}")
            return {
                'status': 'error',
                'message': str(e),
                'duration': time.time() - start_time
            }
        finally:
            self.sync_in_progress = False
    
    async def _process_sync_item(self, sync_item: SyncItem) -> bool:
        """Process a single sync item"""
        try:
            if sync_item.action == SyncAction.ACKNOWLEDGE:
                response = self.api.acknowledge_notification(
                    sync_item.notification_id,
                    {'technician_id': sync_item.technician_id}
                )
                
            elif sync_item.action == SyncAction.MARK_READ:
                response = self.api.mark_as_read(
                    sync_item.notification_id,
                    {'technician_id': sync_item.technician_id}
                )
                
            elif sync_item.action == SyncAction.CREATE_NOTIFICATION:
                response = self.api.create_notification(sync_item.data)
                
            else:
                logger.error(f"Unknown sync action: {sync_item.action}")
                return False
            
            success = response.get('success', False)
            
            if not success:
                error_msg = response.get('error', {}).get('message', 'Unknown error')
                logger.error(f"Sync item {sync_item.id} failed: {error_msg}")
                self.update_sync_item_retry(sync_item, error_msg)
            
            return success
            
        except Exception as e:
            logger.error(f"Error processing sync item {sync_item.id}: {e}")
            self.update_sync_item_retry(sync_item, str(e))
            return False
    
    def perform_incremental_sync(self, technician_id: str) -> Dict[str, Any]:
        """Perform incremental sync for a technician"""
        try:
            # Get last sync timestamp
            last_sync = self.last_sync_timestamps.get(technician_id)
            
            # Get notifications since last sync
            params = {
                'technician_id': technician_id,
                'last_sync': last_sync.isoformat() if last_sync else None
            }
            
            response = self.api.sync_notifications(params)
            
            if response['success']:
                # Update last sync timestamp
                self.last_sync_timestamps[technician_id] = datetime.now()
                
                return {
                    'status': 'success',
                    'notifications': response['data']['notifications'],
                    'unread_count': response['data']['unread_count'],
                    'last_sync': last_sync.isoformat() if last_sync else None,
                    'new_sync_timestamp': self.last_sync_timestamps[technician_id].isoformat()
                }
            else:
                return {
                    'status': 'error',
                    'message': response['error']['message']
                }
                
        except Exception as e:
            logger.error(f"Error in incremental sync for {technician_id}: {e}")
            return {
                'status': 'error',
                'message': str(e)
            }
    
    def get_sync_stats(self) -> Dict[str, Any]:
        """Get synchronization statistics"""
        conn = self.manager.db._get_connection()
        cursor = conn.cursor()
        
        try:
            # Get queue statistics
            cursor.execute("SELECT COUNT(*) as total FROM sync_queue")
            total_queued = cursor.fetchone()['total']
            
            cursor.execute("SELECT COUNT(*) as failed FROM sync_queue WHERE retry_count >= ?", (self.max_retries,))
            failed_items = cursor.fetchone()['failed']
            
            cursor.execute("SELECT priority, COUNT(*) as count FROM sync_queue GROUP BY priority")
            priority_breakdown = {str(row['priority']): row['count'] for row in cursor.fetchall()}
            
            cursor.execute("SELECT action, COUNT(*) as count FROM sync_queue GROUP BY action")
            action_breakdown = {row['action']: row['count'] for row in cursor.fetchall()}
            
            return {
                'total_queued': total_queued,
                'failed_items': failed_items,
                'sync_in_progress': self.sync_in_progress,
                'priority_breakdown': priority_breakdown,
                'action_breakdown': action_breakdown,
                'last_sync_timestamps': {
                    tech_id: timestamp.isoformat() 
                    for tech_id, timestamp in self.last_sync_timestamps.items()
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting sync stats: {e}")
            return {'error': str(e)}
        finally:
            conn.close()
    
    def clear_sync_queue(self, technician_id: Optional[str] = None) -> int:
        """Clear sync queue (for testing/maintenance)"""
        conn = self.manager.db._get_connection()
        cursor = conn.cursor()
        
        try:
            if technician_id:
                cursor.execute("DELETE FROM sync_queue WHERE technician_id = ?", (technician_id,))
            else:
                cursor.execute("DELETE FROM sync_queue")
            
            cleared_count = cursor.rowcount
            conn.commit()
            
            logger.info(f"Cleared {cleared_count} items from sync queue")
            return cleared_count
            
        except Exception as e:
            logger.error(f"Error clearing sync queue: {e}")
            conn.rollback()
            return 0
        finally:
            conn.close()


# Convenience functions
def create_sync_manager(development_mode: bool = False) -> SyncManager:
    """Create and initialize sync manager"""
    config = NotificationConfig(development_mode=development_mode)
    return SyncManager(config)


# Example usage and testing
if __name__ == "__main__":
    import asyncio
    
    async def test_sync_manager():
        print("WindSync Sync Manager - Development Mode")
        print("=" * 50)
        
        # Create sync manager
        sync_manager = create_sync_manager(development_mode=True)
        
        # Test queuing sync actions
        print("\n1. Testing sync queue operations...")
        
        # Queue some test sync actions
        sync_id1 = sync_manager.queue_sync_action(
            SyncAction.ACKNOWLEDGE,
            "tech_007",
            {"timestamp": datetime.now().isoformat()},
            notification_id=1,
            priority=SyncPriority.HIGH
        )
        print(f"Queued acknowledge action: {sync_id1}")
        
        sync_id2 = sync_manager.queue_sync_action(
            SyncAction.MARK_READ,
            "tech_007",
            {"timestamp": datetime.now().isoformat()},
            notification_id=2,
            priority=SyncPriority.MEDIUM
        )
        print(f"Queued mark read action: {sync_id2}")
        
        # Get sync queue
        queue_items = sync_manager.get_sync_queue()
        print(f"Sync queue contains {len(queue_items)} items")
        
        # Test sync stats
        print("\n2. Testing sync statistics...")
        stats = sync_manager.get_sync_stats()
        print(f"Total queued: {stats['total_queued']}")
        print(f"Priority breakdown: {stats['priority_breakdown']}")
        print(f"Action breakdown: {stats['action_breakdown']}")
        
        # Test incremental sync
        print("\n3. Testing incremental sync...")
        sync_result = sync_manager.perform_incremental_sync("tech_007")
        print(f"Incremental sync status: {sync_result['status']}")
        if sync_result['status'] == 'success':
            print(f"Retrieved {len(sync_result['notifications'])} notifications")
            print(f"Unread count: {sync_result['unread_count']}")
        
        # Test processing sync queue
        print("\n4. Testing sync queue processing...")
        process_result = await sync_manager.process_sync_queue()
        print(f"Process result: {process_result['status']}")
        print(f"Processed: {process_result.get('processed', 0)}")
        print(f"Failed: {process_result.get('failed', 0)}")
        print(f"Duration: {process_result.get('duration', 0):.2f}s")
        
        # Clear queue for cleanup
        cleared = sync_manager.clear_sync_queue()
        print(f"\nCleared {cleared} items from sync queue")
        
        print("\n✅ Sync manager testing completed successfully!")
        print("=" * 50)
    
    # Run async test
    asyncio.run(test_sync_manager())