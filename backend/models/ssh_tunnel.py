"""
SSH Tunnel models and configurations
Supports SSH tunneling through jump servers/bastion hosts for secure database connections
"""

from pydantic import BaseModel, Field, validator
from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum
from pathlib import Path
import re
import logging

logger = logging.getLogger(__name__)


class SSHAuthMethod(str, Enum):
    """SSH authentication methods"""
    PASSWORD = "password"
    PRIVATE_KEY = "private_key"
    SSH_AGENT = "ssh_agent"


class TunnelStatus(str, Enum):
    """SSH tunnel connection status"""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting" 
    CONNECTED = "connected"
    FAILED = "failed"
    TIMEOUT = "timeout"


class SSHKeyType(str, Enum):
    """SSH private key types"""
    RSA = "rsa"
    ED25519 = "ed25519"
    ECDSA = "ecdsa"
    DSA = "dsa"


class SSHTunnelConfig(BaseModel):
    """SSH tunnel configuration"""
    enabled: bool = False
    
    # SSH Connection Details
    ssh_host: str = Field(..., description="SSH server hostname or IP")
    ssh_port: int = Field(default=22, ge=1, le=65535)
    ssh_user: str = Field(..., description="SSH username")
    
    # Authentication
    auth_method: SSHAuthMethod = SSHAuthMethod.PRIVATE_KEY
    
    # Password authentication
    ssh_password: Optional[str] = Field(default=None, description="SSH password (will be encrypted)")
    
    # Private key authentication
    private_key_path: Optional[str] = Field(default=None, description="Path to SSH private key")
    private_key_content: Optional[str] = Field(default=None, description="Private key content (will be encrypted)")
    private_key_passphrase: Optional[str] = Field(default=None, description="Private key passphrase (will be encrypted)")
    key_type: Optional[SSHKeyType] = Field(default=None, description="SSH key type")
    
    # Tunnel Configuration
    local_bind_port: Optional[int] = Field(default=None, ge=1024, le=65535, description="Local tunnel port (auto-assigned if None)")
    remote_bind_host: str = Field(default="127.0.0.1", description="Remote host to bind to")
    remote_bind_port: int = Field(default=3306, ge=1, le=65535, description="Remote port to bind to")
    
    # Connection Options
    connect_timeout: int = Field(default=10, ge=1, le=60, description="SSH connection timeout (seconds)")
    keepalive_interval: int = Field(default=30, ge=10, le=300, description="SSH keepalive interval (seconds)")
    compression: bool = Field(default=True, description="Enable SSH compression")
    
    # Security Options
    strict_host_key_checking: bool = Field(default=False, description="Verify SSH host key")
    known_hosts_path: Optional[str] = Field(default=None, description="Path to known_hosts file")
    
    @validator('ssh_host')
    def validate_ssh_host(cls, v):
        """Validate SSH hostname or IP"""
        if not v or not v.strip():
            raise ValueError("SSH host cannot be empty")
        
        # Basic hostname/IP validation
        if not re.match(r'^[a-zA-Z0-9.-]+$', v.strip()):
            raise ValueError("Invalid SSH host format")
        
        return v.strip()
    
    @validator('ssh_user')
    def validate_ssh_user(cls, v):
        """Validate SSH username"""
        if not v or not v.strip():
            raise ValueError("SSH username cannot be empty")
        
        # Basic username validation
        if not re.match(r'^[a-zA-Z0-9._-]+$', v.strip()):
            raise ValueError("Invalid SSH username format")
        
        return v.strip()
    
    @validator('private_key_passphrase', always=True)
    def validate_key_path_requirements(cls, v, values):
        """Validate private key path exists if specified and no content provided - runs after private_key_content"""
        key_path = values.get('private_key_path')
        logger.debug(f"Validating private_key_path={key_path}, values keys: {list(values.keys())}")
        
        if key_path and key_path.strip():  # Only validate non-empty paths
            # If we have private key content, don't validate the path
            has_key_content = values.get('private_key_content')
            if has_key_content and isinstance(has_key_content, str) and has_key_content.strip():
                logger.debug(f"Private key content provided ({len(has_key_content)} chars), skipping path validation")
                return v
            
            # Only validate path if no content is provided and auth method is private key
            auth_method = values.get('auth_method')
            if auth_method == SSHAuthMethod.PRIVATE_KEY:
                logger.debug(f"Validating private key path: {key_path}")
                key_path_obj = Path(key_path)
                if not key_path_obj.exists():
                    raise ValueError(f"Private key file not found: {key_path}")
                if not key_path_obj.is_file():
                    raise ValueError(f"Private key path is not a file: {key_path}")
            else:
                logger.debug(f"Auth method is not private_key ({auth_method}), skipping path validation")
        else:
            logger.debug("Empty or None private_key_path, skipping validation")
            
        return v
    
    @validator('key_type', always=True)
    def validate_auth_requirements(cls, v, values):
        """Ensure required fields are present for chosen auth method - runs after all key fields are processed"""
        auth_method = values.get('auth_method')
        logger.debug(f"Validating auth requirements for method={auth_method}, values keys: {list(values.keys())}")
        
        if auth_method == SSHAuthMethod.PASSWORD:
            password = values.get('ssh_password')
            if not password or (isinstance(password, str) and not password.strip()):
                raise ValueError("SSH password is required for password authentication")
        
        elif auth_method == SSHAuthMethod.PRIVATE_KEY:
            key_path = values.get('private_key_path')
            key_content = values.get('private_key_content')
            
            logger.debug(f"Private key validation - path: {bool(key_path)}, content: {bool(key_content)}")
            if key_content:
                logger.debug(f"Private key content length: {len(key_content) if isinstance(key_content, str) else 0}")
            
            # Check if key_path is valid (not empty string)
            has_valid_key_path = key_path and isinstance(key_path, str) and key_path.strip()
            # Check if key_content is valid (not empty string)  
            has_valid_key_content = key_content and isinstance(key_content, str) and key_content.strip()
            
            logger.debug(f"Has valid path: {has_valid_key_path}, Has valid content: {has_valid_key_content}")
            print(f"DEBUG: key_path='{key_path}', key_content length={len(key_content) if key_content else 0}")
            print(f"DEBUG: has_valid_key_path={has_valid_key_path}, has_valid_key_content={has_valid_key_content}")
            
            if not has_valid_key_path and not has_valid_key_content:
                print(f"DEBUG: Validation failed - no valid key found")
                raise ValueError("Private key (path or content) is required for key authentication")
        
        # SSH_AGENT doesn't require additional validation
        # Return the original key_type value
        return v
    
    def get_masked_config(self) -> Dict[str, Any]:
        """Get configuration with sensitive data masked for logging"""
        config = self.dict()
        
        # Mask sensitive fields
        if config.get('ssh_password'):
            config['ssh_password'] = '***masked***'
        if config.get('private_key_content'):
            config['private_key_content'] = '***masked***'
        if config.get('private_key_passphrase'):
            config['private_key_passphrase'] = '***masked***'
        
        return config


class SSHConnectionInfo(BaseModel):
    """Active SSH connection information"""
    tunnel_id: str = Field(..., description="Unique tunnel identifier")
    config: SSHTunnelConfig
    status: TunnelStatus = TunnelStatus.DISCONNECTED
    
    # Connection details
    local_port: Optional[int] = None
    connected_at: Optional[datetime] = None
    last_activity: Optional[datetime] = None
    
    # Statistics
    bytes_sent: int = 0
    bytes_received: int = 0
    connections_count: int = 0
    
    # Error information
    last_error: Optional[str] = None
    error_count: int = 0
    reconnect_attempts: int = 0
    
    # Performance metrics
    connection_latency_ms: Optional[float] = None
    tunnel_latency_ms: Optional[float] = None
    
    def get_connection_string(self) -> str:
        """Get connection description for display"""
        return f"{self.config.ssh_user}@{self.config.ssh_host}:{self.config.ssh_port}"
    
    def is_healthy(self) -> bool:
        """Check if tunnel is in healthy state"""
        return (
            self.status == TunnelStatus.CONNECTED and
            self.local_port is not None and
            self.error_count == 0
        )


class SSHTunnelTest(BaseModel):
    """SSH tunnel test configuration"""
    config: SSHTunnelConfig
    test_database_connection: bool = True
    timeout_seconds: int = Field(default=30, ge=5, le=120)
    
    @validator('timeout_seconds')
    def validate_timeout(cls, v):
        """Ensure reasonable timeout values"""
        if v < 5:
            return 5
        if v > 120:
            return 120
        return v


class SSHTunnelTestResult(BaseModel):
    """SSH tunnel test result"""
    success: bool
    tunnel_status: TunnelStatus
    local_port: Optional[int] = None
    
    # Test results
    ssh_connection_success: bool = False
    ssh_connection_time_ms: Optional[float] = None
    
    database_connection_success: bool = False
    database_connection_time_ms: Optional[float] = None
    
    # Error information
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    
    # Performance metrics
    total_test_time_ms: float
    tunnel_latency_ms: Optional[float] = None
    
    # Connection details
    ssh_server_info: Optional[Dict[str, Any]] = None
    database_server_info: Optional[Dict[str, Any]] = None
    
    def add_error(self, error: str):
        """Add error message"""
        self.errors.append(error)
        self.success = False
    
    def add_warning(self, warning: str):
        """Add warning message"""
        self.warnings.append(warning)


class SSHKeyInfo(BaseModel):
    """SSH key information and validation"""
    key_path: Optional[str] = None
    key_content: Optional[str] = None
    key_type: Optional[SSHKeyType] = None
    
    # Key validation
    is_valid: bool = False
    is_encrypted: bool = False
    fingerprint: Optional[str] = None
    key_size: Optional[int] = None
    
    # Key metadata
    comment: Optional[str] = None
    created_at: Optional[datetime] = None
    
    # Validation errors
    validation_errors: List[str] = Field(default_factory=list)
    
    def add_validation_error(self, error: str):
        """Add validation error"""
        self.validation_errors.append(error)
        self.is_valid = False


class DatabaseConfigWithSSH(BaseModel):
    """Enhanced database configuration with SSH tunnel support"""
    # Original database config
    host: str
    port: int = 3306
    user: str
    password: str
    database: Optional[str] = None
    
    # SSH tunnel config
    ssh_tunnel: Optional[SSHTunnelConfig] = None
    
    def get_effective_connection_params(self) -> Dict[str, Any]:
        """Get actual connection parameters (with tunnel if enabled)"""
        if self.ssh_tunnel and self.ssh_tunnel.enabled:
            # Use tunnel connection - CRITICAL FIX for Docker environment
            import os
            # In Docker environment, use ssh-proxy hostname, otherwise localhost
            host = "schema-diff-ssh-proxy" if os.getenv('DOCKER_ENV') == 'true' else "127.0.0.1"
            return {
                "host": host,
                "port": self.ssh_tunnel.local_bind_port or 3306,
                "user": self.user,
                "password": self.password,
                "database": self.database
            }
        else:
            # Direct connection
            return {
                "host": self.host,
                "port": self.port,
                "user": self.user,
                "password": self.password,
                "database": self.database
            }
    
    def get_connection_url(self, use_tunnel: bool = None, database: Optional[str] = None) -> str:
        """Generate connection URL (with tunnel if enabled)"""
        if use_tunnel is None:
            use_tunnel = self.ssh_tunnel and self.ssh_tunnel.enabled
            
        if use_tunnel and self.ssh_tunnel:
            # Use tunnel connection - CRITICAL FIX for Docker environment
            import os
            # In Docker environment, use ssh-proxy hostname, otherwise localhost
            host = "schema-diff-ssh-proxy" if os.getenv('DOCKER_ENV') == 'true' else "127.0.0.1"
            port = self.ssh_tunnel.local_bind_port or 3306
        else:
            # Direct connection
            host = self.host
            port = self.port
            
        # Use provided database parameter if given, otherwise use instance database
        db = database if database is not None else (self.database or "")
        return f"mysql+pymysql://{self.user}:{self.password}@{host}:{port}/{db}"
    
    def get_display_config(self) -> Dict[str, Any]:
        """Get configuration for display (with sensitive data masked)"""
        config = {
            "host": self.host,
            "port": self.port,
            "user": self.user,
            "password": "***masked***",
            "database": self.database,
            "ssh_tunnel_enabled": self.ssh_tunnel.enabled if self.ssh_tunnel else False
        }
        
        if self.ssh_tunnel and self.ssh_tunnel.enabled:
            config["ssh_config"] = self.ssh_tunnel.get_masked_config()
        
        return config


# Re-export commonly used enums for convenience
__all__ = [
    "SSHAuthMethod",
    "TunnelStatus", 
    "SSHKeyType",
    "SSHTunnelConfig",
    "SSHConnectionInfo",
    "SSHTunnelTest",
    "SSHTunnelTestResult",
    "SSHKeyInfo",
    "DatabaseConfigWithSSH"
]