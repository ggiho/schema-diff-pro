#!/usr/bin/env python3
"""
SSH Proxy Service - Runs on host network to forward SSH connections
This allows Docker containers to make SSH connections that appear to come from host IP
"""

import asyncio
import json
import logging
import tempfile
import os
import subprocess
import signal
import sys
import socket
import glob
from typing import Dict, Any, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - ssh_proxy - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class SSHProxy:
    def __init__(self, listen_port: int = 9999):
        self.listen_port = listen_port
        self.active_tunnels: Dict[str, subprocess.Popen] = {}
        self.server = None
    
    def _find_free_port(self, start_port: int = 10000) -> int:
        """Find available local port for tunnel"""
        for port in range(start_port, start_port + 1000):
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.bind(('127.0.0.1', port))
                    return port
            except OSError:
                continue
        raise RuntimeError("No free ports available")
        
    async def start(self):
        """Start the SSH proxy server"""
        logger.info(f"Starting SSH proxy server on port {self.listen_port}")
        
        self.server = await asyncio.start_server(
            self.handle_client,
            '0.0.0.0',  # Listen on all interfaces
            self.listen_port
        )
        
        logger.info(f"SSH proxy server started on {self.listen_port}")
        await self.server.serve_forever()
    
    async def handle_client(self, reader, writer):
        """Handle incoming client connections"""
        client_addr = writer.get_extra_info('peername')
        logger.info(f"New client connection from {client_addr}")
        
        try:
            # Read request from client
            data = await reader.read(4096)
            if not data:
                return
                
            # Parse JSON request
            request = json.loads(data.decode())
            
            # Handle different request types
            if request.get('action') == 'create_tunnel':
                response = await self.create_tunnel(request)
            elif request.get('action') == 'close_tunnel':
                response = await self.close_tunnel(request)
            elif request.get('action') == 'test_connection':
                response = await self.test_connection(request)
            else:
                response = {'success': False, 'error': 'Unknown action'}
            
            # Send response
            writer.write(json.dumps(response).encode())
            await writer.drain()
            
        except Exception as e:
            logger.error(f"Error handling client {client_addr}: {e}")
            error_response = {'success': False, 'error': str(e)}
            writer.write(json.dumps(error_response).encode())
            await writer.drain()
        finally:
            writer.close()
            await writer.wait_closed()
    
    async def create_tunnel(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Create SSH tunnel using host's SSH client"""
        try:
            config = request['config']
            requested_port = request.get('local_port')
            tunnel_id = request.get('tunnel_id', f"tunnel_{requested_port}")
            
            # Find available port - use requested port or find a free one
            if requested_port:
                try:
                    # Test if requested port is available
                    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                        s.bind(('127.0.0.1', requested_port))
                    local_port = requested_port
                except OSError:
                    # Requested port is busy, find a free one
                    local_port = self._find_free_port()
                    logger.info(f"Requested port {requested_port} is busy, using port {local_port} instead")
            else:
                local_port = self._find_free_port()
            
            logger.info(f"Creating SSH tunnel {tunnel_id} on port {local_port}")
            
            # Build SSH command
            ssh_cmd = [
                "ssh",  # Use PATH to find SSH binary
                "-L", f"0.0.0.0:{local_port}:{config['remote_bind_host']}:{config['remote_bind_port']}",
                "-N",  # Don't execute remote command
                "-o", "StrictHostKeyChecking=no",
                "-o", "UserKnownHostsFile=/dev/null",
                "-o", f"ConnectTimeout={config.get('connect_timeout', 30)}",
                "-o", "ExitOnForwardFailure=yes",
                "-o", f"ServerAliveInterval={config.get('keepalive_interval', 30)}",
                "-o", "ServerAliveCountMax=3",
                "-o", "TCPKeepAlive=yes",
            ]
            
            # Handle authentication
            if config.get('auth_method') == 'private_key':
                if config.get('private_key_content'):
                    # Write private key to temporary file with proper formatting
                    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.pem', prefix='ssh_key_') as key_file:
                        key_content = config['private_key_content']
                        
                        # Ensure proper private key formatting
                        if not key_content.startswith('-----BEGIN'):
                            logger.error("Invalid private key format - missing header")
                            return {'success': False, 'error': 'Invalid private key format'}
                        
                        # Ensure proper line endings
                        if not key_content.endswith('\n'):
                            key_content += '\n'
                        
                        key_file.write(key_content)
                        key_file.flush()
                        
                        # Set strict file permissions
                        os.chmod(key_file.name, 0o600)
                        
                        # Add SSH options for key handling
                        ssh_cmd.extend([
                            "-i", key_file.name,
                            "-o", "IdentitiesOnly=yes",
                            "-o", "PasswordAuthentication=no"
                        ])
                        
                        logger.debug(f"Private key written to {key_file.name} with mode 600")
                        
                elif config.get('private_key_path'):
                    ssh_cmd.extend([
                        "-i", config['private_key_path'],
                        "-o", "IdentitiesOnly=yes",
                        "-o", "PasswordAuthentication=no"
                    ])
            
            # Add SSH port if not default
            if config.get('ssh_port', 22) != 22:
                ssh_cmd.extend(["-p", str(config['ssh_port'])])
            
            # Add user and host
            ssh_cmd.append(f"{config['ssh_user']}@{config['ssh_host']}")
            
            logger.info(f"Executing SSH command: {' '.join(ssh_cmd[:-1])} ***@{config['ssh_host']}")
            
            # Start SSH process
            process = subprocess.Popen(
                ssh_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.PIPE
            )
            
            # Wait for tunnel to establish and verify it's working
            await asyncio.sleep(3)  # Increased wait time
            
            # Check if process is still running
            if process.poll() is None:
                # Additional verification: test if the tunnel port is actually accessible
                await asyncio.sleep(1)  # Give tunnel more time to fully establish
                
                # Test tunnel connectivity
                try:
                    test_reader, test_writer = await asyncio.wait_for(
                        asyncio.open_connection('127.0.0.1', local_port),
                        timeout=5
                    )
                    test_writer.close()
                    await test_writer.wait_closed()
                    logger.info(f"SSH tunnel {tunnel_id} connectivity verified on port {local_port}")
                except Exception as e:
                    logger.warning(f"SSH tunnel {tunnel_id} connectivity test failed: {e}, but process is running")
                    # Continue anyway as the tunnel might still work for specific protocols
                logger.info(f"SSH tunnel {tunnel_id} established successfully")
                self.active_tunnels[tunnel_id] = process
                return {
                    'success': True,
                    'tunnel_id': tunnel_id,
                    'local_port': local_port,
                    'message': 'Tunnel created successfully'
                }
            else:
                stdout, stderr = process.communicate()
                error_msg = stderr.decode() if stderr else stdout.decode()
                logger.error(f"SSH tunnel failed: {error_msg}")
                return {
                    'success': False,
                    'error': f'SSH tunnel failed: {error_msg}'
                }
                
        except Exception as e:
            logger.error(f"Failed to create tunnel: {e}")
            return {'success': False, 'error': str(e)}
    
    async def close_tunnel(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Close SSH tunnel"""
        try:
            tunnel_id = request['tunnel_id']
            
            if tunnel_id in self.active_tunnels:
                process = self.active_tunnels[tunnel_id]
                process.terminate()
                
                # Wait for process to terminate
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                
                del self.active_tunnels[tunnel_id]
                logger.info(f"SSH tunnel {tunnel_id} closed")
                
                # Clean up any temporary key files
                self._cleanup_temp_files()
                
                return {'success': True, 'message': 'Tunnel closed'}
            else:
                return {'success': False, 'error': 'Tunnel not found'}
                
        except Exception as e:
            logger.error(f"Failed to close tunnel: {e}")
            return {'success': False, 'error': str(e)}
    
    async def test_connection(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Test SSH connection without creating tunnel"""
        try:
            config = request['config']
            
            # Build SSH command for connection test
            ssh_cmd = [
                "ssh",  # Use PATH to find SSH binary
                "-o", "StrictHostKeyChecking=no",
                "-o", "UserKnownHostsFile=/dev/null",
                "-o", f"ConnectTimeout={config.get('connect_timeout', 10)}",
                "-o", "BatchMode=yes",  # Don't prompt for passwords
                "-T",  # Don't allocate TTY
            ]
            
            # Handle authentication
            if config.get('auth_method') == 'private_key':
                if config.get('private_key_content'):
                    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.pem') as key_file:
                        key_file.write(config['private_key_content'])
                        key_file.flush()
                        os.chmod(key_file.name, 0o600)
                        ssh_cmd.extend(["-i", key_file.name])
                elif config.get('private_key_path'):
                    ssh_cmd.extend(["-i", config['private_key_path']])
            
            # Add SSH port if not default
            if config.get('ssh_port', 22) != 22:
                ssh_cmd.extend(["-p", str(config['ssh_port'])])
            
            # Add user and host
            ssh_cmd.append(f"{config['ssh_user']}@{config['ssh_host']}")
            ssh_cmd.append("echo 'SSH connection successful'")
            
            logger.info(f"Testing SSH connection to {config['ssh_host']}")
            
            # Execute SSH test
            process = subprocess.run(
                ssh_cmd,
                capture_output=True,
                timeout=30
            )
            
            if process.returncode == 0:
                return {
                    'success': True,
                    'message': 'SSH connection test successful'
                }
            else:
                error_msg = process.stderr.decode() if process.stderr else 'Unknown error'
                return {
                    'success': False,
                    'error': f'SSH connection test failed: {error_msg}'
                }
                
        except Exception as e:
            logger.error(f"SSH connection test failed: {e}")
            return {'success': False, 'error': str(e)}
    
    def _cleanup_temp_files(self):
        """Clean up temporary SSH key files"""
        try:
            temp_dir = tempfile.gettempdir()
            ssh_key_files = glob.glob(os.path.join(temp_dir, 'ssh_key_*.pem'))
            for key_file in ssh_key_files:
                try:
                    if os.path.exists(key_file):
                        os.unlink(key_file)
                        logger.debug(f"Cleaned up temporary key file: {key_file}")
                except Exception as e:
                    logger.warning(f"Failed to clean up temp file {key_file}: {e}")
        except Exception as e:
            logger.warning(f"Failed to clean up temp files: {e}")
    
    async def shutdown(self):
        """Shutdown proxy and close all tunnels"""
        logger.info("Shutting down SSH proxy...")
        
        # Close all active tunnels
        for tunnel_id, process in self.active_tunnels.items():
            try:
                process.terminate()
                process.wait(timeout=5)
            except:
                process.kill()
        
        self.active_tunnels.clear()
        
        # Clean up temporary files
        self._cleanup_temp_files()
        
        if self.server:
            self.server.close()
            await self.server.wait_closed()
        
        logger.info("SSH proxy shutdown complete")

async def main():
    """Main function"""
    proxy = SSHProxy()
    
    # Setup signal handlers
    def signal_handler():
        logger.info("Received shutdown signal")
        asyncio.create_task(proxy.shutdown())
    
    # Register signal handlers
    for sig in [signal.SIGTERM, signal.SIGINT]:
        signal.signal(sig, lambda s, f: signal_handler())
    
    try:
        await proxy.start()
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
    except Exception as e:
        logger.error(f"SSH proxy error: {e}")
    finally:
        await proxy.shutdown()

if __name__ == "__main__":
    asyncio.run(main())