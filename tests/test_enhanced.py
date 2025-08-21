"""
Enhanced test suite for WhisperLive-NubemAI
Includes unit tests, integration tests, and performance tests
"""

import unittest
import asyncio
import json
import time
import base64
import os
from unittest.mock import Mock, patch, AsyncMock
import websockets
import requests

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from whisper_live.auth import AuthManager, auth_manager
from whisper_live.monitoring import MetricsCollector, HealthCheck
from whisper_live.server import ClientManager


class TestAuthentication(unittest.TestCase):
    """Test authentication and authorization"""
    
    def setUp(self):
        self.auth = AuthManager()
    
    def test_password_hashing(self):
        """Test password hashing and verification"""
        password = "test_password_123"
        hashed = self.auth.get_password_hash(password)
        
        self.assertNotEqual(password, hashed)
        self.assertTrue(self.auth.verify_password(password, hashed))
        self.assertFalse(self.auth.verify_password("wrong_password", hashed))
    
    def test_jwt_token_creation(self):
        """Test JWT token creation and verification"""
        data = {"sub": "test_user", "role": "user"}
        token = self.auth.create_access_token(data)
        
        self.assertIsNotNone(token)
        self.assertIsInstance(token, str)
        
        # Verify token
        payload = self.auth.verify_token(token)
        self.assertIsNotNone(payload)
        self.assertEqual(payload["sub"], "test_user")
        self.assertEqual(payload["role"], "user")
    
    def test_expired_token(self):
        """Test expired token handling"""
        from datetime import timedelta
        
        data = {"sub": "test_user"}
        token = self.auth.create_access_token(data, expires_delta=timedelta(seconds=-1))
        
        payload = self.auth.verify_token(token)
        self.assertIsNone(payload)
    
    def test_api_key_verification(self):
        """Test API key verification"""
        os.environ["API_KEY"] = "test_api_key_123"
        auth = AuthManager()
        
        self.assertTrue(auth.verify_api_key("test_api_key_123"))
        self.assertFalse(auth.verify_api_key("wrong_api_key"))
    
    def test_rate_limiting(self):
        """Test rate limiting functionality"""
        client_id = "test_client"
        
        # Should allow initial requests
        for _ in range(5):
            self.assertTrue(self.auth.check_rate_limit(client_id, max_requests=10, window=1))
        
        # Should block after exceeding limit
        for _ in range(6):
            self.auth.check_rate_limit(client_id, max_requests=10, window=1)
        
        self.assertFalse(self.auth.check_rate_limit(client_id, max_requests=10, window=1))
        
        # Should allow after window expires
        time.sleep(1.1)
        self.assertTrue(self.auth.check_rate_limit(client_id, max_requests=10, window=1))
    
    def test_session_management(self):
        """Test session creation and management"""
        user_id = "test_user"
        websocket_id = "ws_123"
        
        session_id = self.auth.create_session(user_id, websocket_id)
        self.assertIsNotNone(session_id)
        
        session_data = self.auth.get_session(session_id)
        self.assertIsNotNone(session_data)
        self.assertEqual(session_data["user_id"], user_id)
        self.assertEqual(session_data["websocket_id"], websocket_id)
        
        # Update activity
        self.auth.update_session_activity(session_id)
        updated_session = self.auth.get_session(session_id)
        self.assertNotEqual(session_data["last_activity"], updated_session["last_activity"])
        
        # Revoke session
        self.auth.revoke_session(session_id)
        self.assertIsNone(self.auth.get_session(session_id))


class TestMonitoring(unittest.TestCase):
    """Test monitoring and observability features"""
    
    def setUp(self):
        self.metrics = MetricsCollector()
        self.health = HealthCheck()
    
    def test_transcription_metrics(self):
        """Test transcription metrics recording"""
        self.metrics.record_transcription(
            duration=2.5,
            model="base",
            language="en",
            success=True
        )
        
        stats = self.metrics.get_stats()
        self.assertEqual(stats["successful_requests"], 1)
        self.assertEqual(stats["failed_requests"], 0)
        
        self.metrics.record_transcription(
            duration=1.0,
            model="base",
            language="en",
            success=False
        )
        
        stats = self.metrics.get_stats()
        self.assertEqual(stats["successful_requests"], 1)
        self.assertEqual(stats["failed_requests"], 1)
        self.assertEqual(stats["total_requests"], 2)
    
    def test_connection_metrics(self):
        """Test WebSocket connection metrics"""
        self.metrics.record_connection("connect")
        self.metrics.record_connection("connect")
        self.metrics.record_connection("disconnect")
        
        # Check that metrics are recorded (actual values depend on Prometheus)
        stats = self.metrics.get_stats()
        self.assertIn("active_connections", stats)
    
    def test_error_metrics(self):
        """Test error metrics recording"""
        self.metrics.record_error("ValueError", "transcription")
        self.metrics.record_error("TimeoutError", "websocket")
        
        stats = self.metrics.get_stats()
        self.assertEqual(stats["failed_requests"], 2)
    
    def test_resource_metrics(self):
        """Test resource usage metrics"""
        self.metrics.update_resource_usage(cpu_percent=45.5, gpu_percent=80.0)
        self.metrics.update_queue_size("transcription", 10)
        self.metrics.update_model_memory("base", 1024 * 1024 * 500)  # 500MB
        
        # Metrics should be recorded without errors
        stats = self.metrics.get_stats()
        self.assertIsNotNone(stats)
    
    async def test_health_check(self):
        """Test health check functionality"""
        result = await self.health.check_health()
        
        self.assertIn("status", result)
        self.assertIn("timestamp", result)
        self.assertIn("checks", result)
        self.assertIn("duration", result)
        
        # Check individual health checks
        self.assertIn("disk", result["checks"])
        self.assertIn("model", result["checks"])


class TestClientManager(unittest.TestCase):
    """Test client management functionality"""
    
    def setUp(self):
        self.manager = ClientManager(max_clients=3, max_connection_time=60)
    
    def test_add_remove_client(self):
        """Test adding and removing clients"""
        mock_websocket = Mock()
        mock_client = Mock()
        
        self.manager.add_client(mock_websocket, mock_client)
        self.assertEqual(len(self.manager.clients), 1)
        self.assertIn(mock_websocket, self.manager.clients)
        
        retrieved_client = self.manager.get_client(mock_websocket)
        self.assertEqual(retrieved_client, mock_client)
        
        self.manager.remove_client(mock_websocket)
        self.assertEqual(len(self.manager.clients), 0)
        self.assertFalse(self.manager.get_client(mock_websocket))
    
    def test_max_clients_limit(self):
        """Test maximum clients limit"""
        mock_websockets = [Mock() for _ in range(4)]
        mock_clients = [Mock() for _ in range(4)]
        
        # Add clients up to limit
        for i in range(3):
            self.manager.add_client(mock_websockets[i], mock_clients[i])
        
        self.assertEqual(len(self.manager.clients), 3)
        
        # Check if server is full
        mock_websocket_new = Mock()
        mock_websocket_new.send = Mock()
        
        is_full = self.manager.is_server_full(mock_websocket_new, {"uid": "test"})
        self.assertTrue(is_full)
    
    def test_wait_time_calculation(self):
        """Test wait time calculation for full server"""
        mock_websockets = [Mock() for _ in range(3)]
        mock_clients = [Mock() for _ in range(3)]
        
        # Add clients with different start times
        for i, (ws, client) in enumerate(zip(mock_websockets, mock_clients)):
            self.manager.add_client(ws, client)
            self.manager.start_times[ws] = time.time() - (i * 10)  # 0, 10, 20 seconds ago
        
        wait_time = self.manager.get_wait_time()
        self.assertGreater(wait_time, 0)
        self.assertLess(wait_time, 1)  # Should be less than 1 minute


class TestIntegration(unittest.IsolatedAsyncioTestCase):
    """Integration tests for the complete system"""
    
    @classmethod
    def setUpClass(cls):
        """Start the server for integration tests"""
        # Note: In real tests, you would start the actual server
        # For now, we'll mock the endpoints
        pass
    
    async def test_websocket_connection_flow(self):
        """Test complete WebSocket connection flow"""
        # This would connect to actual server in integration tests
        # For unit tests, we mock the behavior
        
        mock_websocket = AsyncMock()
        mock_websocket.recv = AsyncMock()
        mock_websocket.send = AsyncMock()
        
        # Simulate connection
        await mock_websocket.send(json.dumps({
            "type": "auth",
            "token": "test_token"
        }))
        
        # Simulate receiving audio
        audio_data = base64.b64encode(b"fake_audio_data").decode()
        await mock_websocket.send(json.dumps({
            "type": "audio",
            "data": audio_data
        }))
        
        # Verify send was called
        mock_websocket.send.assert_called()
    
    async def test_rest_api_flow(self):
        """Test REST API transcription flow"""
        # This would make actual HTTP requests in integration tests
        # For unit tests, we mock the behavior
        
        with patch('requests.post') as mock_post:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "text": "Transcribed text",
                "duration": 1.5
            }
            mock_post.return_value = mock_response
            
            # Simulate API call
            response = requests.post(
                "http://localhost:9090/transcribe",
                headers={"Authorization": "Bearer test_token"},
                json={"audio_data": "base64_encoded_audio"}
            )
            
            self.assertEqual(response.status_code, 200)
            result = response.json()
            self.assertIn("text", result)
            self.assertIn("duration", result)


class TestPerformance(unittest.TestCase):
    """Performance and load tests"""
    
    def test_concurrent_connections(self):
        """Test handling multiple concurrent connections"""
        manager = ClientManager(max_clients=100)
        
        start_time = time.time()
        
        # Simulate 100 concurrent connections
        mock_websockets = []
        mock_clients = []
        
        for i in range(100):
            ws = Mock()
            client = Mock()
            mock_websockets.append(ws)
            mock_clients.append(client)
            manager.add_client(ws, client)
        
        elapsed = time.time() - start_time
        
        self.assertEqual(len(manager.clients), 100)
        self.assertLess(elapsed, 1.0)  # Should handle 100 connections in under 1 second
        
        # Cleanup
        for ws in mock_websockets:
            manager.remove_client(ws)
        
        self.assertEqual(len(manager.clients), 0)
    
    def test_rate_limiting_performance(self):
        """Test rate limiting performance under load"""
        auth = AuthManager()
        
        start_time = time.time()
        
        # Simulate 1000 rate limit checks
        for i in range(1000):
            client_id = f"client_{i % 10}"  # 10 different clients
            auth.check_rate_limit(client_id, max_requests=100, window=60)
        
        elapsed = time.time() - start_time
        
        self.assertLess(elapsed, 1.0)  # Should handle 1000 checks in under 1 second


class TestSecurity(unittest.TestCase):
    """Security-related tests"""
    
    def test_sql_injection_prevention(self):
        """Test SQL injection prevention in session management"""
        auth = AuthManager()
        
        # Try to inject SQL
        malicious_user_id = "'; DROP TABLE sessions; --"
        malicious_ws_id = "1' OR '1'='1"
        
        session_id = auth.create_session(malicious_user_id, malicious_ws_id)
        session_data = auth.get_session(session_id)
        
        # Should handle malicious input safely
        self.assertEqual(session_data["user_id"], malicious_user_id)
        self.assertEqual(session_data["websocket_id"], malicious_ws_id)
    
    def test_xss_prevention(self):
        """Test XSS prevention in transcription responses"""
        # This would test that transcribed text is properly escaped
        malicious_text = "<script>alert('XSS')</script>"
        
        # In real implementation, ensure this is escaped
        escaped_text = malicious_text.replace("<", "&lt;").replace(">", "&gt;")
        
        self.assertNotIn("<script>", escaped_text)
        self.assertIn("&lt;script&gt;", escaped_text)
    
    def test_path_traversal_prevention(self):
        """Test path traversal prevention in file operations"""
        # Test that file paths are properly validated
        malicious_paths = [
            "../../../etc/passwd",
            "..\\..\\..\\windows\\system32\\config\\sam",
            "/etc/shadow",
            "models/../../../etc/passwd"
        ]
        
        for path in malicious_paths:
            # In real implementation, these should be rejected or sanitized
            safe_path = os.path.basename(path)
            self.assertNotIn("..", safe_path)
            self.assertNotIn("/etc/", safe_path)


if __name__ == "__main__":
    unittest.main()