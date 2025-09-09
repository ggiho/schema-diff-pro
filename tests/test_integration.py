"""
Integration tests for SSH tunnel and environment configuration
"""

import os
import sys
import asyncio
import aiohttp
import json
from typing import Dict, Any

# Add backend directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from models.ssh_tunnel import SSHTunnelConfig, SSHAuthMethod


class IntegrationTester:
    """Integration tester for SSH tunnel functionality"""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
    
    async def test_api_health(self) -> Dict[str, Any]:
        """Test API health endpoint"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.base_url}/health") as response:
                    if response.status == 200:
                        data = await response.json()
                        return {"status": "success", "data": data}
                    else:
                        return {"status": "error", "message": f"HTTP {response.status}"}
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    async def test_ssh_status(self) -> Dict[str, Any]:
        """Test SSH system status endpoint"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.base_url}/api/v1/ssh/status") as response:
                    if response.status == 200:
                        data = await response.json()
                        return {"status": "success", "data": data}
                    else:
                        return {"status": "error", "message": f"HTTP {response.status}"}
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    async def test_database_connection(self) -> Dict[str, Any]:
        """Test basic database connection (without SSH)"""
        test_config = {
            "host": "localhost",
            "port": 3306,
            "user": "test",
            "password": "test",
            "database": "test"
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/api/v1/database/test",
                    headers={"Content-Type": "application/json"},
                    data=json.dumps(test_config)
                ) as response:
                    data = await response.json()
                    return {
                        "status": "tested",
                        "http_status": response.status,
                        "response": data
                    }
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    async def test_ssh_tunnel_validation(self) -> Dict[str, Any]:
        """Test SSH tunnel configuration validation"""
        test_ssh_config = {
            "key_path": "/path/to/nonexistent/key",
            "key_content": "invalid_key_content",
            "passphrase": "test"
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/api/v1/ssh/key/validate",
                    headers={"Content-Type": "application/json"},
                    data=json.dumps(test_ssh_config)
                ) as response:
                    data = await response.json()
                    return {
                        "status": "tested",
                        "http_status": response.status,
                        "response": data
                    }
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    async def run_all_tests(self) -> Dict[str, Any]:
        """Run all integration tests"""
        results = {}
        
        print("🔍 Testing API Health...")
        results["health"] = await self.test_api_health()
        print(f"   Health: {results['health']['status']}")
        
        print("🔍 Testing SSH Status...")
        results["ssh_status"] = await self.ssh_status()
        print(f"   SSH Status: {results['ssh_status']['status']}")
        
        print("🔍 Testing Database Connection...")
        results["database"] = await self.test_database_connection()
        print(f"   Database: {results['database']['status']}")
        
        print("🔍 Testing SSH Key Validation...")
        results["ssh_validation"] = await self.test_ssh_tunnel_validation()
        print(f"   SSH Validation: {results['ssh_validation']['status']}")
        
        return results


def test_environment_variables():
    """Test environment variable configuration"""
    print("🔧 Testing Environment Variables...")
    
    docker_env = os.getenv('DOCKER_ENV')
    print(f"   DOCKER_ENV: {docker_env}")
    
    # Test that we can determine the environment correctly
    is_docker = docker_env == 'true'
    print(f"   Running in Docker: {is_docker}")
    
    if is_docker:
        print("   ✅ Docker environment detected")
        expected_api_url = "http://backend:8000"
    else:
        print("   ✅ Local environment detected")
        expected_api_url = "http://localhost:8000"
    
    print(f"   Expected API URL: {expected_api_url}")
    return {"is_docker": is_docker, "api_url": expected_api_url}


async def main():
    """Main test runner"""
    print("🚀 Starting Integration Tests...")
    print("=" * 50)
    
    # Test environment variables
    env_results = test_environment_variables()
    print()
    
    # Determine API URL based on environment
    api_url = env_results["api_url"]
    tester = IntegrationTester(api_url)
    
    # Run integration tests
    print(f"🌐 Testing API at: {api_url}")
    test_results = await tester.run_all_tests()
    
    print()
    print("📊 Test Summary:")
    print("=" * 50)
    
    for test_name, result in test_results.items():
        status = result.get("status", "unknown")
        if status == "success":
            print(f"   ✅ {test_name}: PASSED")
        elif status == "tested":
            print(f"   ⚠️  {test_name}: TESTED (check response)")
        else:
            print(f"   ❌ {test_name}: FAILED - {result.get('message', 'Unknown error')}")
    
    print()
    print("🎯 Integration Test Complete!")
    return test_results


if __name__ == "__main__":
    asyncio.run(main())