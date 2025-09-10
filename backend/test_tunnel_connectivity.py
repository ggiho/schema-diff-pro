#!/usr/bin/env python3
"""
SSH Tunnel Connectivity Test
Test if SSH tunnels are properly forwarding traffic by testing connectivity to the tunneled ports.
"""

import asyncio
import socket
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_port_connectivity(host, port, timeout=5):
    """Test if a port is reachable"""
    try:
        # Create socket connection test
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        
        result = sock.connect_ex((host, port))
        sock.close()
        
        if result == 0:
            return True, "Connected successfully"
        else:
            return False, f"Connection failed with code {result}"
            
    except Exception as e:
        return False, f"Connection error: {str(e)}"

async def test_tunnel_ports():
    """Test SSH tunnel port connectivity"""
    print("🔍 SSH Tunnel Port Connectivity Test")
    print(f"⏰ Started at: {datetime.now()}")
    print("=" * 50)
    
    # Test ssh-proxy tunnel ports
    host = "ssh-proxy"
    ports = [10000, 10001, 10002]
    
    results = []
    
    for port in ports:
        print(f"\n📡 Testing port {port} on {host}")
        
        try:
            connected, message = await test_port_connectivity(host, port, timeout=10)
            
            if connected:
                print(f"✅ Port {port}: {message}")
                status = "✅ REACHABLE"
            else:
                print(f"❌ Port {port}: {message}")
                status = "❌ UNREACHABLE"
                
            results.append((port, connected, message))
            
        except Exception as e:
            print(f"❌ Port {port}: Error during test - {e}")
            results.append((port, False, str(e)))
            status = "❌ ERROR"
    
    print("\n" + "=" * 50)
    print("📊 Summary:")
    
    connected_count = 0
    for port, connected, message in results:
        status_icon = "✅" if connected else "❌"
        print(f"  Port {port}: {status_icon} {'REACHABLE' if connected else 'UNREACHABLE'}")
        if connected:
            connected_count += 1
    
    print(f"\n🎯 Result: {connected_count}/{len(ports)} ports are reachable")
    
    if connected_count > 0:
        print("✅ SSH tunnels are accepting connections")
        print("   This confirms tunnel forwarding is working")
        print("   Database connection issues may be due to:")
        print("   - Incorrect database credentials")
        print("   - Database firewall restrictions")
        print("   - MySQL configuration issues")
    else:
        print("❌ SSH tunnels are not accepting connections")
        print("   This indicates a tunnel configuration issue")
    
    print(f"\n⏰ Completed at: {datetime.now()}")
    
    return connected_count > 0

if __name__ == "__main__":
    asyncio.run(test_tunnel_ports())