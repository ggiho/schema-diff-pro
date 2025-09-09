# backend/models/ssh_tunnel.py
from pydantic import BaseModel, Field, validator
from typing import Optional, Dict, Any, Literal
from datetime import datetime
from enum import Enum
from pathlib import Path


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
    ssh_password: Optional[str] = Field(default=None, description="SSH password (encrypted)")
    
    # Private key authentication
    private_key_path: Optional[str] = Field(default=None, description="Path to SSH private key")
    private_key_content: Optional[str] = Field(default=None, description="Private key content (encrypted)")
    private_key_passphrase: Optional[str] = Field(default=None, description="Private key passphrase (encrypted)")
    key_type: Optional[SSHKeyType] = Field(default=None, description="SSH key type")
    
    # Tunnel Configuration
    local_bind_port: Optional[int] = Field(default=None, ge=1024, le=65535, description="Local tunnel port")
    remote_bind_host: str = Field(default="127.0.0.1", description="Remote host to bind to")
    remote_bind_port: int = Field(default=3306, ge=1, le=65535, description="Remote port to bind to")
    
    # Connection Options
    connect_timeout: int = Field(default=10, ge=1, le=60, description="SSH connection timeout (seconds)")
    keepalive_interval: int = Field(default=30, ge=10, le=300, description="SSH keepalive interval (seconds)")
    compression: bool = Field(default=True, description="Enable SSH compression")
    
    # Security Options
    strict_host_key_checking: bool = Field(default=True, description="Verify SSH host key")
    known_hosts_path: Optional[str] = Field(default=None, description="Path to known_hosts file")
    
    @validator('private_key_path')
    def validate_key_path(cls, v, values):
        """Validate private key path exists if specified"""
        if v and not Path(v).exists():
            raise ValueError(f"Private key file not found: {v}")
        return v
    
    @validator('auth_method')
    def validate_auth_method(cls, v, values):
        """Ensure required fields are present for chosen auth method"""
        if v == SSHAuthMethod.PASSWORD and not values.get('ssh_password'):
            raise ValueError("Password is required for password authentication")
        if v == SSHAuthMethod.PRIVATE_KEY and not (values.get('private_key_path') or values.get('private_key_content')):
            raise ValueError("Private key is required for key authentication")
        return v


class DatabaseConfigWithSSH(BaseModel):
    """Extended database configuration with SSH tunnel support"""
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
            # Use localhost with tunnel port
            return {
                "host": "127.0.0.1",
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


class SSHTunnelTest(BaseModel):
    """SSH tunnel test configuration"""
    config: SSHTunnelConfig
    test_database_connection: bool = True
    timeout_seconds: int = Field(default=30, ge=5, le=120)


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


# Extended existing DatabaseConfig to include SSH tunnel
class EnhancedDatabaseConfig(BaseModel):
    """Enhanced database configuration with SSH tunnel support"""
    host: str
    port: int = 3306
    user: str
    password: str
    database: Optional[str] = None
    
    # SSH Tunnel Configuration
    ssh_tunnel: Optional[SSHTunnelConfig] = None
    
    def get_connection_url(self, use_tunnel: bool = None) -> str:
        """Generate connection URL (with tunnel if enabled)"""
        if use_tunnel is None:
            use_tunnel = self.ssh_tunnel and self.ssh_tunnel.enabled
            
        if use_tunnel and self.ssh_tunnel:
            # Use tunnel connection
            host = "127.0.0.1"
            port = self.ssh_tunnel.local_bind_port or 3306
        else:
            # Direct connection
            host = self.host
            port = self.port
            
        db = self.database or ""
        return f"mysql+pymysql://{self.user}:{self.password}@{host}:{port}/{db}"