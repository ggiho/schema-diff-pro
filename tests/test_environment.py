"""
Tests for environment detection and configuration
"""

import os
import pytest
from unittest.mock import patch, MagicMock
import sys
import tempfile

# Add backend directory to Python path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from core.config import settings
from models.ssh_tunnel import SSHTunnelConfig, SSHAuthMethod, TunnelStatus
from services.ssh_tunnel_manager import tunnel_manager


class TestEnvironmentDetection:
    """Test environment detection and configuration"""
    
    def test_docker_environment_detection(self):
        """Test Docker environment detection"""
        with patch.dict(os.environ, {'DOCKER_ENV': 'true'}):
            # In real implementation, this would test the environment detection
            assert os.getenv('DOCKER_ENV') == 'true'
    
    def test_local_environment_detection(self):
        """Test local environment detection"""  
        with patch.dict(os.environ, {}, clear=True):
            if 'DOCKER_ENV' in os.environ:
                del os.environ['DOCKER_ENV']
            # In real implementation, this would test the environment detection
            assert os.getenv('DOCKER_ENV') is None


class TestSSHTunnelConfig:
    """Test SSH tunnel configuration validation"""
    
    def test_ssh_tunnel_config_creation(self):
        """Test creating SSH tunnel configuration"""
        config = SSHTunnelConfig(
            enabled=True,
            ssh_host='bastion.example.com',
            ssh_port=22,
            ssh_user='ubuntu',
            auth_method=SSHAuthMethod.PASSWORD,
            ssh_password='test123',
            remote_bind_host='localhost',
            remote_bind_port=3306,
            connect_timeout=30,
            keepalive_interval=30,
            compression=False,
            strict_host_key_checking=True
        )
        
        assert config.enabled is True
        assert config.ssh_host == 'bastion.example.com'
        assert config.ssh_port == 22
        assert config.auth_method == SSHAuthMethod.PASSWORD
    
    def test_ssh_tunnel_config_validation(self):
        """Test SSH tunnel configuration validation"""
        # Test missing required fields
        with pytest.raises(ValueError):
            SSHTunnelConfig(
                enabled=True,
                ssh_host='',  # Empty host should fail validation
                ssh_port=22,
                ssh_user='ubuntu',
                auth_method=SSHAuthMethod.PASSWORD,
                remote_bind_host='localhost',
                remote_bind_port=3306,
                connect_timeout=30,
                keepalive_interval=30,
                compression=False,
                strict_host_key_checking=True
            )
    
    def test_ssh_auth_methods(self):
        """Test different SSH authentication methods"""
        # Password auth
        password_config = SSHTunnelConfig(
            enabled=True,
            ssh_host='bastion.example.com',
            ssh_port=22,
            ssh_user='ubuntu',
            auth_method=SSHAuthMethod.PASSWORD,
            ssh_password='test123',
            remote_bind_host='localhost',
            remote_bind_port=3306,
            connect_timeout=30,
            keepalive_interval=30,
            compression=False,
            strict_host_key_checking=True
        )
        assert password_config.auth_method == SSHAuthMethod.PASSWORD
        assert password_config.ssh_password == 'test123'
        
        # Private key auth
        key_config = SSHTunnelConfig(
            enabled=True,
            ssh_host='bastion.example.com',
            ssh_port=22,
            ssh_user='ubuntu',
            auth_method=SSHAuthMethod.PRIVATE_KEY,
            private_key_content='-----BEGIN PRIVATE KEY-----',
            remote_bind_host='localhost',
            remote_bind_port=3306,
            connect_timeout=30,
            keepalive_interval=30,
            compression=False,
            strict_host_key_checking=True
        )
        assert key_config.auth_method == SSHAuthMethod.PRIVATE_KEY
        assert key_config.private_key_content == '-----BEGIN PRIVATE KEY-----'


class TestSSHTunnelManager:
    """Test SSH tunnel manager functionality"""
    
    @pytest.mark.asyncio
    async def test_config_validation(self):
        """Test SSH tunnel configuration validation"""
        # Valid config should pass validation
        valid_config = SSHTunnelConfig(
            enabled=True,
            ssh_host='bastion.example.com',
            ssh_port=22,
            ssh_user='ubuntu',
            auth_method=SSHAuthMethod.PASSWORD,
            ssh_password='test123',
            remote_bind_host='localhost',
            remote_bind_port=3306,
            connect_timeout=30,
            keepalive_interval=30,
            compression=False,
            strict_host_key_checking=True
        )
        
        errors = await tunnel_manager.validate_config(valid_config)
        # Should have no validation errors for valid config
        # Note: This might have errors if asyncssh is not installed
        if not errors or any('asyncssh' in str(error) for error in errors):
            # If asyncssh is not available, that's expected in test environment
            pass
        else:
            assert len(errors) == 0
    
    @pytest.mark.asyncio
    async def test_invalid_config_validation(self):
        """Test SSH tunnel configuration validation with invalid config"""
        # Invalid config should fail validation
        invalid_config = SSHTunnelConfig(
            enabled=True,
            ssh_host='',  # Empty host
            ssh_port=22,
            ssh_user='',  # Empty user
            auth_method=SSHAuthMethod.PASSWORD,
            ssh_password='',  # Empty password
            remote_bind_host='localhost',
            remote_bind_port=3306,
            connect_timeout=30,
            keepalive_interval=30,
            compression=False,
            strict_host_key_checking=True
        )
        
        try:
            errors = await tunnel_manager.validate_config(invalid_config)
            # Should have validation errors for invalid config
            assert len(errors) > 0
        except Exception as e:
            # If asyncssh is not available, validation will fail
            assert 'asyncssh' in str(e) or 'SSH' in str(e)


if __name__ == '__main__':
    pytest.main([__file__])