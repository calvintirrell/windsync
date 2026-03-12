"""
WindSync Notification API
========================

RESTful API endpoints for the notification system that can be integrated
with Streamlit or used as a standalone FastAPI service.

This module provides:
- REST API endpoints for notification CRUD operations
- Streamlit query parameter integration
- JSON response formatting
- Error handling and validation
"""

import json
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union
from dataclasses import asdict
import logging

from notifications_system import (
    NotificationManager, NotificationConfig, NotificationData,
    NotificationPriority, NotificationCategory
)

logger = logging.getLogger(__name__)


class NotificationAPI:
    """RESTful API interface for the notification system"""
    
    def __init__(self, config: Optional[NotificationConfig] = None):
        self.config = config or NotificationConfig()
        self.manager = NotificationManager(self.config)
        self.manager.initialize()
    
    def create_notification(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        POST /api/notifications
        Create a new notification
        """
        try:
            # Validate required fields
            required_fields = ['title', 'message', 'priority', 'technician_id']
            for field in required_fields:
                if field not in data:
                    return self._error_response(f"Missing required field: {field}", 400)
            
            # Validate priority and category
            try:
                priority = NotificationPriority(data['priority'].lower())
            except ValueError:
                return self._error_response(f"Invalid priority: {data['priority']}", 400)
            
            category = data.get('category', 'system')
            try:
                category = NotificationCategory(category.lower())
            except ValueError:
                return self._error_response(f"Invalid category: {category}", 400)
            
            # Create notification
            notification_id = self.manager.create_alert(
                title=data['title'],
                message=data['message'],
                priority=priority,
                technician_id=data['technician_id'],
                category=category,
                metadata=data.get('metadata'),
                requires_acknowledgment=data.get('requires_acknowledgment')
            )
            
            return self._success_response({
                'notification_id': notification_id,
                'message': 'Notification created successfully'
            })
            
        except Exception as e:
            logger.error(f"Error creating notification: {e}")
            return self._error_response(f"Internal server error: {str(e)}", 500)
    
    def get_notifications(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        GET /api/notifications
        Fetch notifications for a technician
        """
        try:
            technician_id = params.get('technician_id')
            if not technician_id:
                return self._error_response("Missing required parameter: technician_id", 400)
            
            # Parse optional parameters
            since_str = params.get('since')
            since_timestamp = None
            if since_str:
                try:
                    since_timestamp = datetime.fromisoformat(since_str.replace('Z', '+00:00'))
                except ValueError:
                    return self._error_response("Invalid since timestamp format", 400)
            
            limit = int(params.get('limit', 100))
            if limit > 1000:
                limit = 1000  # Cap at 1000 for performance
            
            # Get notifications
            notifications = self.manager.get_notifications(technician_id, since_timestamp)
            
            # Apply limit
            if len(notifications) > limit:
                notifications = notifications[:limit]
            
            # Format response
            return self._success_response({
                'notifications': notifications,
                'count': len(notifications),
                'technician_id': technician_id,
                'since': since_str,
                'limit': limit
            })
            
        except Exception as e:
            logger.error(f"Error fetching notifications: {e}")
            return self._error_response(f"Internal server error: {str(e)}", 500)
    
    def acknowledge_notification(self, notification_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        PUT /api/notifications/{id}/acknowledge
        Acknowledge a notification
        """
        try:
            technician_id = data.get('technician_id')
            if not technician_id:
                return self._error_response("Missing required field: technician_id", 400)
            
            success = self.manager.acknowledge_notification(notification_id, technician_id)
            
            if success:
                return self._success_response({
                    'message': 'Notification acknowledged successfully',
                    'notification_id': notification_id,
                    'technician_id': technician_id,
                    'acknowledged_at': datetime.now().isoformat()
                })
            else:
                return self._error_response("Notification not found or already acknowledged", 404)
                
        except Exception as e:
            logger.error(f"Error acknowledging notification: {e}")
            return self._error_response(f"Internal server error: {str(e)}", 500)
    
    def mark_as_read(self, notification_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        PUT /api/notifications/{id}/read
        Mark notification as read
        """
        try:
            technician_id = data.get('technician_id')
            if not technician_id:
                return self._error_response("Missing required field: technician_id", 400)
            
            success = self.manager.mark_as_read(notification_id, technician_id)
            
            if success:
                return self._success_response({
                    'message': 'Notification marked as read',
                    'notification_id': notification_id,
                    'technician_id': technician_id,
                    'read_at': datetime.now().isoformat()
                })
            else:
                return self._error_response("Notification not found or already read", 404)
                
        except Exception as e:
            logger.error(f"Error marking notification as read: {e}")
            return self._error_response(f"Internal server error: {str(e)}", 500)
    
    def sync_notifications(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        GET /api/notifications/sync
        Sync endpoint for offline clients
        """
        try:
            technician_id = params.get('technician_id')
            if not technician_id:
                return self._error_response("Missing required parameter: technician_id", 400)
            
            # Get last sync timestamp
            last_sync_str = params.get('last_sync')
            last_sync = None
            if last_sync_str:
                try:
                    last_sync = datetime.fromisoformat(last_sync_str.replace('Z', '+00:00'))
                except ValueError:
                    return self._error_response("Invalid last_sync timestamp format", 400)
            
            # Get notifications since last sync
            notifications = self.manager.get_notifications(technician_id, last_sync)
            
            # Get unread count
            unread_count = self.manager.get_unread_count(technician_id)
            
            # Current server timestamp for next sync
            server_timestamp = datetime.now().isoformat()
            
            return self._success_response({
                'notifications': notifications,
                'unread_count': unread_count,
                'server_timestamp': server_timestamp,
                'sync_timestamp': server_timestamp,
                'technician_id': technician_id
            })
            
        except Exception as e:
            logger.error(f"Error in sync endpoint: {e}")
            return self._error_response(f"Internal server error: {str(e)}", 500)
    
    def get_notification_stats(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        GET /api/notifications/stats
        Get notification statistics
        """
        try:
            technician_id = params.get('technician_id')
            if not technician_id:
                return self._error_response("Missing required parameter: technician_id", 400)
            
            notifications = self.manager.get_notifications(technician_id)
            
            # Calculate statistics
            total_count = len(notifications)
            unread_count = len([n for n in notifications if not n['read_at']])
            critical_count = len([n for n in notifications if n['priority'] == 'critical'])
            pending_ack_count = len([n for n in notifications if n['requires_acknowledgment'] and not n['acknowledged_at']])
            
            # Priority breakdown
            priority_stats = {}
            for priority in ['critical', 'high', 'medium', 'low']:
                priority_stats[priority] = len([n for n in notifications if n['priority'] == priority])
            
            # Category breakdown
            category_stats = {}
            for category in ['safety', 'task', 'equipment', 'system']:
                category_stats[category] = len([n for n in notifications if n['category'] == category])
            
            return self._success_response({
                'technician_id': technician_id,
                'total_notifications': total_count,
                'unread_notifications': unread_count,
                'critical_notifications': critical_count,
                'pending_acknowledgments': pending_ack_count,
                'priority_breakdown': priority_stats,
                'category_breakdown': category_stats,
                'last_updated': datetime.now().isoformat()
            })
            
        except Exception as e:
            logger.error(f"Error getting notification stats: {e}")
            return self._error_response(f"Internal server error: {str(e)}", 500)
    
    def health_check(self) -> Dict[str, Any]:
        """
        GET /api/health
        Health check endpoint
        """
        try:
            # Test database connection
            test_notifications = self.manager.get_notifications("health_check_test")
            
            return self._success_response({
                'status': 'healthy',
                'timestamp': datetime.now().isoformat(),
                'database': 'connected',
                'notification_system': 'operational'
            })
            
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return self._error_response(f"Health check failed: {str(e)}", 500)
    
    def _success_response(self, data: Any, status_code: int = 200) -> Dict[str, Any]:
        """Format successful API response"""
        return {
            'success': True,
            'status_code': status_code,
            'data': data,
            'timestamp': datetime.now().isoformat()
        }
    
    def _error_response(self, message: str, status_code: int = 400) -> Dict[str, Any]:
        """Format error API response"""
        return {
            'success': False,
            'status_code': status_code,
            'error': {
                'message': message,
                'code': status_code
            },
            'timestamp': datetime.now().isoformat()
        }


class StreamlitNotificationAPI:
    """Streamlit integration for notification API using query parameters"""
    
    def __init__(self, api: NotificationAPI):
        self.api = api
    
    def handle_request(self, query_params: Dict[str, List[str]]) -> Optional[Dict[str, Any]]:
        """
        Handle API requests via Streamlit query parameters
        
        Usage in Streamlit:
        query_params = st.experimental_get_query_params()
        response = streamlit_api.handle_request(query_params)
        if response:
            st.json(response)
            st.stop()
        """
        if 'api' not in query_params:
            return None
        
        api_action = query_params['api'][0]
        
        try:
            if api_action == 'notifications':
                return self._handle_get_notifications(query_params)
            elif api_action == 'create':
                return self._handle_create_notification(query_params)
            elif api_action == 'acknowledge':
                return self._handle_acknowledge(query_params)
            elif api_action == 'read':
                return self._handle_mark_read(query_params)
            elif api_action == 'sync':
                return self._handle_sync(query_params)
            elif api_action == 'stats':
                return self._handle_stats(query_params)
            elif api_action == 'health':
                return self.api.health_check()
            else:
                return self.api._error_response(f"Unknown API action: {api_action}", 400)
                
        except Exception as e:
            logger.error(f"Error handling Streamlit API request: {e}")
            return self.api._error_response(f"Request handling error: {str(e)}", 500)
    
    def _get_param(self, query_params: Dict[str, List[str]], key: str, default: Any = None) -> Any:
        """Get parameter from query params"""
        return query_params.get(key, [default])[0] if key in query_params else default
    
    def _handle_get_notifications(self, query_params: Dict[str, List[str]]) -> Dict[str, Any]:
        """Handle GET notifications request"""
        params = {
            'technician_id': self._get_param(query_params, 'technician_id'),
            'since': self._get_param(query_params, 'since'),
            'limit': self._get_param(query_params, 'limit', 100)
        }
        return self.api.get_notifications(params)
    
    def _handle_create_notification(self, query_params: Dict[str, List[str]]) -> Dict[str, Any]:
        """Handle create notification request"""
        data = {
            'title': self._get_param(query_params, 'title'),
            'message': self._get_param(query_params, 'message'),
            'priority': self._get_param(query_params, 'priority'),
            'technician_id': self._get_param(query_params, 'technician_id'),
            'category': self._get_param(query_params, 'category', 'system'),
            'requires_acknowledgment': self._get_param(query_params, 'requires_ack', 'false').lower() == 'true'
        }
        
        # Parse metadata if provided
        metadata_str = self._get_param(query_params, 'metadata')
        if metadata_str:
            try:
                data['metadata'] = json.loads(metadata_str)
            except json.JSONDecodeError:
                return self.api._error_response("Invalid JSON in metadata parameter", 400)
        
        return self.api.create_notification(data)
    
    def _handle_acknowledge(self, query_params: Dict[str, List[str]]) -> Dict[str, Any]:
        """Handle acknowledge notification request"""
        notification_id = self._get_param(query_params, 'notification_id')
        if not notification_id:
            return self.api._error_response("Missing notification_id parameter", 400)
        
        try:
            notification_id = int(notification_id)
        except ValueError:
            return self.api._error_response("Invalid notification_id format", 400)
        
        data = {
            'technician_id': self._get_param(query_params, 'technician_id')
        }
        
        return self.api.acknowledge_notification(notification_id, data)
    
    def _handle_mark_read(self, query_params: Dict[str, List[str]]) -> Dict[str, Any]:
        """Handle mark as read request"""
        notification_id = self._get_param(query_params, 'notification_id')
        if not notification_id:
            return self.api._error_response("Missing notification_id parameter", 400)
        
        try:
            notification_id = int(notification_id)
        except ValueError:
            return self.api._error_response("Invalid notification_id format", 400)
        
        data = {
            'technician_id': self._get_param(query_params, 'technician_id')
        }
        
        return self.api.mark_as_read(notification_id, data)
    
    def _handle_sync(self, query_params: Dict[str, List[str]]) -> Dict[str, Any]:
        """Handle sync request"""
        params = {
            'technician_id': self._get_param(query_params, 'technician_id'),
            'last_sync': self._get_param(query_params, 'last_sync')
        }
        return self.api.sync_notifications(params)
    
    def _handle_stats(self, query_params: Dict[str, List[str]]) -> Dict[str, Any]:
        """Handle stats request"""
        params = {
            'technician_id': self._get_param(query_params, 'technician_id')
        }
        return self.api.get_notification_stats(params)


# Convenience functions for easy integration
def create_notification_api(development_mode: bool = False) -> NotificationAPI:
    """Create and initialize notification API"""
    config = NotificationConfig(development_mode=development_mode)
    return NotificationAPI(config)


def create_streamlit_api(development_mode: bool = False) -> StreamlitNotificationAPI:
    """Create Streamlit-integrated notification API"""
    api = create_notification_api(development_mode)
    return StreamlitNotificationAPI(api)


# Example usage and testing
if __name__ == "__main__":
    print("WindSync Notification API - Development Mode")
    print("=" * 50)
    
    # Create API instance
    api = create_notification_api(development_mode=True)
    
    # Test health check
    print("\n1. Testing health check...")
    health_response = api.health_check()
    print(f"Health check: {health_response['success']}")
    
    # Test create notification
    print("\n2. Testing create notification...")
    create_data = {
        'title': 'API Test Notification',
        'message': 'This is a test notification created via API',
        'priority': 'high',
        'technician_id': 'tech_007',
        'category': 'system',
        'metadata': {'test': True, 'api_version': '1.0'}
    }
    
    create_response = api.create_notification(create_data)
    print(f"Create notification: {create_response['success']}")
    if create_response['success']:
        notification_id = create_response['data']['notification_id']
        print(f"Created notification ID: {notification_id}")
    
    # Test get notifications
    print("\n3. Testing get notifications...")
    get_params = {'technician_id': 'tech_007', 'limit': 10}
    get_response = api.get_notifications(get_params)
    print(f"Get notifications: {get_response['success']}")
    if get_response['success']:
        count = get_response['data']['count']
        print(f"Retrieved {count} notifications")
    
    # Test stats
    print("\n4. Testing notification stats...")
    stats_params = {'technician_id': 'tech_007'}
    stats_response = api.get_notification_stats(stats_params)
    print(f"Get stats: {stats_response['success']}")
    if stats_response['success']:
        total = stats_response['data']['total_notifications']
        unread = stats_response['data']['unread_notifications']
        print(f"Stats: {total} total, {unread} unread")
    
    # Test Streamlit integration
    print("\n5. Testing Streamlit integration...")
    streamlit_api = StreamlitNotificationAPI(api)
    
    # Simulate Streamlit query params
    test_query_params = {
        'api': ['notifications'],
        'technician_id': ['tech_007'],
        'limit': ['5']
    }
    
    streamlit_response = streamlit_api.handle_request(test_query_params)
    if streamlit_response:
        print(f"Streamlit API: {streamlit_response['success']}")
        if streamlit_response['success']:
            count = streamlit_response['data']['count']
            print(f"Streamlit retrieved {count} notifications")
    
    print("\n✅ API testing completed successfully!")
    print("=" * 50)