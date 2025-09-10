"""
SSH Tunnel Manager Service
Handles SSH tunnel creation, management, and monitoring
"""

import asyncio
import socket
import uuid
import time
import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from contextlib import asynccontextmanager
from pathlib import Path

try:
    import asyncssh
    ASYNCSSH_AVAILABLE = True
except ImportError:
    ASYNCSSH_AVAILABLE = False
    asyncssh = None

from models.ssh_tunnel import (
    SSHTunnelConfig, 
    SSHConnectionInfo, 
    TunnelStatus,
    SSHAuthMethod
)
from core.security import security_manager, DataClassification

logger = logging.getLogger(__name__)


class SSHTunnelManager:
    """Manages SSH tunnel connections and lifecycle"""
    
    def __init__(self):
        if not ASYNCSSH_AVAILABLE:
            logger.warning("asyncssh not available. SSH tunneling will be disabled.")
        
        self.active_tunnels: Dict[str, SSHConnectionInfo] = {}
        self.ssh_connections: Dict[str, Any] = {}  # SSH connection objects
        self.tunnel_listeners: Dict[str, Any] = {}  # Port forward listeners
        
        # Connection persistence and reuse tracking
        self.tunnel_pools: Dict[str, List[str]] = {}  # host:port -> list of tunnel_ids
        self.schema_discovery_tunnels: Dict[str, str] = {}  # connection_key -> tunnel_id
        self.tunnel_keep_alive_tasks: Dict[str, asyncio.Task] = {}  # tunnel_id -> keep_alive_task
        self.connection_warming_enabled = True
        
        self._cleanup_task = None
        self._start_background_tasks()
    
    def _start_background_tasks(self):
        """Start background maintenance tasks"""
        if self._cleanup_task is None and ASYNCSSH_AVAILABLE:
            self._cleanup_task = asyncio.create_task(self._periodic_maintenance())
    
    async def _periodic_maintenance(self):
        """Periodically maintain tunnels and cleanup stale connections"""
        while True:
            try:
                await asyncio.sleep(60)  # Check every minute
                await self._cleanup_stale_tunnels()
                await self._update_tunnel_stats()
                await self._maintain_tunnel_pools()
                await self._refresh_keep_alive_tasks()
            except Exception as e:
                logger.error(f"Tunnel maintenance task error: {e}")
    
    async def _cleanup_stale_tunnels(self):
        """Remove stale or failed tunnels with enhanced persistence logic"""
        stale_tunnels = []
        # Extended cutoff time for schema discovery tunnels (2 hours vs 30 minutes)
        regular_cutoff = datetime.now() - timedelta(minutes=30)
        schema_cutoff = datetime.now() - timedelta(hours=2)
        
        for tunnel_id, tunnel_info in self.active_tunnels.items():
            # Determine if this is a schema discovery tunnel
            is_schema_tunnel = any(tid == tunnel_id for tid in self.schema_discovery_tunnels.values())
            cutoff_time = schema_cutoff if is_schema_tunnel else regular_cutoff
            
            # Check for stale tunnels with different thresholds
            if (tunnel_info.status == TunnelStatus.FAILED or 
                (tunnel_info.last_activity and tunnel_info.last_activity < cutoff_time)):
                # Give schema discovery tunnels a chance to recover
                if is_schema_tunnel and tunnel_info.status != TunnelStatus.FAILED:
                    logger.info(f"Attempting to recover schema discovery tunnel: {tunnel_id}")
                    recovery_success = await self._attempt_tunnel_recovery(tunnel_id)
                    if recovery_success:
                        continue
                
                stale_tunnels.append(tunnel_id)
                continue
            
            # Enhanced health check for active tunnels
            if tunnel_info.status == TunnelStatus.CONNECTED:
                is_healthy = await self._health_check_tunnel(tunnel_id)
                if not is_healthy:
                    logger.warning(f"Tunnel {tunnel_id} failed health check")
                    # Attempt immediate recovery for schema discovery tunnels
                    if is_schema_tunnel:
                        logger.info(f"Attempting immediate recovery for schema discovery tunnel: {tunnel_id}")
                        recovery_success = await self._attempt_tunnel_recovery(tunnel_id)
                        if recovery_success:
                            continue
                    
                    tunnel_info.status = TunnelStatus.FAILED
                    tunnel_info.error_count += 1
                    tunnel_info.last_error = "Health check failed"
        
        # Cleanup stale tunnels
        for tunnel_id in stale_tunnels:
            logger.info(f"Cleaning up stale tunnel: {tunnel_id}")
            await self.close_tunnel(tunnel_id)
    
    async def _update_tunnel_stats(self):
        """Update tunnel statistics and activity"""
        for tunnel_id, tunnel_info in self.active_tunnels.items():
            if tunnel_info.status == TunnelStatus.CONNECTED:
                # Update last activity
                tunnel_info.last_activity = datetime.now()
                
                # Could add more detailed statistics here
                # like bytes transferred, connection count, etc.
    
    async def _health_check_tunnel(self, tunnel_id: str) -> bool:
        """Perform health check on SSH tunnel"""
        try:
            tunnel_info = self.active_tunnels.get(tunnel_id)
            if not tunnel_info or not tunnel_info.local_port:
                return False
            
            # Simple socket connectivity test
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            try:
                result = sock.connect_ex(('127.0.0.1', tunnel_info.local_port))
                return result == 0
            finally:
                sock.close()
        
        except Exception as e:
            logger.debug(f"Health check failed for tunnel {tunnel_id}: {e}")
            return False
    
    async def _maintain_tunnel_pools(self):
        """Maintain tunnel pools for connection reuse"""
        try:
            for pool_key, tunnel_ids in list(self.tunnel_pools.items()):
                # Remove closed tunnels from pools
                active_tunnel_ids = [tid for tid in tunnel_ids if tid in self.active_tunnels]
                
                if len(active_tunnel_ids) != len(tunnel_ids):
                    logger.debug(f"Cleaned pool {pool_key}: {len(tunnel_ids)} -> {len(active_tunnel_ids)} tunnels")
                    self.tunnel_pools[pool_key] = active_tunnel_ids
                
                # Remove empty pools
                if not active_tunnel_ids:
                    del self.tunnel_pools[pool_key]
                    logger.debug(f"Removed empty tunnel pool: {pool_key}")
        
        except Exception as e:
            logger.error(f"Tunnel pool maintenance error: {e}")
    
    async def _refresh_keep_alive_tasks(self):
        """Refresh keep-alive tasks for active tunnels"""
        try:
            # Remove completed or cancelled keep-alive tasks
            completed_tasks = []
            for tunnel_id, task in self.tunnel_keep_alive_tasks.items():
                if task.done() or task.cancelled():
                    completed_tasks.append(tunnel_id)
            
            for tunnel_id in completed_tasks:
                del self.tunnel_keep_alive_tasks[tunnel_id]
                logger.debug(f"Removed completed keep-alive task for tunnel: {tunnel_id}")
            
            # Start keep-alive tasks for schema discovery tunnels without them
            for tunnel_id in self.schema_discovery_tunnels.values():
                if (tunnel_id in self.active_tunnels and 
                    tunnel_id not in self.tunnel_keep_alive_tasks and
                    self.active_tunnels[tunnel_id].status == TunnelStatus.CONNECTED):
                    
                    task = asyncio.create_task(self._keep_tunnel_alive(tunnel_id))
                    self.tunnel_keep_alive_tasks[tunnel_id] = task
                    logger.debug(f"Started keep-alive task for schema discovery tunnel: {tunnel_id}")
        
        except Exception as e:
            logger.error(f"Keep-alive task refresh error: {e}")
    
    async def _keep_tunnel_alive(self, tunnel_id: str):
        """Keep tunnel alive with periodic health checks and activity"""
        try:
            while tunnel_id in self.active_tunnels:
                tunnel_info = self.active_tunnels[tunnel_id]
                
                if tunnel_info.status != TunnelStatus.CONNECTED:
                    break
                
                # Perform health check
                is_healthy = await self._health_check_tunnel(tunnel_id)
                if is_healthy:
                    tunnel_info.last_activity = datetime.now()
                    logger.debug(f"Keep-alive ping successful for tunnel: {tunnel_id}")
                else:
                    logger.warning(f"Keep-alive ping failed for tunnel: {tunnel_id}")
                    # Attempt recovery
                    recovery_success = await self._attempt_tunnel_recovery(tunnel_id)
                    if not recovery_success:
                        logger.error(f"Keep-alive recovery failed for tunnel: {tunnel_id}")
                        break
                
                # Wait before next keep-alive check (every 5 minutes)
                await asyncio.sleep(300)
        
        except asyncio.CancelledError:
            logger.debug(f"Keep-alive task cancelled for tunnel: {tunnel_id}")
        except Exception as e:
            logger.error(f"Keep-alive task error for tunnel {tunnel_id}: {e}")
    
    async def _attempt_tunnel_recovery(self, tunnel_id: str) -> bool:
        """Attempt to recover a failed tunnel"""
        try:
            tunnel_info = self.active_tunnels.get(tunnel_id)
            if not tunnel_info:
                return False
            
            logger.info(f"Attempting recovery for tunnel: {tunnel_id}")
            
            # Try a simple health check first
            if await self._health_check_tunnel(tunnel_id):
                tunnel_info.status = TunnelStatus.CONNECTED
                tunnel_info.last_activity = datetime.now()
                tunnel_info.last_error = None
                logger.info(f"Tunnel {tunnel_id} recovered via health check")
                return True
            
            # Attempt full reconnection
            return await self.reconnect_tunnel(tunnel_id)
        
        except Exception as e:
            logger.error(f"Tunnel recovery failed for {tunnel_id}: {e}")
            return False
    
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
        
        if not ASYNCSSH_AVAILABLE:
            errors.append("SSH tunneling is not available (asyncssh not installed)")
            return errors
        
        # Basic validation
        if not config.ssh_host.strip():
            errors.append("SSH host is required")
        
        if not config.ssh_user.strip():
            errors.append("SSH username is required")
        
        # Authentication validation
        if config.auth_method == SSHAuthMethod.PASSWORD:
            if not config.ssh_password:
                errors.append("SSH password is required for password authentication")
        
        elif config.auth_method == SSHAuthMethod.PRIVATE_KEY:
            if not config.private_key_path and not config.private_key_content:
                errors.append("Private key is required for key authentication")
            
            if config.private_key_path:
                key_path = Path(config.private_key_path)
                if not key_path.exists():
                    errors.append(f"Private key file not found: {config.private_key_path}")
        
        # Port validation
        if not (1 <= config.ssh_port <= 65535):
            errors.append("SSH port must be between 1 and 65535")
        
        if not (1 <= config.remote_bind_port <= 65535):
            errors.append("Remote port must be between 1 and 65535")
        
        if config.local_bind_port and not (1024 <= config.local_bind_port <= 65535):
            errors.append("Local port must be between 1024 and 65535")
        
        return errors
    
    async def _prepare_auth_options(self, config: SSHTunnelConfig) -> Dict[str, Any]:
        """Prepare SSH authentication options with comprehensive type validation"""
        auth_options = {}
        
        # Log config for debugging type issues
        logger.debug(f"Preparing auth options for config: "
                    f"auth_method={config.auth_method}, "
                    f"private_key_path={type(config.private_key_path)}={config.private_key_path}, "
                    f"private_key_content={type(config.private_key_content)}={'[MASKED]' if config.private_key_content else None}, "
                    f"known_hosts_path={type(config.known_hosts_path)}={config.known_hosts_path}, "
                    f"strict_host_key_checking={type(config.strict_host_key_checking)}={config.strict_host_key_checking}")
        
        if config.auth_method == SSHAuthMethod.PASSWORD:
            # Decrypt password
            password = await security_manager.decrypt_value(
                config.ssh_password, 
                DataClassification.CONFIDENTIAL
            )
            auth_options['password'] = password
        
        elif config.auth_method == SSHAuthMethod.PRIVATE_KEY:
            # Handle private key authentication
            if config.private_key_content:
                # Validate private_key_content type
                if not isinstance(config.private_key_content, str):
                    logger.error(f"Invalid private_key_content type: {type(config.private_key_content)}, expected str")
                    raise ValueError(f"Private key content must be a string, got {type(config.private_key_content)}")
                
                # Check if key content is already plain text (starts with -----)
                if config.private_key_content.startswith('-----BEGIN'):
                    # Plain text private key (for testing)
                    private_key = config.private_key_content
                    logger.debug("Using plain text private key for testing")
                else:
                    # Encrypted private key (for production)
                    private_key = await security_manager.decrypt_value(
                        config.private_key_content,
                        DataClassification.RESTRICTED
                    )
                    logger.debug("Decrypted private key content")
                
                passphrase = None
                if config.private_key_passphrase:
                    passphrase = await security_manager.decrypt_value(
                        config.private_key_passphrase,
                        DataClassification.RESTRICTED
                    )
                
                # Create temporary key file for asyncssh
                import tempfile
                with tempfile.NamedTemporaryFile(mode='w', suffix='.pem', delete=False) as temp_key:
                    temp_key.write(private_key)
                    temp_key_path = temp_key.name
                
                auth_options['client_keys'] = [(temp_key_path, passphrase)]
                auth_options['_temp_key_path'] = temp_key_path  # For cleanup
            
            elif config.private_key_path:
                # Validate and sanitize private_key_path
                if isinstance(config.private_key_path, bool):
                    logger.error(f"private_key_path is boolean ({config.private_key_path}), cannot use for authentication")
                    raise ValueError("Private key path cannot be a boolean value")
                elif not isinstance(config.private_key_path, str):
                    logger.error(f"Invalid private_key_path type: {type(config.private_key_path)}, expected str")
                    raise ValueError(f"Private key path must be a string, got {type(config.private_key_path)}")
                elif not config.private_key_path.strip():
                    logger.error(f"Empty private_key_path string")
                    raise ValueError("Private key path cannot be empty")
                
                # Use key file path
                passphrase = None
                if config.private_key_passphrase:
                    passphrase = await security_manager.decrypt_value(
                        config.private_key_passphrase,
                        DataClassification.RESTRICTED
                    )
                
                auth_options['client_keys'] = [(config.private_key_path.strip(), passphrase)]
            else:
                # No private key content or path provided
                logger.error("Private key authentication selected but no key content or path provided")
                raise ValueError("Private key (path or content) is required for key authentication")
        
        elif config.auth_method == SSHAuthMethod.SSH_AGENT:
            # For SSH agent, asyncssh uses the 'agent_path' parameter
            # Setting to None or omitting will use the default SSH agent
            # We don't need to set anything special for SSH agent
            logger.debug("Using SSH agent for authentication")
            # Explicitly ensure no agent_path boolean is set
            # This prevents any legacy boolean values from causing issues
            pass
        
        # Host key verification with strict type checking
        if not config.strict_host_key_checking:
            auth_options['known_hosts'] = None
            logger.debug("Disabled strict host key checking, setting known_hosts=None")
        elif config.known_hosts_path:
            # Validate and sanitize known_hosts_path
            if isinstance(config.known_hosts_path, bool):
                logger.warning(f"known_hosts_path is boolean ({config.known_hosts_path}), converting to None")
                auth_options['known_hosts'] = None
            elif not isinstance(config.known_hosts_path, str):
                logger.warning(f"Invalid known_hosts_path type: {type(config.known_hosts_path)}, converting to None")
                auth_options['known_hosts'] = None
            elif not config.known_hosts_path.strip():
                logger.debug("Empty known_hosts_path string, setting to None")
                auth_options['known_hosts'] = None
            else:
                auth_options['known_hosts'] = config.known_hosts_path.strip()
                logger.debug(f"Using known_hosts file: {config.known_hosts_path.strip()}")
        else:
            # known_hosts_path is None or empty, use default behavior
            logger.debug("No known_hosts_path specified, using asyncssh default")
        
        # Final validation - remove any boolean values to prevent PathLike errors
        cleaned_auth_options = {}
        for key, value in auth_options.items():
            if isinstance(value, bool):
                logger.warning(f"Removing boolean auth_option: {key}={value}")
                continue
            if value is None:
                logger.debug(f"Skipping None auth_option: {key}")
                continue
            if isinstance(value, str) and not value.strip():
                logger.debug(f"Skipping empty string auth_option: {key}")
                continue
            cleaned_auth_options[key] = value
        
        # Log final auth options (excluding sensitive data)
        safe_auth_options = {k: f"{type(v).__name__}={v}" if k not in ['password', '_temp_key_path'] else '[MASKED]' 
                            for k, v in cleaned_auth_options.items()}
        logger.debug(f"Final cleaned auth_options: {safe_auth_options}")
        
        return cleaned_auth_options
    
    async def get_or_create_tunnel_for_schema_discovery(
        self,
        config: SSHTunnelConfig,
        connection_key: str,
        timeout: int = 60
    ) -> SSHConnectionInfo:
        """Get existing tunnel or create new one optimized for schema discovery operations"""
        # Check if we already have a tunnel for this connection
        existing_tunnel_id = self.schema_discovery_tunnels.get(connection_key)
        if existing_tunnel_id and existing_tunnel_id in self.active_tunnels:
            tunnel_info = self.active_tunnels[existing_tunnel_id]
            
            # Verify tunnel is healthy
            if tunnel_info.status == TunnelStatus.CONNECTED:
                is_healthy = await self._health_check_tunnel(existing_tunnel_id)
                if is_healthy:
                    tunnel_info.last_activity = datetime.now()
                    tunnel_info.connections_count += 1
                    logger.info(f"Reusing existing tunnel for schema discovery: {existing_tunnel_id}")
                    return tunnel_info
                else:
                    logger.warning(f"Existing tunnel {existing_tunnel_id} is unhealthy, creating new one")
        
        # Create new tunnel with extended timeout for schema operations
        logger.info(f"Creating new tunnel for schema discovery: {connection_key}")
        tunnel_info = await self.create_tunnel(config, test_mode=False, timeout=timeout)
        
        # Register as schema discovery tunnel if successful
        if tunnel_info.status == TunnelStatus.CONNECTED:
            self.schema_discovery_tunnels[connection_key] = tunnel_info.tunnel_id
            
            # Start keep-alive task
            if self.connection_warming_enabled:
                keep_alive_task = asyncio.create_task(self._keep_tunnel_alive(tunnel_info.tunnel_id))
                self.tunnel_keep_alive_tasks[tunnel_info.tunnel_id] = keep_alive_task
                logger.info(f"Started keep-alive for schema discovery tunnel: {tunnel_info.tunnel_id}")
        
        return tunnel_info
    
    async def warm_connection_pool(self, configs: List[SSHTunnelConfig]) -> Dict[str, bool]:
        """Pre-warm connection pool for anticipated schema discovery operations"""
        results = {}
        
        for config in configs:
            connection_key = f"{config.ssh_host}:{config.ssh_port}:{config.remote_bind_host}:{config.remote_bind_port}"
            
            try:
                logger.info(f"Warming connection for: {connection_key}")
                tunnel_info = await self.get_or_create_tunnel_for_schema_discovery(
                    config, connection_key, timeout=60
                )
                results[connection_key] = tunnel_info.status == TunnelStatus.CONNECTED
                
                if results[connection_key]:
                    logger.info(f"Successfully warmed connection: {connection_key}")
                else:
                    logger.warning(f"Failed to warm connection: {connection_key}")
            
            except Exception as e:
                logger.error(f"Connection warming failed for {connection_key}: {e}")
                results[connection_key] = False
        
        return results

    async def create_tunnel(
        self, 
        config: SSHTunnelConfig, 
        test_mode: bool = False,
        timeout: int = 30
    ) -> SSHConnectionInfo:
        """Create and establish SSH tunnel"""
        if not ASYNCSSH_AVAILABLE:
            raise RuntimeError("SSH tunneling is not available (asyncssh not installed)")
        
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
        
        temp_key_path = None
        
        try:
            # Validate configuration
            validation_errors = await self.validate_config(config)
            if validation_errors:
                raise ValueError(f"Configuration validation failed: {', '.join(validation_errors)}")
            
            # Find local port
            local_port = config.local_bind_port or self._find_free_port()
            tunnel_info.local_port = local_port
            
            # Prepare authentication
            auth_options = await self._prepare_auth_options(config)
            temp_key_path = auth_options.pop('_temp_key_path', None)
            
            # Ensure temp_key_path is None or string, never boolean or other types
            if temp_key_path is not None:
                if not isinstance(temp_key_path, str):
                    logger.warning(f"Invalid temp_key_path type: {type(temp_key_path)} (value: {temp_key_path}), setting to None")
                    temp_key_path = None
                elif not temp_key_path.strip():  # Empty string check
                    logger.debug("Empty temp_key_path string, setting to None")
                    temp_key_path = None
            
            logger.info(f"Creating SSH tunnel {tunnel_id}: {config.ssh_user}@{config.ssh_host}:{config.ssh_port}")
            
            # Validate core SSH connection parameters to prevent boolean contamination
            if not isinstance(config.ssh_host, str) or not config.ssh_host.strip():
                logger.error(f"Invalid ssh_host: {type(config.ssh_host)}={config.ssh_host}")
                raise ValueError(f"SSH host must be a non-empty string, got {type(config.ssh_host)}")
            
            if not isinstance(config.ssh_user, str) or not config.ssh_user.strip():
                logger.error(f"Invalid ssh_user: {type(config.ssh_user)}={config.ssh_user}")
                raise ValueError(f"SSH user must be a non-empty string, got {type(config.ssh_user)}")
            
            if not isinstance(config.ssh_port, int) or not (1 <= config.ssh_port <= 65535):
                logger.error(f"Invalid ssh_port: {type(config.ssh_port)}={config.ssh_port}")
                raise ValueError(f"SSH port must be an integer between 1-65535, got {type(config.ssh_port)}")
            
            # Log all parameters being passed to asyncssh.connect (excluding sensitive data)
            connect_params = {
                "host": f"{type(config.ssh_host)}={config.ssh_host}",
                "port": f"{type(config.ssh_port)}={config.ssh_port}",
                "username": f"{type(config.ssh_user)}={config.ssh_user}",
                "connect_timeout": f"{type(config.connect_timeout)}={config.connect_timeout}",
                "keepalive_interval": f"{type(config.keepalive_interval)}={config.keepalive_interval}",
                "compression": f"{type(config.compression)}={config.compression}",
                "auth_options_keys": list(auth_options.keys()),
            }
            logger.debug(f"asyncssh.connect parameters: {connect_params}")
            
            # Check if running in Docker and use proxy if needed
            import os
            is_docker = os.getenv('DOCKER_ENV') == 'true'
            
            ssh_host = config.ssh_host.strip()
            ssh_options = {
                "port": config.ssh_port,
                "username": config.ssh_user.strip(),
                "connect_timeout": config.connect_timeout,
                "keepalive_interval": config.keepalive_interval,
                "compression_algs": ['zlib@openssh.com'] if config.compression else None,
                **auth_options
            }
            
            if is_docker:
                # In Docker, use host's SSH client to bypass container IP restrictions
                logger.info(f"Docker environment detected, using host SSH client for connection to {ssh_host}")
                # Create SSH tunnel using host's SSH binary via subprocess
                await self._create_host_ssh_tunnel(config, local_port, timeout)
                # Create a dummy connection object for compatibility
                ssh_conn = None  # Will be handled differently for host SSH
            else:
                # Direct connection when not in Docker
                ssh_conn = await asyncio.wait_for(
                    asyncssh.connect(ssh_host, **ssh_options),
                    timeout=timeout
                )
            
            # Create port forwarding
            if ssh_conn is not None:
                # Using asyncssh connection
                listener = await ssh_conn.forward_local_port(
                    listen_host='127.0.0.1',
                    listen_port=local_port,
                    dest_host=config.remote_bind_host,
                    dest_port=config.remote_bind_port
                )
            else:
                # Using host SSH (tunnel already created by _create_host_ssh_tunnel)
                listener = None
            
            # Update tunnel status
            tunnel_info.status = TunnelStatus.CONNECTED
            tunnel_info.connected_at = datetime.now()
            tunnel_info.last_activity = datetime.now()
            tunnel_info.connection_latency_ms = (
                datetime.now() - start_time
            ).total_seconds() * 1000
            
            # Store SSH connection for management
            if not test_mode:
                self.ssh_connections[tunnel_id] = ssh_conn
                self.tunnel_listeners[tunnel_id] = listener
                
                # Add to tunnel pool for reuse
                pool_key = f"{config.ssh_host}:{config.ssh_port}"
                if pool_key not in self.tunnel_pools:
                    self.tunnel_pools[pool_key] = []
                self.tunnel_pools[pool_key].append(tunnel_id)
            
            logger.info(f"SSH tunnel established: {tunnel_id} -> {local_port}")
            
        except asyncio.TimeoutError:
            tunnel_info.status = TunnelStatus.TIMEOUT
            tunnel_info.last_error = "Connection timeout"
            if not test_mode and tunnel_id in self.active_tunnels:
                del self.active_tunnels[tunnel_id]
            logger.error(f"SSH tunnel {tunnel_id} connection timeout")
        
        except Exception as e:
            tunnel_info.status = TunnelStatus.FAILED
            tunnel_info.last_error = str(e)
            tunnel_info.error_count += 1
            if not test_mode and tunnel_id in self.active_tunnels:
                del self.active_tunnels[tunnel_id]
            logger.error(f"SSH tunnel creation failed: {e}")
        
        finally:
            # Cleanup temporary key file
            if temp_key_path:
                # Ensure temp_key_path is a valid string path
                if not isinstance(temp_key_path, str):
                    logger.warning(f"Invalid temp_key_path type during cleanup: {type(temp_key_path)}, expected str")
                else:
                    try:
                        temp_path = Path(temp_key_path)
                        if temp_path.exists():
                            temp_path.unlink()
                            logger.debug(f"Cleaned up temporary key file: {temp_key_path}")
                    except Exception as e:
                        logger.warning(f"Failed to cleanup temporary key file {temp_key_path}: {e}")
        
        return tunnel_info
    
    async def close_tunnel(self, tunnel_id: str) -> bool:
        """Close SSH tunnel and cleanup resources"""
        try:
            success = False
            
            # Close listener (check for None to prevent NoneType errors)
            if tunnel_id in self.tunnel_listeners:
                try:
                    listener = self.tunnel_listeners[tunnel_id]
                    if listener is not None:
                        listener.close()
                        logger.debug(f"Closed tunnel listener for {tunnel_id}")
                    else:
                        logger.debug(f"Tunnel listener for {tunnel_id} was None (host SSH tunnel)")
                    del self.tunnel_listeners[tunnel_id]
                    success = True
                except Exception as e:
                    logger.warning(f"Failed to close tunnel listener {tunnel_id}: {e}")
            
            # Close SSH connection (check for None to prevent NoneType errors)
            if tunnel_id in self.ssh_connections:
                try:
                    ssh_conn = self.ssh_connections[tunnel_id]
                    if ssh_conn is not None:
                        ssh_conn.close()
                        logger.debug(f"Closed SSH connection for {tunnel_id}")
                    else:
                        logger.debug(f"SSH connection for {tunnel_id} was None (host SSH tunnel)")
                    del self.ssh_connections[tunnel_id]
                    success = True
                except Exception as e:
                    logger.warning(f"Failed to close SSH connection {tunnel_id}: {e}")
            
            # Handle host SSH tunnel cleanup (Docker environment)
            if hasattr(self, '_proxy_tunnels'):
                for port, proxy_tunnel_id in list(self._proxy_tunnels.items()):
                    if proxy_tunnel_id == f"tunnel_{tunnel_id.split('_')[-1] if '_' in tunnel_id else tunnel_id}":
                        try:
                            # Send close request to SSH proxy
                            await self._close_host_ssh_tunnel(proxy_tunnel_id)
                            del self._proxy_tunnels[port]
                            logger.debug(f"Closed host SSH tunnel for port {port}")
                            success = True
                        except Exception as e:
                            logger.warning(f"Failed to close host SSH tunnel on port {port}: {e}")
            
            # Remove from active tunnels and associated tracking
            if tunnel_id in self.active_tunnels:
                del self.active_tunnels[tunnel_id]
                success = True
                
                # Clean up schema discovery tunnel tracking
                schema_keys_to_remove = []
                for conn_key, tid in self.schema_discovery_tunnels.items():
                    if tid == tunnel_id:
                        schema_keys_to_remove.append(conn_key)
                
                for key in schema_keys_to_remove:
                    del self.schema_discovery_tunnels[key]
                    logger.debug(f"Removed schema discovery tunnel mapping: {key}")
                
                # Cancel keep-alive task
                if tunnel_id in self.tunnel_keep_alive_tasks:
                    self.tunnel_keep_alive_tasks[tunnel_id].cancel()
                    del self.tunnel_keep_alive_tasks[tunnel_id]
                    logger.debug(f"Cancelled keep-alive task for tunnel: {tunnel_id}")
                
                # Remove from tunnel pools
                for pool_key, tunnel_list in list(self.tunnel_pools.items()):
                    if tunnel_id in tunnel_list:
                        tunnel_list.remove(tunnel_id)
                        logger.debug(f"Removed tunnel {tunnel_id} from pool {pool_key}")
                        # Remove empty pools
                        if not tunnel_list:
                            del self.tunnel_pools[pool_key]
                            logger.debug(f"Removed empty tunnel pool: {pool_key}")
                        break
            
            if success:
                logger.info(f"SSH tunnel closed: {tunnel_id}")
            
            return success
        
        except Exception as e:
            logger.error(f"Failed to close SSH tunnel {tunnel_id}: {e}")
            return False
    
    async def get_tunnel_info(self, tunnel_id: str) -> Optional[SSHConnectionInfo]:
        """Get tunnel information and update activity"""
        tunnel_info = self.active_tunnels.get(tunnel_id)
        if tunnel_info:
            # Update activity timestamp
            tunnel_info.last_activity = datetime.now()
        return tunnel_info
    
    async def list_active_tunnels(self) -> List[SSHConnectionInfo]:
        """List all active tunnels"""
        return list(self.active_tunnels.values())
    
    async def test_database_through_tunnel(
        self, 
        tunnel_id: str,
        db_config: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Test database connection through existing tunnel"""
        try:
            tunnel_info = self.active_tunnels.get(tunnel_id)
            if not tunnel_info or tunnel_info.status != TunnelStatus.CONNECTED:
                return False
            
            if not tunnel_info.local_port:
                return False
            
            # Simple connection test to tunnel port
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            try:
                result = sock.connect_ex(('127.0.0.1', tunnel_info.local_port))
                connection_success = result == 0
                
                # Update tunnel stats
                tunnel_info.connections_count += 1
                if connection_success:
                    tunnel_info.last_activity = datetime.now()
                
                return connection_success
            finally:
                sock.close()
        
        except Exception as e:
            logger.error(f"Database test through tunnel failed: {e}")
            return False
    
    async def _create_host_ssh_tunnel(self, config: SSHTunnelConfig, local_port: int, timeout: int = 30):
        """Create SSH tunnel using SSH proxy service on host"""
        import json
        
        # Prepare configuration for SSH proxy
        proxy_config = {
            "ssh_host": config.ssh_host,
            "ssh_port": config.ssh_port,
            "ssh_user": config.ssh_user,
            "auth_method": config.auth_method.value,
            "remote_bind_host": config.remote_bind_host,
            "remote_bind_port": config.remote_bind_port,
            "connect_timeout": timeout
        }
        
        # Add authentication details
        if config.auth_method == SSHAuthMethod.PRIVATE_KEY:
            if config.private_key_content:
                # Handle private key decryption consistently with direct connections
                if not isinstance(config.private_key_content, str):
                    logger.error(f"Invalid private_key_content type: {type(config.private_key_content)}, expected str")
                    raise ValueError(f"Private key content must be a string, got {type(config.private_key_content)}")
                
                # Check if key content is already plain text (starts with -----)
                if config.private_key_content.startswith('-----BEGIN'):
                    # Plain text private key (for testing)
                    key_content = config.private_key_content
                    logger.debug("Using plain text private key for SSH proxy")
                else:
                    # Encrypted private key (for production) - use same method as direct connections
                    key_content = await security_manager.decrypt_value(
                        config.private_key_content,
                        DataClassification.RESTRICTED
                    )
                    logger.debug("Decrypted private key content for SSH proxy")
                
                proxy_config["private_key_content"] = key_content
            elif config.private_key_path:
                proxy_config["private_key_path"] = config.private_key_path
        
        # Create request for SSH proxy
        request = {
            "action": "create_tunnel",
            "config": proxy_config,
            "local_port": local_port,
            "tunnel_id": f"tunnel_{local_port}"
        }
        
        logger.info(f"Requesting SSH tunnel from proxy: {config.ssh_user}@{config.ssh_host}:{config.ssh_port}")
        
        try:
            # Connect to SSH proxy service
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection('schema-diff-ssh-proxy', 9999),
                timeout=10
            )
            
            # Send request
            writer.write(json.dumps(request).encode())
            await writer.drain()
            
            # Read response
            response_data = await asyncio.wait_for(reader.read(4096), timeout=30)
            response = json.loads(response_data.decode())
            
            # Close connection
            writer.close()
            await writer.wait_closed()
            
            if response.get('success'):
                logger.info(f"SSH tunnel established successfully via proxy on port {local_port}")
                # Store tunnel info for cleanup
                if not hasattr(self, '_proxy_tunnels'):
                    self._proxy_tunnels = {}
                self._proxy_tunnels[local_port] = response.get('tunnel_id')
            else:
                error_msg = response.get('error', 'Unknown error')
                logger.error(f"SSH proxy tunnel failed: {error_msg}")
                raise Exception(f"SSH proxy tunnel failed: {error_msg}")
                
        except Exception as e:
            logger.error(f"Failed to communicate with SSH proxy: {e}")
            raise

    async def _close_host_ssh_tunnel(self, proxy_tunnel_id: str):
        """Close SSH tunnel via proxy service"""
        import json
        
        request = {
            "action": "close_tunnel",
            "tunnel_id": proxy_tunnel_id
        }
        
        try:
            # Connect to SSH proxy service
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection('schema-diff-ssh-proxy', 9999),
                timeout=5
            )
            
            # Send close request
            writer.write(json.dumps(request).encode())
            await writer.drain()
            
            # Read response
            response_data = await asyncio.wait_for(reader.read(4096), timeout=10)
            response = json.loads(response_data.decode())
            
            # Close connection
            writer.close()
            await writer.wait_closed()
            
            if response.get('success'):
                logger.debug(f"SSH proxy tunnel closed successfully: {proxy_tunnel_id}")
            else:
                error_msg = response.get('error', 'Unknown error')
                logger.warning(f"SSH proxy tunnel close failed: {error_msg}")
                
        except Exception as e:
            logger.warning(f"Failed to close SSH proxy tunnel {proxy_tunnel_id}: {e}")

    async def get_tunnel_metrics(self, tunnel_id: str) -> Dict[str, Any]:
        """Get detailed tunnel metrics and statistics"""
        tunnel_info = self.active_tunnels.get(tunnel_id)
        if not tunnel_info:
            return {}
        
        # Basic metrics
        metrics = {
            "tunnel_id": tunnel_id,
            "status": tunnel_info.status.value,
            "local_port": tunnel_info.local_port,
            "connected_at": tunnel_info.connected_at.isoformat() if tunnel_info.connected_at else None,
            "last_activity": tunnel_info.last_activity.isoformat() if tunnel_info.last_activity else None,
            "connection_latency_ms": tunnel_info.connection_latency_ms,
            "connections_count": tunnel_info.connections_count,
            "error_count": tunnel_info.error_count,
            "last_error": tunnel_info.last_error
        }
        
        # Calculate uptime
        if tunnel_info.connected_at:
            uptime_seconds = (datetime.now() - tunnel_info.connected_at).total_seconds()
            metrics["uptime_seconds"] = uptime_seconds
            metrics["uptime_human"] = str(timedelta(seconds=int(uptime_seconds)))
        
        # Health status
        metrics["is_healthy"] = tunnel_info.is_healthy()
        
        return metrics
    
    async def reconnect_tunnel(self, tunnel_id: str) -> bool:
        """Attempt to reconnect a failed tunnel"""
        tunnel_info = self.active_tunnels.get(tunnel_id)
        if not tunnel_info:
            return False
        
        if tunnel_info.status == TunnelStatus.CONNECTED:
            return True  # Already connected
        
        # Close existing connection if any
        await self.close_tunnel(tunnel_id)
        
        # Attempt to recreate tunnel
        try:
            new_tunnel_info = await self.create_tunnel(tunnel_info.config)
            if new_tunnel_info.status == TunnelStatus.CONNECTED:
                # Update existing tunnel info
                tunnel_info.status = new_tunnel_info.status
                tunnel_info.local_port = new_tunnel_info.local_port
                tunnel_info.connected_at = new_tunnel_info.connected_at
                tunnel_info.last_activity = new_tunnel_info.last_activity
                tunnel_info.connection_latency_ms = new_tunnel_info.connection_latency_ms
                tunnel_info.reconnect_attempts += 1
                tunnel_info.last_error = None
                
                logger.info(f"SSH tunnel reconnected successfully: {tunnel_id}")
                return True
        
        except Exception as e:
            tunnel_info.reconnect_attempts += 1
            tunnel_info.last_error = f"Reconnection failed: {str(e)}"
            logger.error(f"Failed to reconnect SSH tunnel {tunnel_id}: {e}")
        
        return False
    
    async def shutdown(self):
        """Shutdown tunnel manager and close all tunnels"""
        logger.info("Shutting down SSH tunnel manager...")
        
        # Stop background tasks
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        
        # Close all active tunnels
        tunnel_ids = list(self.active_tunnels.keys())
        for tunnel_id in tunnel_ids:
            await self.close_tunnel(tunnel_id)
        
        logger.info("SSH tunnel manager shutdown complete")


# Global tunnel manager instance
tunnel_manager = SSHTunnelManager()