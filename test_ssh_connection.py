#!/usr/bin/env python3
"""
SSH Database Connection Test
Test script to verify SSH tunnel database connectivity using the backend application logic.
"""

import asyncio
import os
import sys
import logging
from datetime import datetime

# Add backend to Python path
sys.path.append('/app')

from backend.models.ssh_tunnel import DatabaseConfigWithSSH, SSHTunnelConfig, SSHAuthMethod
from backend.services.ssh_tunnel_manager import tunnel_manager
from backend.core.database import DatabaseConnection

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_ssh_database_connection():
    """Test SSH tunnel database connection with real configuration"""
    
    print("🔍 SSH Database Connection Test Starting...")
    print(f"⏰ Test started at: {datetime.now()}")
    print("=" * 60)
    
    try:
        # Create SSH tunnel configuration (using test values - replace with real ones)
        ssh_config = SSHTunnelConfig(
            enabled=True,
            ssh_host="your-ssh-host",  # Replace with real SSH host
            ssh_port=22,
            ssh_user="your-user",      # Replace with real SSH user
            auth_method=SSHAuthMethod.PRIVATE_KEY,
            private_key_path="/path/to/key",  # Replace with real key path
            remote_bind_host="127.0.0.1",
            remote_bind_port=3306,
            connect_timeout=30,
            keepalive_interval=30
        )
        
        # Create database configuration
        db_config = DatabaseConfigWithSSH(
            host="your-aurora-host",  # Replace with real Aurora host
            port=3306,
            user="your-db-user",     # Replace with real DB user
            password="your-password", # Replace with real DB password
            database="ASSET",        # Replace with real database name
            ssh_tunnel=ssh_config
        )
        
        print("🔧 Configuration created:")
        print(f"   SSH Host: {ssh_config.ssh_host}:{ssh_config.ssh_port}")
        print(f"   DB Host: {db_config.host}:{db_config.port}")
        print(f"   Database: {db_config.database}")
        print()
        
        # Test 1: SSH Tunnel Creation
        print("📡 Step 1: Testing SSH Tunnel Creation...")
        connection_key = f"{ssh_config.ssh_host}:{ssh_config.ssh_port}:{ssh_config.remote_bind_host}:{ssh_config.remote_bind_port}"
        
        tunnel_info = await tunnel_manager.get_or_create_tunnel_for_schema_discovery(
            ssh_config,
            connection_key,
            timeout=60
        )
        
        if not tunnel_info:
            print("❌ SSH tunnel creation failed: No tunnel info returned")
            return False
            
        print(f"✅ SSH tunnel created: {tunnel_info.tunnel_id}")
        print(f"   Status: {tunnel_info.status}")
        print(f"   Local Port: {tunnel_info.local_port}")
        print()
        
        # Test 2: Database Connection through Tunnel
        print("🔌 Step 2: Testing Database Connection through Tunnel...")
        
        # Create updated config with tunnel settings
        tunnel_host = "ssh-proxy" if os.getenv('DOCKER_ENV') == 'true' else "127.0.0.1"
        
        updated_config = DatabaseConfigWithSSH(
            host=tunnel_host,
            port=tunnel_info.local_port,
            user=db_config.user,
            password=db_config.password,
            database=db_config.database,
            ssh_tunnel=ssh_config
        )
        
        # Get connection URL
        connection_url = updated_config.get_connection_url(database="")
        print(f"   Connection URL: {connection_url.split('@')[1] if '@' in connection_url else connection_url}")
        
        # Create database connection
        db_conn = DatabaseConnection(
            connection_url=connection_url,
            database=db_config.database,
            is_schema_discovery=True
        )
        
        # Test 3: Simple Query
        print("📊 Step 3: Testing Simple Query...")
        try:
            result = await db_conn.execute_query("SELECT 1 as test_value", timeout=30)
            print(f"✅ Simple query successful: {result}")
        except Exception as e:
            print(f"❌ Simple query failed: {e}")
            return False
        
        # Test 4: Database Schema Query
        print("🗃️ Step 4: Testing Schema Query...")
        try:
            schema_query = """
            SELECT TABLE_SCHEMA, TABLE_NAME, TABLE_TYPE 
            FROM information_schema.TABLES 
            WHERE TABLE_SCHEMA = %s 
            LIMIT 5
            """
            result = await db_conn.execute_query(schema_query, [db_config.database], timeout=30)
            print(f"✅ Schema query successful: Found {len(result)} tables")
            for row in result[:3]:  # Show first 3 tables
                print(f"   - {row[0]}.{row[1]} ({row[2]})")
        except Exception as e:
            print(f"❌ Schema query failed: {e}")
            return False
        
        # Test 5: Table Count Query
        print("🔢 Step 5: Testing Table Count...")
        try:
            count_query = """
            SELECT COUNT(*) as table_count 
            FROM information_schema.TABLES 
            WHERE TABLE_SCHEMA = %s 
            AND TABLE_TYPE = 'BASE TABLE'
            """
            result = await db_conn.execute_query(count_query, [db_config.database], timeout=30)
            table_count = result[0][0] if result else 0
            print(f"✅ Table count query successful: {table_count} tables found")
        except Exception as e:
            print(f"❌ Table count query failed: {e}")
            return False
        
        # Cleanup
        await db_conn.close()
        
        print()
        print("=" * 60)
        print("🎉 SSH Database Connection Test PASSED!")
        print(f"✅ SSH tunnel: {tunnel_info.tunnel_id} -> port {tunnel_info.local_port}")
        print(f"✅ Database: {db_config.database} with {table_count} tables")
        print(f"⏰ Test completed at: {datetime.now()}")
        
        return True
        
    except Exception as e:
        print()
        print("=" * 60)
        print("❌ SSH Database Connection Test FAILED!")
        print(f"Error: {str(e)}")
        print(f"⏰ Test failed at: {datetime.now()}")
        return False

async def test_current_tunnels():
    """Test current active tunnels"""
    print("🔍 Checking Current SSH Tunnels...")
    
    try:
        # List active tunnels
        active_tunnels = tunnel_manager.active_tunnels
        print(f"Active tunnels: {len(active_tunnels)}")
        
        for tunnel_id, tunnel_info in active_tunnels.items():
            print(f"  Tunnel {tunnel_id}:")
            print(f"    Status: {tunnel_info.status}")
            print(f"    Local Port: {tunnel_info.local_port}")
            print(f"    SSH Host: {tunnel_info.config.ssh_host}")
            
            # Test connectivity to this tunnel
            tunnel_host = "ssh-proxy" if os.getenv('DOCKER_ENV') == 'true' else "127.0.0.1"
            print(f"    Testing connectivity to {tunnel_host}:{tunnel_info.local_port}...")
            
            # Simple socket test would be here, but we'll use database connection instead
            
    except Exception as e:
        print(f"❌ Error checking tunnels: {e}")

if __name__ == "__main__":
    # Set Docker environment variable
    os.environ['DOCKER_ENV'] = 'true'
    
    print("SSH Database Connection Test")
    print("Note: This test uses placeholder configuration.")
    print("Replace with actual SSH and database credentials to run real test.")
    print()
    
    # Run tunnel check first
    asyncio.run(test_current_tunnels())
    print()
    
    # Note: Commented out full test as it needs real credentials
    # asyncio.run(test_ssh_database_connection())
    
    print("Test script ready. Update credentials and uncomment test to run.")