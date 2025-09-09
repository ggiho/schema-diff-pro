"""
SSH Tunnel API Router
Provides REST endpoints for SSH tunnel management
"""

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from typing import Dict, Any, Optional, List
import asyncio
import logging
from datetime import datetime

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from models.ssh_tunnel import (
        SSHTunnelConfig, 
        SSHTunnelTest, 
        SSHTunnelTestResult, 
        SSHConnectionInfo,
        TunnelStatus,
        SSHKeyInfo,
        DatabaseConfigWithSSH
    )
    from models.base import DatabaseConfigWithSSH as BaseDBConfigWithSSH
else:
    # Import at runtime to avoid circular imports
    import importlib
    def _get_ssh_models():
        ssh_module = importlib.import_module('models.ssh_tunnel')
        base_module = importlib.import_module('models.base')
        return (
            ssh_module.SSHTunnelConfig,
            ssh_module.SSHTunnelTest,
            ssh_module.SSHTunnelTestResult,
            ssh_module.SSHConnectionInfo,
            ssh_module.TunnelStatus,
            ssh_module.SSHKeyInfo,
            ssh_module.DatabaseConfigWithSSH,
            base_module.DatabaseConfigWithSSH
        )
    
    (SSHTunnelConfig, SSHTunnelTest, SSHTunnelTestResult, 
     SSHConnectionInfo, TunnelStatus, SSHKeyInfo, 
     DatabaseConfigWithSSH, BaseDBConfigWithSSH) = _get_ssh_models()
from services.ssh_tunnel_manager import tunnel_manager
from core.security import security_manager, DataClassification

logger = logging.getLogger(__name__)
router = APIRouter()




# Dependency for checking if SSH tunneling is available
def check_ssh_available():
    """Dependency to check if SSH functionality is available"""
    try:
        import asyncssh
        return True
    except ImportError:
        raise HTTPException(
            status_code=503, 
            detail="SSH tunneling is not available. Please install asyncssh: pip install asyncssh"
        )


@router.post("/tunnel/test", response_model=SSHTunnelTestResult)
async def test_ssh_tunnel(
    request: Request,
    _: bool = Depends(check_ssh_available)
) -> SSHTunnelTestResult:
    """Test SSH tunnel connection and optionally database connection"""
    start_time = datetime.now()
    result = SSHTunnelTestResult(
        success=False,
        tunnel_status=TunnelStatus.DISCONNECTED,
        total_test_time_ms=0
    )
    
    try:
        # Parse request body manually for debugging
        body = await request.body()
        logger.info(f"Received SSH tunnel test request")
        logger.debug(f"Raw request body: {body}")
        
        # Parse JSON
        import json
        try:
            request_data = json.loads(body)
            logger.info(f"Parsed request data keys: {list(request_data.keys())}")
            if 'config' in request_data:
                config_data = request_data['config']
                logger.info(f"SSH config data: auth_method={config_data.get('auth_method')}, private_key_path={config_data.get('private_key_path')}, has_private_key_content={bool(config_data.get('private_key_content'))}")
                if config_data.get('private_key_content'):
                    logger.info(f"Private key content length: {len(config_data['private_key_content'])}")
                    logger.info(f"Private key content first 50 chars: {config_data['private_key_content'][:50]}")
                logger.info(f"All config keys: {list(config_data.keys())}")
                # Log all non-sensitive data
                for key, value in config_data.items():
                    if key not in ['ssh_password', 'private_key_passphrase']:  # Allow private_key_content for debugging
                        if key == 'private_key_content':
                            logger.info(f"Config {key}: [PRESENT - {len(value)} chars] (type: {type(value)})")
                        else:
                            logger.info(f"Config {key}: {value} (type: {type(value)})")
        except Exception as e:
            logger.error(f"Failed to parse JSON: {e}")
            raise HTTPException(status_code=400, detail=f"Invalid JSON: {e}")
        
        # Try to create SSH config first
        try:
            logger.info("Creating SSHTunnelConfig directly...")
            
            # Log the EXACT dictionary being passed to Pydantic
            config_dict = request_data['config']
            logger.info(f"EXACT dict being passed to SSHTunnelConfig:")
            for key, value in config_dict.items():
                if key == 'private_key_content':
                    logger.info(f"  {key}: [LENGTH={len(value) if value else 0}] (type: {type(value)})")
                    if value:
                        logger.info(f"  {key} first 50 chars: '{value[:50]}'")
                elif key not in ['ssh_password', 'private_key_passphrase']:
                    logger.info(f"  {key}: {repr(value)} (type: {type(value)})")
            
            ssh_config = SSHTunnelConfig(**config_dict)
            logger.info(f"Successfully created SSHTunnelConfig")
            
            # Log what actually got stored in the created model
            logger.info(f"Created SSHTunnelConfig contents:")
            logger.info(f"  ssh_host: {ssh_config.ssh_host}")
            logger.info(f"  ssh_user: {ssh_config.ssh_user}")
            logger.info(f"  auth_method: {ssh_config.auth_method}")
            logger.info(f"  private_key_path: {repr(ssh_config.private_key_path)}")
            logger.info(f"  private_key_content: [LENGTH={len(ssh_config.private_key_content) if ssh_config.private_key_content else 0}] (type: {type(ssh_config.private_key_content)})")
            if ssh_config.private_key_content:
                logger.info(f"  private_key_content first 50 chars: '{ssh_config.private_key_content[:50]}'")
            logger.info(f"  enabled: {ssh_config.enabled}")
            
            # Now create the test config
            test_config = SSHTunnelTest(
                config=ssh_config,
                test_database_connection=request_data.get('test_database_connection', False),
                timeout_seconds=request_data.get('timeout_seconds', 30)
            )
            logger.info(f"Successfully parsed SSHTunnelTest")
        except Exception as e:
            logger.error(f"Failed to create SSH models: {e}")
            logger.error(f"Exception type: {type(e)}")
            
            # Print full validation error details for Pydantic errors
            if hasattr(e, 'errors'):
                logger.error(f"Pydantic validation errors:")
                for error in e.errors():
                    logger.error(f"  Field: {error.get('loc')}, Type: {error.get('type')}, Message: {error.get('msg')}")
                    logger.error(f"  Input: {error.get('input')}")
            
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise HTTPException(status_code=422, detail=f"Validation error: {e}")
        
        logger.debug(f"Test config auth_method: {test_config.config.auth_method}")
        logger.debug(f"Test config ssh_host: {test_config.config.ssh_host}")
        logger.debug(f"Test config ssh_port: {test_config.config.ssh_port}")
        logger.debug(f"Test config ssh_user: {test_config.config.ssh_user}")
        logger.info(f"Testing SSH tunnel to {test_config.config.ssh_host}:{test_config.config.ssh_port}")
        
        # Validate SSH configuration
        validation_errors = await tunnel_manager.validate_config(test_config.config)
        if validation_errors:
            for error in validation_errors:
                result.add_error(error)
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
        
        result.tunnel_status = tunnel_info.status
        
        if tunnel_info.status == TunnelStatus.CONNECTED:
            result.ssh_connection_success = True
            result.ssh_connection_time_ms = (ssh_end - ssh_start).total_seconds() * 1000
            result.local_port = tunnel_info.local_port
            
            # Get SSH server info
            result.ssh_server_info = {
                "host": test_config.config.ssh_host,
                "port": test_config.config.ssh_port,
                "user": test_config.config.ssh_user,
                "connection_latency_ms": tunnel_info.connection_latency_ms
            }
            
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
                    result.add_warning("SSH tunnel connected but database port test failed")
            
            # Cleanup test tunnel
            await tunnel_manager.close_tunnel(tunnel_info.tunnel_id)
            
            result.success = result.ssh_connection_success and (
                not test_config.test_database_connection or result.database_connection_success
            )
            
        else:
            result.add_error(f"SSH connection failed: {tunnel_info.last_error or 'Unknown error'}")
    
    except asyncio.TimeoutError:
        result.add_error(f"Connection timeout after {test_config.timeout_seconds} seconds")
        result.tunnel_status = TunnelStatus.TIMEOUT
    except Exception as e:
        logger.error(f"SSH tunnel test failed: {str(e)}")
        result.add_error(f"Test failed: {str(e)}")
        result.tunnel_status = TunnelStatus.FAILED
    
    result.total_test_time_ms = (datetime.now() - start_time).total_seconds() * 1000
    logger.info(f"SSH tunnel test completed in {result.total_test_time_ms:.2f}ms, success: {result.success}")
    return result


@router.post("/tunnel/create", response_model=SSHConnectionInfo)
async def create_ssh_tunnel(
    config: Dict[str, Any],
    _: bool = Depends(check_ssh_available)
) -> SSHConnectionInfo:
    """Create and establish SSH tunnel"""
    try:
        logger.info(f"Creating SSH tunnel to {config['ssh_host']}:{config['ssh_port']}")
        
        # Encrypt sensitive data before storing
        if config.get('ssh_password'):
            config['ssh_password'] = await security_manager.encrypt_value(
                config['ssh_password'],
                DataClassification.CONFIDENTIAL
            )
        
        if config.get('private_key_content'):
            config['private_key_content'] = await security_manager.encrypt_value(
                config['private_key_content'],
                DataClassification.RESTRICTED
            )
        
        if config.get('private_key_passphrase'):
            config['private_key_passphrase'] = await security_manager.encrypt_value(
                config['private_key_passphrase'],
                DataClassification.RESTRICTED
            )
        
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
                detail=f"Failed to establish SSH tunnel: {tunnel_info.last_error or 'Unknown error'}"
            )
        
        logger.info(f"SSH tunnel created successfully: {tunnel_info.tunnel_id}")
        return tunnel_info
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create SSH tunnel: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tunnel/{tunnel_id}/status", response_model=SSHConnectionInfo)
async def get_tunnel_status(
    tunnel_id: str,
    _: bool = Depends(check_ssh_available)
) -> SSHConnectionInfo:
    """Get SSH tunnel status and information"""
    tunnel_info = await tunnel_manager.get_tunnel_info(tunnel_id)
    if not tunnel_info:
        raise HTTPException(status_code=404, detail="SSH tunnel not found")
    
    return tunnel_info


@router.get("/tunnel/{tunnel_id}/metrics")
async def get_tunnel_metrics(
    tunnel_id: str,
    _: bool = Depends(check_ssh_available)
) -> Dict[str, Any]:
    """Get detailed tunnel metrics and statistics"""
    metrics = await tunnel_manager.get_tunnel_metrics(tunnel_id)
    if not metrics:
        raise HTTPException(status_code=404, detail="SSH tunnel not found")
    
    return metrics


@router.post("/tunnel/{tunnel_id}/reconnect")
async def reconnect_tunnel(
    tunnel_id: str,
    _: bool = Depends(check_ssh_available)
) -> Dict[str, Any]:
    """Attempt to reconnect a failed SSH tunnel"""
    success = await tunnel_manager.reconnect_tunnel(tunnel_id)
    
    if success:
        return {
            "status": "success",
            "message": f"SSH tunnel {tunnel_id} reconnected successfully"
        }
    else:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to reconnect SSH tunnel {tunnel_id}"
        )


@router.delete("/tunnel/{tunnel_id}")
async def close_ssh_tunnel(
    tunnel_id: str,
    _: bool = Depends(check_ssh_available)
) -> Dict[str, str]:
    """Close SSH tunnel"""
    try:
        success = await tunnel_manager.close_tunnel(tunnel_id)
        if success:
            logger.info(f"SSH tunnel closed: {tunnel_id}")
            return {"status": "closed", "tunnel_id": tunnel_id}
        else:
            raise HTTPException(status_code=404, detail="SSH tunnel not found")
    except Exception as e:
        logger.error(f"Failed to close SSH tunnel {tunnel_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tunnels", response_model=List[SSHConnectionInfo])
async def list_active_tunnels(
    _: bool = Depends(check_ssh_available)
) -> List[SSHConnectionInfo]:
    """List all active SSH tunnels"""
    return await tunnel_manager.list_active_tunnels()


@router.post("/key/validate", response_model=SSHKeyInfo)
async def validate_ssh_key(
    key_data: Dict[str, Any]
) -> SSHKeyInfo:
    """Validate SSH private key"""
    try:
        key_info = await security_manager.validate_ssh_key(
            key_path=key_data.get('key_path'),
            key_content=key_data.get('key_content'),
            passphrase=key_data.get('passphrase')
        )
        
        logger.info(f"SSH key validation: valid={key_info.is_valid}, type={key_info.key_type}")
        return key_info
    
    except Exception as e:
        logger.error(f"SSH key validation failed: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/keys", response_model=List[Dict[str, Any]])
async def list_stored_keys() -> List[Dict[str, Any]]:
    """List stored SSH keys (metadata only)"""
    try:
        keys = await security_manager.list_stored_keys()
        return keys
    except Exception as e:
        logger.error(f"Failed to list SSH keys: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/key/store")
async def store_ssh_key(
    key_data: Dict[str, Any]
) -> Dict[str, Any]:
    """Store SSH key securely"""
    try:
        required_fields = ['key_id', 'key_content']
        for field in required_fields:
            if field not in key_data:
                raise HTTPException(status_code=400, detail=f"Missing required field: {field}")
        
        metadata = await security_manager.secure_store_ssh_key(
            key_id=key_data['key_id'],
            key_content=key_data['key_content'],
            passphrase=key_data.get('passphrase'),
            metadata=key_data.get('metadata', {})
        )
        
        logger.info(f"SSH key stored: {key_data['key_id']}")
        return {
            "status": "success",
            "key_id": key_data['key_id'],
            "metadata": metadata
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to store SSH key: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/key/{key_id}")
async def delete_ssh_key(key_id: str) -> Dict[str, Any]:
    """Delete stored SSH key"""
    try:
        success = await security_manager.delete_ssh_key(key_id)
        if success:
            logger.info(f"SSH key deleted: {key_id}")
            return {"status": "deleted", "key_id": key_id}
        else:
            raise HTTPException(status_code=404, detail="SSH key not found")
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete SSH key {key_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/database/test-with-tunnel")
async def test_database_with_tunnel(
    config: Dict[str, Any],
    _: bool = Depends(check_ssh_available)
) -> Dict[str, Any]:
    """Test database connection with SSH tunnel"""
    ssh_tunnel = config.get('ssh_tunnel')
    if not ssh_tunnel or not ssh_tunnel.get('enabled'):
        raise HTTPException(status_code=400, detail="SSH tunnel not enabled in configuration")
    
    tunnel_info = None
    try:
        logger.info(f"Testing database connection through SSH tunnel to {ssh_tunnel.get('ssh_host')}")
        
        # Encrypt sensitive data
        if ssh_tunnel.get('ssh_password'):
            ssh_tunnel['ssh_password'] = await security_manager.encrypt_value(
                ssh_tunnel['ssh_password'],
                DataClassification.CONFIDENTIAL
            )
        
        if ssh_tunnel.get('private_key_content'):
            ssh_tunnel['private_key_content'] = await security_manager.encrypt_value(
                ssh_tunnel['private_key_content'],
                DataClassification.RESTRICTED
            )
        
        if ssh_tunnel.get('private_key_passphrase'):
            ssh_tunnel['private_key_passphrase'] = await security_manager.encrypt_value(
                ssh_tunnel['private_key_passphrase'],
                DataClassification.RESTRICTED
            )
        
        # Create properly validated SSHTunnelConfig object
        try:
            from models.ssh_tunnel import SSHTunnelConfig
            tunnel_config = SSHTunnelConfig(**ssh_tunnel)
        except Exception as e:
            logger.error(f"Invalid SSH tunnel configuration: {e}")
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid SSH tunnel configuration: {e}"
            )
        
        # Create SSH tunnel
        tunnel_info = await tunnel_manager.create_tunnel(tunnel_config)
        
        if tunnel_info.status != TunnelStatus.CONNECTED:
            raise HTTPException(
                status_code=500,
                detail=f"SSH tunnel connection failed: {tunnel_info.last_error}"
            )
        
        # Test database connection through tunnel
        db_test_success = await tunnel_manager.test_database_through_tunnel(
            tunnel_info.tunnel_id
        )
        
        # TODO: Implement actual database connection test
        # For now, we'll use the simple port connectivity test
        
        result = {
            "success": db_test_success,
            "tunnel_info": {
                "tunnel_id": tunnel_info.tunnel_id,
                "local_port": tunnel_info.local_port,
                "status": tunnel_info.status.value,
                "connection_latency_ms": tunnel_info.connection_latency_ms
            },
            "database_info": {
                "host": config.get('host'),
                "port": config.get('port'),
                "database": config.get('database'),
                "effective_host": "127.0.0.1",
                "effective_port": tunnel_info.local_port,
                "connection_test": db_test_success
            }
        }
        
        if not db_test_success:
            result["error"] = "Database connection test failed through SSH tunnel"
        
        logger.info(f"Database test through SSH tunnel completed: success={db_test_success}")
        return result
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Database test with SSH tunnel failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    
    finally:
        # Cleanup tunnel if created
        if tunnel_info and tunnel_info.tunnel_id:
            try:
                await tunnel_manager.close_tunnel(tunnel_info.tunnel_id)
            except Exception as e:
                logger.warning(f"Failed to cleanup test tunnel: {e}")


@router.get("/status")
async def get_ssh_status() -> Dict[str, Any]:
    """Get SSH tunneling system status and health check"""
    try:
        import asyncssh
        asyncssh_available = True
        asyncssh_version = getattr(asyncssh, '__version__', 'unknown')
    except ImportError:
        asyncssh_available = False
        asyncssh_version = None
    
    # Get tunnel manager statistics
    active_tunnels = await tunnel_manager.list_active_tunnels()
    tunnel_stats = {
        "total": len(active_tunnels),
        "connected": len([t for t in active_tunnels if t.status == TunnelStatus.CONNECTED]),
        "failed": len([t for t in active_tunnels if t.status == TunnelStatus.FAILED]),
        "connecting": len([t for t in active_tunnels if t.status == TunnelStatus.CONNECTING])
    }
    
    # Get security manager status
    security_status = security_manager.get_security_status()
    
    return {
        "ssh_available": asyncssh_available,
        "asyncssh_version": asyncssh_version,
        "tunnel_statistics": tunnel_stats,
        "security_status": security_status,
        "system_status": "healthy" if asyncssh_available else "degraded"
    }


@router.post("/shutdown")
async def shutdown_ssh_system(
    background_tasks: BackgroundTasks
) -> Dict[str, str]:
    """Shutdown SSH tunnel system (close all tunnels)"""
    try:
        # Use background task to avoid blocking the response
        background_tasks.add_task(tunnel_manager.shutdown)
        
        logger.info("SSH tunnel system shutdown initiated")
        return {"status": "shutdown_initiated", "message": "All SSH tunnels will be closed"}
    
    except Exception as e:
        logger.error(f"Failed to shutdown SSH system: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))