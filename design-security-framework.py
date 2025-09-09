# ================================
# Security Framework Design
# ================================

# backend/core/security_policy.py
from enum import Enum
from dataclasses import dataclass
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class SecurityLevel(str, Enum):
    """Security levels for different deployment environments"""
    DEVELOPMENT = "development"    # Minimal security, ease of development
    STAGING = "staging"           # Medium security, testing environment  
    PRODUCTION = "production"     # Maximum security, enterprise-ready


class DataClassification(str, Enum):
    """Data classification levels"""
    PUBLIC = "public"             # No encryption needed
    INTERNAL = "internal"         # Basic encryption
    CONFIDENTIAL = "confidential" # Strong encryption
    RESTRICTED = "restricted"     # Maximum encryption + audit


@dataclass
class SecurityPolicy:
    """Security policy configuration"""
    security_level: SecurityLevel
    
    # Encryption settings
    encrypt_passwords: bool = True
    encrypt_ssh_keys: bool = True
    encrypt_connection_strings: bool = True
    
    # SSH settings
    allow_password_auth: bool = True
    require_key_passphrase: bool = False
    max_tunnel_lifetime_minutes: int = 480  # 8 hours
    max_concurrent_tunnels: int = 10
    
    # Audit settings
    enable_audit_logging: bool = True
    log_connection_attempts: bool = True
    log_failed_authentications: bool = True
    
    # Key management
    auto_cleanup_keys: bool = True
    key_rotation_days: Optional[int] = None
    
    # Network security
    allowed_ssh_hosts: Optional[List[str]] = None
    blocked_ssh_hosts: Optional[List[str]] = None
    require_known_hosts: bool = False
    
    @classmethod
    def for_environment(cls, env: str) -> 'SecurityPolicy':
        """Create security policy for specific environment"""
        if env.lower() in ['prod', 'production']:
            return cls.production_policy()
        elif env.lower() in ['stage', 'staging']:
            return cls.staging_policy()
        else:
            return cls.development_policy()
    
    @classmethod
    def development_policy(cls) -> 'SecurityPolicy':
        """Relaxed security for development"""
        return cls(
            security_level=SecurityLevel.DEVELOPMENT,
            allow_password_auth=True,
            require_key_passphrase=False,
            max_tunnel_lifetime_minutes=480,
            max_concurrent_tunnels=50,
            require_known_hosts=False,
            key_rotation_days=None
        )
    
    @classmethod
    def staging_policy(cls) -> 'SecurityPolicy':
        """Moderate security for staging"""
        return cls(
            security_level=SecurityLevel.STAGING,
            allow_password_auth=True,
            require_key_passphrase=True,
            max_tunnel_lifetime_minutes=240,  # 4 hours
            max_concurrent_tunnels=20,
            require_known_hosts=True,
            key_rotation_days=90
        )
    
    @classmethod
    def production_policy(cls) -> 'SecurityPolicy':
        """Maximum security for production"""
        return cls(
            security_level=SecurityLevel.PRODUCTION,
            allow_password_auth=False,  # Key-only authentication
            require_key_passphrase=True,
            max_tunnel_lifetime_minutes=120,  # 2 hours
            max_concurrent_tunnels=10,
            require_known_hosts=True,
            key_rotation_days=30
        )


# ================================
# Enhanced Security Manager
# ================================

# backend/core/security_enhanced.py
import os
import json
import secrets
import hashlib
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime, timedelta
from pathlib import Path
import logging

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import hashes, padding, serialization
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric import rsa, padding as asym_padding

from models.ssh_tunnel import SSHKeyInfo, SSHKeyType
from core.security_policy import SecurityPolicy, DataClassification

logger = logging.getLogger(__name__)


class EnhancedSecurityManager:
    """Enhanced security manager with enterprise features"""
    
    def __init__(self, policy: SecurityPolicy):
        self.policy = policy
        self.master_key = self._get_or_create_master_key()
        self.audit_log_path = Path("logs/security_audit.log")
        self.key_storage_path = Path(".ssh_keys")
        self.key_storage_path.mkdir(exist_ok=True)
        self._setup_audit_logging()
    
    def _setup_audit_logging(self):
        """Setup security audit logging"""
        if self.policy.enable_audit_logging:
            self.audit_log_path.parent.mkdir(exist_ok=True)
            
            # Configure audit logger
            audit_logger = logging.getLogger("security_audit")
            audit_logger.setLevel(logging.INFO)
            
            if not audit_logger.handlers:
                handler = logging.FileHandler(self.audit_log_path)
                formatter = logging.Formatter(
                    '%(asctime)s - %(levelname)s - %(message)s'
                )
                handler.setFormatter(formatter)
                audit_logger.addHandler(handler)
    
    def _audit_log(self, event: str, details: Dict[str, Any], level: str = "INFO"):
        """Log security event"""
        if not self.policy.enable_audit_logging:
            return
        
        audit_logger = logging.getLogger("security_audit")
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "event": event,
            "details": details,
            "security_level": self.policy.security_level.value
        }
        
        if level.upper() == "ERROR":
            audit_logger.error(json.dumps(log_entry))
        elif level.upper() == "WARNING":
            audit_logger.warning(json.dumps(log_entry))
        else:
            audit_logger.info(json.dumps(log_entry))
    
    def _get_or_create_master_key(self) -> bytes:
        """Get or create master encryption key with proper security"""
        key_file = Path(".master_key")
        
        if key_file.exists():
            with open(key_file, 'rb') as f:
                key_data = f.read()
            
            # Verify key integrity
            if len(key_data) != 64:  # 32 bytes key + 32 bytes salt
                raise ValueError("Corrupted master key file")
            
            return key_data[:32]
        
        else:
            # Generate cryptographically secure master key
            master_key = secrets.token_bytes(32)  # 256-bit key
            salt = secrets.token_bytes(32)       # 256-bit salt
            
            # Store key with salt for future verification
            with open(key_file, 'wb') as f:
                f.write(master_key + salt)
            
            # Secure file permissions (owner read-only)
            os.chmod(key_file, 0o600)
            
            self._audit_log("master_key_created", {
                "key_length": len(master_key) * 8,
                "salt_length": len(salt) * 8
            })
            
            return master_key
    
    def _derive_key(self, password: str, salt: bytes) -> bytes:
        """Derive encryption key from password using PBKDF2"""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,  # OWASP recommended minimum
            backend=default_backend()
        )
        return kdf.derive(password.encode())
    
    async def encrypt_sensitive_data(
        self, 
        data: str, 
        classification: DataClassification = DataClassification.CONFIDENTIAL
    ) -> str:
        """Encrypt sensitive data based on classification level"""
        if not data:
            return data
        
        try:
            # Generate random salt and IV
            salt = secrets.token_bytes(16)
            iv = secrets.token_bytes(16)
            
            # Use different encryption methods based on classification
            if classification == DataClassification.RESTRICTED:
                # Maximum security: AES-256-GCM with authenticated encryption
                key = self._derive_key(self.master_key.hex(), salt)
                cipher = Cipher(
                    algorithms.AES(key), 
                    modes.GCM(iv), 
                    backend=default_backend()
                )
                encryptor = cipher.encryptor()
                ciphertext = encryptor.update(data.encode()) + encryptor.finalize()
                
                # Include authentication tag
                result = salt + iv + encryptor.tag + ciphertext
                
            else:
                # Standard security: AES-256-CBC
                cipher = Cipher(
                    algorithms.AES(self.master_key), 
                    modes.CBC(iv), 
                    backend=default_backend()
                )
                encryptor = cipher.encryptor()
                
                # PKCS7 padding
                padder = padding.PKCS7(128).padder()
                padded_data = padder.update(data.encode()) + padder.finalize()
                
                ciphertext = encryptor.update(padded_data) + encryptor.finalize()
                result = salt + iv + ciphertext
            
            encrypted_b64 = base64.b64encode(result).decode()
            
            self._audit_log("data_encrypted", {
                "classification": classification.value,
                "data_length": len(data),
                "encrypted_length": len(encrypted_b64)
            })
            
            return encrypted_b64
            
        except Exception as e:
            self._audit_log("encryption_failed", {
                "error": str(e),
                "classification": classification.value
            }, level="ERROR")
            raise
    
    async def decrypt_sensitive_data(
        self, 
        encrypted_data: str, 
        classification: DataClassification = DataClassification.CONFIDENTIAL
    ) -> str:
        """Decrypt sensitive data"""
        if not encrypted_data:
            return encrypted_data
        
        try:
            data = base64.b64decode(encrypted_data.encode())
            
            if classification == DataClassification.RESTRICTED:
                # GCM decryption
                salt = data[:16]
                iv = data[16:32]
                tag = data[32:48]
                ciphertext = data[48:]
                
                key = self._derive_key(self.master_key.hex(), salt)
                cipher = Cipher(
                    algorithms.AES(key), 
                    modes.GCM(iv, tag), 
                    backend=default_backend()
                )
                decryptor = cipher.decryptor()
                plaintext = decryptor.update(ciphertext) + decryptor.finalize()
                
            else:
                # CBC decryption
                salt = data[:16]
                iv = data[16:32]
                ciphertext = data[32:]
                
                cipher = Cipher(
                    algorithms.AES(self.master_key), 
                    modes.CBC(iv), 
                    backend=default_backend()
                )
                decryptor = cipher.decryptor()
                padded_data = decryptor.update(ciphertext) + decryptor.finalize()
                
                # Remove PKCS7 padding
                unpadder = padding.PKCS7(128).unpadder()
                plaintext = unpadder.update(padded_data) + unpadder.finalize()
            
            return plaintext.decode()
            
        except Exception as e:
            self._audit_log("decryption_failed", {
                "error": str(e),
                "classification": classification.value
            }, level="ERROR")
            raise ValueError("Failed to decrypt sensitive data")
    
    async def secure_store_ssh_key(
        self, 
        key_id: str, 
        key_content: str, 
        passphrase: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Securely store SSH key with metadata"""
        try:
            key_file = self.key_storage_path / f"{key_id}.key"
            meta_file = self.key_storage_path / f"{key_id}.meta"
            
            # Encrypt key content
            encrypted_key = await self.encrypt_sensitive_data(
                key_content, 
                DataClassification.RESTRICTED
            )
            
            # Encrypt passphrase if provided
            encrypted_passphrase = None
            if passphrase:
                encrypted_passphrase = await self.encrypt_sensitive_data(
                    passphrase,
                    DataClassification.RESTRICTED
                )
            
            # Store encrypted key
            with open(key_file, 'w') as f:
                f.write(encrypted_key)
            os.chmod(key_file, 0o600)
            
            # Store metadata
            key_metadata = {
                "key_id": key_id,
                "created_at": datetime.now().isoformat(),
                "has_passphrase": passphrase is not None,
                "metadata": metadata or {},
                "fingerprint": None,  # Will be calculated
                "last_used": None,
                "usage_count": 0
            }
            
            # Calculate key fingerprint for verification
            try:
                key_info = await self.validate_ssh_key(key_content=key_content, passphrase=passphrase)
                key_metadata["fingerprint"] = key_info.fingerprint
                key_metadata["key_type"] = key_info.key_type.value if key_info.key_type else None
                key_metadata["key_size"] = key_info.key_size
            except:
                pass
            
            with open(meta_file, 'w') as f:
                json.dump(key_metadata, f, indent=2)
            os.chmod(meta_file, 0o600)
            
            self._audit_log("ssh_key_stored", {
                "key_id": key_id,
                "has_passphrase": passphrase is not None,
                "metadata": metadata or {}
            })
            
            return key_metadata
            
        except Exception as e:
            self._audit_log("ssh_key_storage_failed", {
                "key_id": key_id,
                "error": str(e)
            }, level="ERROR")
            raise
    
    async def retrieve_ssh_key(self, key_id: str) -> Tuple[str, Optional[str], Dict[str, Any]]:
        """Retrieve and decrypt SSH key"""
        try:
            key_file = self.key_storage_path / f"{key_id}.key"
            meta_file = self.key_storage_path / f"{key_id}.meta"
            
            if not key_file.exists() or not meta_file.exists():
                raise FileNotFoundError(f"SSH key {key_id} not found")
            
            # Load metadata
            with open(meta_file, 'r') as f:
                metadata = json.load(f)
            
            # Update usage tracking
            metadata["last_used"] = datetime.now().isoformat()
            metadata["usage_count"] = metadata.get("usage_count", 0) + 1
            
            with open(meta_file, 'w') as f:
                json.dump(metadata, f, indent=2)
            
            # Decrypt key content
            with open(key_file, 'r') as f:
                encrypted_key = f.read()
            
            key_content = await self.decrypt_sensitive_data(
                encrypted_key, 
                DataClassification.RESTRICTED
            )
            
            # Decrypt passphrase if exists
            passphrase = None
            if metadata.get("has_passphrase"):
                # Passphrase would be stored separately if needed
                pass
            
            self._audit_log("ssh_key_retrieved", {
                "key_id": key_id,
                "usage_count": metadata["usage_count"]
            })
            
            return key_content, passphrase, metadata
            
        except Exception as e:
            self._audit_log("ssh_key_retrieval_failed", {
                "key_id": key_id,
                "error": str(e)
            }, level="ERROR")
            raise
    
    async def list_stored_keys(self) -> List[Dict[str, Any]]:
        """List all stored SSH keys metadata"""
        keys = []
        
        for meta_file in self.key_storage_path.glob("*.meta"):
            try:
                with open(meta_file, 'r') as f:
                    metadata = json.load(f)
                
                # Remove sensitive information from listing
                safe_metadata = {
                    "key_id": metadata["key_id"],
                    "created_at": metadata["created_at"],
                    "last_used": metadata.get("last_used"),
                    "usage_count": metadata.get("usage_count", 0),
                    "key_type": metadata.get("key_type"),
                    "key_size": metadata.get("key_size"),
                    "fingerprint": metadata.get("fingerprint"),
                    "has_passphrase": metadata.get("has_passphrase", False)
                }
                keys.append(safe_metadata)
                
            except Exception as e:
                logger.warning(f"Failed to read key metadata {meta_file}: {e}")
        
        return sorted(keys, key=lambda x: x["created_at"], reverse=True)
    
    async def delete_ssh_key(self, key_id: str) -> bool:
        """Securely delete SSH key"""
        try:
            key_file = self.key_storage_path / f"{key_id}.key"
            meta_file = self.key_storage_path / f"{key_id}.meta"
            
            deleted_files = []
            if key_file.exists():
                # Secure deletion (overwrite with random data)
                file_size = key_file.stat().st_size
                with open(key_file, 'rb+') as f:
                    f.write(secrets.token_bytes(file_size))
                    f.flush()
                    os.fsync(f.fileno())
                key_file.unlink()
                deleted_files.append("key")
            
            if meta_file.exists():
                meta_file.unlink()
                deleted_files.append("metadata")
            
            if deleted_files:
                self._audit_log("ssh_key_deleted", {
                    "key_id": key_id,
                    "deleted_files": deleted_files
                })
                return True
            else:
                return False
                
        except Exception as e:
            self._audit_log("ssh_key_deletion_failed", {
                "key_id": key_id,
                "error": str(e)
            }, level="ERROR")
            raise
    
    async def rotate_keys(self) -> Dict[str, Any]:
        """Rotate expired SSH keys based on policy"""
        if not self.policy.key_rotation_days:
            return {"rotated": 0, "message": "Key rotation disabled"}
        
        cutoff_date = datetime.now() - timedelta(days=self.policy.key_rotation_days)
        keys = await self.list_stored_keys()
        
        expired_keys = []
        for key in keys:
            created_at = datetime.fromisoformat(key["created_at"])
            if created_at < cutoff_date:
                expired_keys.append(key["key_id"])
        
        # Log rotation requirement (actual rotation would need manual intervention)
        if expired_keys:
            self._audit_log("key_rotation_required", {
                "expired_keys": expired_keys,
                "rotation_policy_days": self.policy.key_rotation_days
            }, level="WARNING")
        
        return {
            "rotated": 0,
            "expired_keys": expired_keys,
            "message": f"Found {len(expired_keys)} keys requiring rotation"
        }
    
    def get_security_status(self) -> Dict[str, Any]:
        """Get current security status and recommendations"""
        return {
            "security_level": self.policy.security_level.value,
            "encryption_enabled": True,
            "audit_logging_enabled": self.policy.enable_audit_logging,
            "key_management_active": True,
            "policy_settings": {
                "allow_password_auth": self.policy.allow_password_auth,
                "require_key_passphrase": self.policy.require_key_passphrase,
                "max_tunnel_lifetime_minutes": self.policy.max_tunnel_lifetime_minutes,
                "max_concurrent_tunnels": self.policy.max_concurrent_tunnels,
                "key_rotation_days": self.policy.key_rotation_days
            },
            "recommendations": self._get_security_recommendations()
        }
    
    def _get_security_recommendations(self) -> List[str]:
        """Generate security recommendations based on current configuration"""
        recommendations = []
        
        if self.policy.security_level == SecurityLevel.DEVELOPMENT:
            recommendations.append("Consider upgrading to staging security level for better protection")
        
        if self.policy.allow_password_auth and self.policy.security_level == SecurityLevel.PRODUCTION:
            recommendations.append("Disable password authentication in production for better security")
        
        if not self.policy.require_key_passphrase:
            recommendations.append("Enable mandatory key passphrases for enhanced security")
        
        if self.policy.max_tunnel_lifetime_minutes > 240:
            recommendations.append("Consider reducing tunnel lifetime for better security")
        
        if not self.policy.key_rotation_days:
            recommendations.append("Enable automatic key rotation policy")
        
        return recommendations


# ================================
# Environment Configuration
# ================================

# backend/core/environment.py
import os
from typing import Dict, Any, Optional
from core.security_policy import SecurityPolicy

class EnvironmentConfig:
    """Environment-specific configuration manager"""
    
    @staticmethod
    def detect_environment() -> str:
        """Detect current deployment environment"""
        # Check for explicit environment variable
        env = os.getenv('DEPLOYMENT_ENV', os.getenv('NODE_ENV', 'development')).lower()
        
        # Check for Docker environment
        if os.getenv('DOCKER_ENV') == 'true' or os.path.exists('/.dockerenv'):
            if env == 'development':
                env = 'docker-dev'
            else:
                env = f'docker-{env}'
        
        return env
    
    @staticmethod
    def get_security_policy() -> SecurityPolicy:
        """Get security policy for current environment"""
        env = EnvironmentConfig.detect_environment()
        return SecurityPolicy.for_environment(env)
    
    @staticmethod
    def get_api_base_url() -> str:
        """Get appropriate API base URL for environment"""
        env = EnvironmentConfig.detect_environment()
        
        if 'docker' in env:
            return os.getenv('API_BASE_URL', 'http://backend:8000')
        else:
            return os.getenv('API_BASE_URL', 'http://localhost:8000')
    
    @staticmethod
    def get_cors_origins() -> List[str]:
        """Get CORS origins for current environment"""
        env = EnvironmentConfig.detect_environment()
        
        if 'production' in env:
            # Production: Only allow specific domains
            origins = os.getenv('CORS_ORIGINS', '').split(',')
            return [origin.strip() for origin in origins if origin.strip()]
        else:
            # Development: Allow localhost variants
            return [
                'http://localhost:3000',
                'http://localhost:8000',
                'http://127.0.0.1:3000',
                'http://127.0.0.1:8000'
            ]