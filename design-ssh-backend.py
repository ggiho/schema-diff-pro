# backend/api/routers/ssh.py
from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any, Optional, List
import asyncio
import logging
from datetime import datetime, timedelta

from models.ssh_tunnel import (
    SSHTunnelConfig, 
    SSHTunnelTest, 
    SSHTunnelTestResult, 
    SSHConnectionInfo,
    TunnelStatus,
    SSHKeyInfo,
    DatabaseConfigWithSSH
)
from services.ssh_tunnel_manager import SSHTunnelManager
from core.security import SecurityManager

logger = logging.getLogger(__name__)
router = APIRouter()

# Global tunnel manager instance
tunnel_manager = SSHTunnelManager()
security_manager = SecurityManager()


@router.post("/test")
async def test_ssh_tunnel(test_config: SSHTunnelTest) -> SSHTunnelTestResult:
    """Test SSH tunnel connection and optionally database connection"""
    start_time = datetime.now()
    result = SSHTunnelTestResult(
        success=False,
        tunnel_status=TunnelStatus.DISCONNECTED,
        total_test_time_ms=0
    )
    
    try:
        # Validate SSH configuration
        validation_errors = await tunnel_manager.validate_config(test_config.config)
        if validation_errors:
            result.errors = validation_errors
            result.total_test_time_ms = (datetime.now() - start_time).total_seconds() * 1000
            return result
        
        # Test SSH connection
        ssh_start = datetime.now()
        tunnel_info = await tunnel_manager.create_tunnel(
            config=test_config.config,
            test_mode=True,
            timeout=test_config.timeout_seconds
        )
        ssh_end = datetime.now()
        
        if tunnel_info.status == TunnelStatus.CONNECTED:
            result.ssh_connection_success = True
            result.ssh_connection_time_ms = (ssh_end - ssh_start).total_seconds() * 1000
            result.tunnel_status = TunnelStatus.CONNECTED
            result.local_port = tunnel_info.local_port
            
            # Test database connection if requested
            if test_config.test_database_connection:
                db_start = datetime.now()
                db_success = await tunnel_manager.test_database_through_tunnel(
                    tunnel_info.tunnel_id
                )
                db_end = datetime.now()
                
                result.database_connection_success = db_success
                result.database_connection_time_ms = (db_end - db_start).total_seconds() * 1000
                
                if not db_success:
                    result.warnings.append("SSH tunnel connected but database connection failed")
            
            # Cleanup test tunnel
            await tunnel_manager.close_tunnel(tunnel_info.tunnel_id)
            
            result.success = result.ssh_connection_success and (
                not test_config.test_database_connection or result.database_connection_success
            )
            
        else:
            result.errors.append(f"SSH connection failed: {tunnel_info.last_error}")
            result.tunnel_status = tunnel_info.status
    
    except Exception as e:
        logger.error(f"SSH tunnel test failed: {str(e)}")
        result.errors.append(f"Test failed: {str(e)}")
        result.tunnel_status = TunnelStatus.FAILED
    
    result.total_test_time_ms = (datetime.now() - start_time).total_seconds() * 1000
    return result


@router.post("/tunnel/create")
async def create_ssh_tunnel(config: SSHTunnelConfig) -> SSHConnectionInfo:
    """Create and establish SSH tunnel"""
    try:
        # Validate configuration
        validation_errors = await tunnel_manager.validate_config(config)
        if validation_errors:
            raise HTTPException(
                status_code=400, 
                detail=f"Configuration validation failed: {', '.join(validation_errors)}"
            )
        
        # Create tunnel
        tunnel_info = await tunnel_manager.create_tunnel(config)
        
        if tunnel_info.status != TunnelStatus.CONNECTED:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to establish SSH tunnel: {tunnel_info.last_error}"
            )
        
        return tunnel_info
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create SSH tunnel: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tunnel/{tunnel_id}/status")
async def get_tunnel_status(tunnel_id: str) -> SSHConnectionInfo:
    """Get SSH tunnel status and information"""
    tunnel_info = await tunnel_manager.get_tunnel_info(tunnel_id)
    if not tunnel_info:
        raise HTTPException(status_code=404, detail="SSH tunnel not found")
    return tunnel_info


@router.delete("/tunnel/{tunnel_id}")
async def close_ssh_tunnel(tunnel_id: str) -> Dict[str, str]:
    """Close SSH tunnel"""
    try:
        success = await tunnel_manager.close_tunnel(tunnel_id)
        if success:
            return {"status": "closed", "tunnel_id": tunnel_id}
        else:
            raise HTTPException(status_code=404, detail="SSH tunnel not found")
    except Exception as e:
        logger.error(f"Failed to close SSH tunnel {tunnel_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tunnels")
async def list_active_tunnels() -> List[SSHConnectionInfo]:
    """List all active SSH tunnels"""
    return await tunnel_manager.list_active_tunnels()


@router.post("/key/validate")
async def validate_ssh_key(key_data: Dict[str, Any]) -> SSHKeyInfo:
    """Validate SSH private key"""
    try:
        key_info = await security_manager.validate_ssh_key(
            key_path=key_data.get('key_path'),
            key_content=key_data.get('key_content'),
            passphrase=key_data.get('passphrase')
        )
        return key_info
    except Exception as e:
        logger.error(f"SSH key validation failed: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/database/test-with-tunnel")
async def test_database_with_tunnel(config: DatabaseConfigWithSSH) -> Dict[str, Any]:
    """Test database connection with SSH tunnel"""
    if not config.ssh_tunnel or not config.ssh_tunnel.enabled:
        raise HTTPException(status_code=400, detail="SSH tunnel not enabled")
    
    tunnel_info = None
    try:
        # Create SSH tunnel
        tunnel_info = await tunnel_manager.create_tunnel(config.ssh_tunnel)
        
        if tunnel_info.status != TunnelStatus.CONNECTED:
            raise HTTPException(
                status_code=500,
                detail=f"SSH tunnel connection failed: {tunnel_info.last_error}"
            )
        
        # Test database connection through tunnel
        from services.database_service import DatabaseService
        db_service = DatabaseService()
        
        # Use tunnel connection parameters
        tunnel_config = config.get_effective_connection_params()
        test_result = await db_service.test_connection(tunnel_config)
        
        return {
            "success": True,
            "tunnel_info": {
                "tunnel_id": tunnel_info.tunnel_id,
                "local_port": tunnel_info.local_port,
                "status": tunnel_info.status
            },
            "database_info": test_result
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Database test with SSH tunnel failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    
    finally:
        # Cleanup tunnel if created
        if tunnel_info and tunnel_info.tunnel_id:
            await tunnel_manager.close_tunnel(tunnel_info.tunnel_id)


# ================================
# backend/services/ssh_tunnel_manager.py
import asyncio
import asyncssh
import socket
import uuid
import time
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from contextlib import asynccontextmanager
import logging

from models.ssh_tunnel import (
    SSHTunnelConfig, 
    SSHConnectionInfo, 
    TunnelStatus,
    SSHAuthMethod
)
from core.security import SecurityManager

logger = logging.getLogger(__name__)


class SSHTunnelManager:
    """Manages SSH tunnel connections"""
    
    def __init__(self):
        self.active_tunnels: Dict[str, SSHConnectionInfo] = {}
        self.ssh_connections: Dict[str, Any] = {}  # SSH connection objects
        self.security_manager = SecurityManager()
        self._cleanup_task = None
        self._start_cleanup_task()
    
    def _start_cleanup_task(self):
        """Start background task for tunnel cleanup"""
        if self._cleanup_task is None:
            self._cleanup_task = asyncio.create_task(self._periodic_cleanup())
    
    async def _periodic_cleanup(self):
        """Periodically check and cleanup stale tunnels"""
        while True:
            try:
                await asyncio.sleep(60)  # Check every minute
                await self._cleanup_stale_tunnels()
            except Exception as e:
                logger.error(f"Tunnel cleanup task error: {e}")
    
    async def _cleanup_stale_tunnels(self):
        """Remove stale or failed tunnels"""
        stale_tunnels = []
        cutoff_time = datetime.now() - timedelta(minutes=30)
        
        for tunnel_id, tunnel_info in self.active_tunnels.items():
            if (tunnel_info.status == TunnelStatus.FAILED or 
                (tunnel_info.last_activity and tunnel_info.last_activity < cutoff_time)):
                stale_tunnels.append(tunnel_id)
        
        for tunnel_id in stale_tunnels:
            await self.close_tunnel(tunnel_id)
    
    def _find_free_port(self, start_port: int = 10000) -> int:
        """Find available local port for tunnel"""
        for port in range(start_port, start_port + 1000):
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.bind(('127.0.0.1', port))
                    return port
            except OSError:
                continue
        raise RuntimeError("No available ports for SSH tunnel")
    
    async def validate_config(self, config: SSHTunnelConfig) -> List[str]:
        """Validate SSH tunnel configuration"""
        errors = []
        
        if not config.ssh_host:
            errors.append("SSH host is required")
        
        if not config.ssh_user:
            errors.append("SSH username is required")
        
        if config.auth_method == SSHAuthMethod.PASSWORD and not config.ssh_password:
            errors.append("SSH password is required for password authentication")
        
        if (config.auth_method == SSHAuthMethod.PRIVATE_KEY and 
            not config.private_key_path and not config.private_key_content):
            errors.append("Private key is required for key authentication")
        
        # Validate ports
        if not (1 <= config.ssh_port <= 65535):
            errors.append("SSH port must be between 1 and 65535")
        
        if not (1 <= config.remote_bind_port <= 65535):
            errors.append("Remote port must be between 1 and 65535")
        
        if config.local_bind_port and not (1024 <= config.local_bind_port <= 65535):
            errors.append("Local port must be between 1024 and 65535")
        
        return errors
    
    async def create_tunnel(
        self, 
        config: SSHTunnelConfig, 
        test_mode: bool = False,
        timeout: int = 30
    ) -> SSHConnectionInfo:
        """Create SSH tunnel"""
        tunnel_id = str(uuid.uuid4())
        start_time = datetime.now()
        
        # Initialize tunnel info
        tunnel_info = SSHConnectionInfo(
            tunnel_id=tunnel_id,
            config=config,
            status=TunnelStatus.CONNECTING
        )
        
        if not test_mode:
            self.active_tunnels[tunnel_id] = tunnel_info
        
        try:
            # Find local port
            local_port = config.local_bind_port or self._find_free_port()
            tunnel_info.local_port = local_port
            
            # Prepare authentication
            auth_options = await self._prepare_auth_options(config)
            
            # Establish SSH connection
            ssh_conn = await asyncio.wait_for(
                asyncssh.connect(
                    host=config.ssh_host,
                    port=config.ssh_port,
                    username=config.ssh_user,
                    connect_timeout=config.connect_timeout,
                    keepalive_interval=config.keepalive_interval,
                    compression_algs=['zlib@openssh.com'] if config.compression else None,
                    **auth_options
                ),
                timeout=timeout
            )
            
            # Create port forwarding
            listener = await ssh_conn.forward_local_port(
                listen_host='127.0.0.1',
                listen_port=local_port,
                dest_host=config.remote_bind_host,
                dest_port=config.remote_bind_port
            )
            
            # Update tunnel status
            tunnel_info.status = TunnelStatus.CONNECTED
            tunnel_info.connected_at = datetime.now()
            tunnel_info.last_activity = datetime.now()
            tunnel_info.connection_latency_ms = (
                datetime.now() - start_time
            ).total_seconds() * 1000
            
            # Store SSH connection for management
            if not test_mode:
                self.ssh_connections[tunnel_id] = {
                    'connection': ssh_conn,
                    'listener': listener
                }
            
            logger.info(f"SSH tunnel established: {tunnel_id} -> {config.ssh_host}:{config.ssh_port}")
            
        except asyncio.TimeoutError:
            tunnel_info.status = TunnelStatus.TIMEOUT
            tunnel_info.last_error = "Connection timeout"
            if not test_mode and tunnel_id in self.active_tunnels:
                del self.active_tunnels[tunnel_id]
        except Exception as e:
            tunnel_info.status = TunnelStatus.FAILED
            tunnel_info.last_error = str(e)
            tunnel_info.error_count += 1
            if not test_mode and tunnel_id in self.active_tunnels:
                del self.active_tunnels[tunnel_id]
            logger.error(f"SSH tunnel creation failed: {e}")
        
        return tunnel_info
    
    async def _prepare_auth_options(self, config: SSHTunnelConfig) -> Dict[str, Any]:
        """Prepare SSH authentication options"""
        auth_options = {}
        
        if config.auth_method == SSHAuthMethod.PASSWORD:
            auth_options['password'] = await self.security_manager.decrypt_value(config.ssh_password)
        
        elif config.auth_method == SSHAuthMethod.PRIVATE_KEY:
            if config.private_key_content:
                # Use key content directly
                private_key = await self.security_manager.decrypt_value(config.private_key_content)
                passphrase = None
                if config.private_key_passphrase:
                    passphrase = await self.security_manager.decrypt_value(config.private_key_passphrase)
                
                auth_options['client_keys'] = [(private_key, passphrase)]
            
            elif config.private_key_path:
                # Use key file path
                passphrase = None
                if config.private_key_passphrase:
                    passphrase = await self.security_manager.decrypt_value(config.private_key_passphrase)
                
                auth_options['client_keys'] = [(config.private_key_path, passphrase)]
        
        elif config.auth_method == SSHAuthMethod.SSH_AGENT:
            auth_options['agent_path'] = True
        
        # Host key verification
        if not config.strict_host_key_checking:
            auth_options['known_hosts'] = None
        elif config.known_hosts_path:
            auth_options['known_hosts'] = config.known_hosts_path
        
        return auth_options
    
    async def close_tunnel(self, tunnel_id: str) -> bool:
        """Close SSH tunnel"""
        try:
            if tunnel_id in self.ssh_connections:
                ssh_data = self.ssh_connections[tunnel_id]
                
                # Close listener
                if 'listener' in ssh_data:
                    ssh_data['listener'].close()
                
                # Close SSH connection
                if 'connection' in ssh_data:
                    ssh_data['connection'].close()
                
                del self.ssh_connections[tunnel_id]
            
            if tunnel_id in self.active_tunnels:
                del self.active_tunnels[tunnel_id]
            
            logger.info(f"SSH tunnel closed: {tunnel_id}")
            return True
        
        except Exception as e:
            logger.error(f"Failed to close SSH tunnel {tunnel_id}: {e}")
            return False
    
    async def get_tunnel_info(self, tunnel_id: str) -> Optional[SSHConnectionInfo]:
        """Get tunnel information"""
        tunnel_info = self.active_tunnels.get(tunnel_id)
        if tunnel_info:
            # Update activity timestamp
            tunnel_info.last_activity = datetime.now()
        return tunnel_info
    
    async def list_active_tunnels(self) -> List[SSHConnectionInfo]:
        """List all active tunnels"""
        return list(self.active_tunnels.values())
    
    async def test_database_through_tunnel(self, tunnel_id: str) -> bool:
        """Test database connection through existing tunnel"""
        try:
            tunnel_info = self.active_tunnels.get(tunnel_id)
            if not tunnel_info or tunnel_info.status != TunnelStatus.CONNECTED:
                return False
            
            # Simple connection test to tunnel port
            import aiomysql
            
            connection = await aiomysql.connect(
                host='127.0.0.1',
                port=tunnel_info.local_port,
                user='root',  # This would come from actual DB config
                password='',
                connect_timeout=5
            )
            
            connection.close()
            return True
        
        except Exception as e:
            logger.error(f"Database test through tunnel failed: {e}")
            return False


# ================================
# backend/core/security.py
import base64
import hashlib
import os
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, ed25519, ec, dsa
from typing import Optional, Dict, Any
import logging

from models.ssh_tunnel import SSHKeyInfo, SSHKeyType

logger = logging.getLogger(__name__)


class SecurityManager:
    """Handles encryption, decryption and security operations"""
    
    def __init__(self):
        self.encryption_key = self._get_or_create_encryption_key()
    
    def _get_or_create_encryption_key(self) -> bytes:
        """Get or create encryption key for sensitive data"""
        key_path = os.path.join(os.getcwd(), '.ssh_encryption_key')
        
        if os.path.exists(key_path):
            with open(key_path, 'rb') as f:
                return f.read()
        else:
            # Generate new key
            key = os.urandom(32)  # 256-bit key
            with open(key_path, 'wb') as f:
                f.write(key)
            os.chmod(key_path, 0o600)  # Read-only for owner
            return key
    
    async def encrypt_value(self, value: str) -> str:
        """Encrypt sensitive value"""
        if not value:
            return value
        
        # Generate random IV
        iv = os.urandom(16)
        cipher = Cipher(algorithms.AES(self.encryption_key), modes.CBC(iv), backend=default_backend())
        encryptor = cipher.encryptor()
        
        # Pad value to multiple of 16 bytes
        padding_length = 16 - (len(value.encode()) % 16)
        padded_value = value + chr(padding_length) * padding_length
        
        encrypted = encryptor.update(padded_value.encode()) + encryptor.finalize()
        
        # Combine IV and encrypted data
        result = iv + encrypted
        return base64.b64encode(result).decode()
    
    async def decrypt_value(self, encrypted_value: str) -> str:
        """Decrypt sensitive value"""
        if not encrypted_value:
            return encrypted_value
        
        try:
            data = base64.b64decode(encrypted_value.encode())
            iv = data[:16]
            encrypted = data[16:]
            
            cipher = Cipher(algorithms.AES(self.encryption_key), modes.CBC(iv), backend=default_backend())
            decryptor = cipher.decryptor()
            
            decrypted = decryptor.update(encrypted) + decryptor.finalize()
            
            # Remove padding
            padding_length = decrypted[-1]
            return decrypted[:-padding_length].decode()
        
        except Exception as e:
            logger.error(f"Failed to decrypt value: {e}")
            raise ValueError("Failed to decrypt sensitive data")
    
    async def validate_ssh_key(
        self, 
        key_path: Optional[str] = None,
        key_content: Optional[str] = None,
        passphrase: Optional[str] = None
    ) -> SSHKeyInfo:
        """Validate SSH private key"""
        key_info = SSHKeyInfo()
        
        try:
            if key_content:
                key_data = key_content.encode()
            elif key_path:
                with open(key_path, 'rb') as f:
                    key_data = f.read()
                key_info.key_path = key_path
            else:
                key_info.validation_errors.append("No key data provided")
                return key_info
            
            # Try to load the key
            try:
                if passphrase:
                    passphrase_bytes = passphrase.encode()
                else:
                    passphrase_bytes = None
                
                private_key = serialization.load_pem_private_key(
                    key_data, 
                    password=passphrase_bytes,
                    backend=default_backend()
                )
                
                key_info.is_valid = True
                key_info.is_encrypted = passphrase is not None
                
                # Determine key type and size
                if isinstance(private_key, rsa.RSAPrivateKey):
                    key_info.key_type = SSHKeyType.RSA
                    key_info.key_size = private_key.key_size
                elif isinstance(private_key, ed25519.Ed25519PrivateKey):
                    key_info.key_type = SSHKeyType.ED25519
                    key_info.key_size = 256
                elif isinstance(private_key, ec.EllipticCurvePrivateKey):
                    key_info.key_type = SSHKeyType.ECDSA
                    key_info.key_size = private_key.curve.key_size
                elif isinstance(private_key, dsa.DSAPrivateKey):
                    key_info.key_type = SSHKeyType.DSA
                    key_info.key_size = private_key.key_size
                
                # Generate fingerprint
                public_key = private_key.public_key()
                public_key_bytes = public_key.public_bytes(
                    encoding=serialization.Encoding.DER,
                    format=serialization.PublicFormat.SubjectPublicKeyInfo
                )
                
                fingerprint_hash = hashes.Hash(hashes.SHA256(), backend=default_backend())
                fingerprint_hash.update(public_key_bytes)
                fingerprint = base64.b64encode(fingerprint_hash.finalize()).decode()
                key_info.fingerprint = f"SHA256:{fingerprint}"
                
            except ValueError as e:
                if "Bad decrypt" in str(e) or "invalid" in str(e).lower():
                    key_info.validation_errors.append("Invalid passphrase or corrupted key")
                else:
                    key_info.validation_errors.append(f"Invalid key format: {str(e)}")
            
        except FileNotFoundError:
            key_info.validation_errors.append("Key file not found")
        except PermissionError:
            key_info.validation_errors.append("Permission denied accessing key file")
        except Exception as e:
            key_info.validation_errors.append(f"Key validation failed: {str(e)}")
        
        return key_info