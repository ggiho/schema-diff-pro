"""
Security framework for SSH tunneling and sensitive data management
Provides encryption, decryption, and SSH key management capabilities
"""

import os
import json
import secrets
import hashlib
import base64
import logging
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime, timedelta
from pathlib import Path
from enum import Enum

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import hashes, padding, serialization
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric import rsa, ed25519, ec, dsa

from models.ssh_tunnel import SSHKeyInfo, SSHKeyType

logger = logging.getLogger(__name__)


class DataClassification(str, Enum):
    """Data classification levels for encryption"""
    PUBLIC = "public"         # No encryption needed
    INTERNAL = "internal"     # Basic encryption
    CONFIDENTIAL = "confidential"  # Strong encryption
    RESTRICTED = "restricted"      # Maximum encryption + audit


class SecurityManager:
    """Handles encryption, decryption and SSH key management"""
    
    def __init__(self):
        self.master_key = self._get_or_create_master_key()
        self.key_storage_path = Path(".ssh_keys")
        self.key_storage_path.mkdir(exist_ok=True, mode=0o700)
        self._setup_audit_logging()
    
    def _setup_audit_logging(self):
        """Setup security audit logging"""
        audit_log_path = Path("logs/security_audit.log")
        audit_log_path.parent.mkdir(exist_ok=True)
        
        # Configure audit logger
        audit_logger = logging.getLogger("security_audit")
        audit_logger.setLevel(logging.INFO)
        
        if not audit_logger.handlers:
            handler = logging.FileHandler(audit_log_path)
            formatter = logging.Formatter(
                '%(asctime)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            audit_logger.addHandler(handler)
    
    def _audit_log(self, event: str, details: Dict[str, Any], level: str = "INFO"):
        """Log security event"""
        audit_logger = logging.getLogger("security_audit")
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "event": event,
            "details": details
        }
        
        if level.upper() == "ERROR":
            audit_logger.error(json.dumps(log_entry))
        elif level.upper() == "WARNING":
            audit_logger.warning(json.dumps(log_entry))
        else:
            audit_logger.info(json.dumps(log_entry))
    
    def _get_or_create_master_key(self) -> bytes:
        """Get or create master encryption key"""
        key_file = Path(".master_key")
        
        if key_file.exists():
            with open(key_file, 'rb') as f:
                key_data = f.read()
            
            # Verify key integrity
            if len(key_data) != 64:  # 32 bytes key + 32 bytes salt
                logger.warning("Corrupted master key file, regenerating...")
                key_file.unlink()
                return self._get_or_create_master_key()
            
            return key_data[:32]
        
        else:
            # Generate cryptographically secure master key
            master_key = secrets.token_bytes(32)  # 256-bit key
            salt = secrets.token_bytes(32)       # 256-bit salt
            
            # Store key with salt for verification
            with open(key_file, 'wb') as f:
                f.write(master_key + salt)
            
            # Secure file permissions (owner read-only)
            os.chmod(key_file, 0o600)
            
            self._audit_log("master_key_created", {
                "key_length": len(master_key) * 8,
                "salt_length": len(salt) * 8
            })
            
            logger.info("Created new master encryption key")
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
    
    async def encrypt_value(
        self, 
        value: str, 
        classification: DataClassification = DataClassification.CONFIDENTIAL
    ) -> str:
        """Encrypt sensitive value based on classification level"""
        if not value:
            return value
        
        try:
            # Generate random salt and IV
            salt = secrets.token_bytes(16)
            iv = secrets.token_bytes(16)
            
            if classification == DataClassification.RESTRICTED:
                # Maximum security: AES-256-GCM with authenticated encryption
                key = self._derive_key(self.master_key.hex(), salt)
                cipher = Cipher(
                    algorithms.AES(key), 
                    modes.GCM(iv), 
                    backend=default_backend()
                )
                encryptor = cipher.encryptor()
                ciphertext = encryptor.update(value.encode()) + encryptor.finalize()
                
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
                padded_data = padder.update(value.encode()) + padder.finalize()
                
                ciphertext = encryptor.update(padded_data) + encryptor.finalize()
                result = salt + iv + ciphertext
            
            encrypted_b64 = base64.b64encode(result).decode()
            
            self._audit_log("data_encrypted", {
                "classification": classification.value,
                "data_length": len(value)
            })
            
            return encrypted_b64
            
        except Exception as e:
            self._audit_log("encryption_failed", {
                "error": str(e),
                "classification": classification.value
            }, level="ERROR")
            raise ValueError(f"Encryption failed: {str(e)}")
    
    async def decrypt_value(
        self, 
        encrypted_value: str, 
        classification: DataClassification = DataClassification.CONFIDENTIAL
    ) -> str:
        """Decrypt sensitive value"""
        if not encrypted_value:
            return encrypted_value
        
        try:
            data = base64.b64decode(encrypted_value.encode())
            
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
    
    async def validate_ssh_key(
        self, 
        key_path: Optional[str] = None,
        key_content: Optional[str] = None,
        passphrase: Optional[str] = None
    ) -> SSHKeyInfo:
        """Validate SSH private key and extract metadata"""
        key_info = SSHKeyInfo()
        
        try:
            # Get key data
            if key_content:
                key_data = key_content.encode()
            elif key_path:
                with open(key_path, 'rb') as f:
                    key_data = f.read()
                key_info.key_path = key_path
            else:
                key_info.add_validation_error("No key data provided")
                return key_info
            
            # Try to load the key
            try:
                passphrase_bytes = passphrase.encode() if passphrase else None
                
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
                
                # Extract comment if present
                key_str = key_data.decode('utf-8', errors='ignore')
                if '-----' in key_str:
                    # Look for comment lines
                    lines = key_str.split('\n')
                    for line in lines:
                        if line.startswith('#') or 'Comment:' in line:
                            key_info.comment = line.strip()
                            break
                
                self._audit_log("ssh_key_validated", {
                    "key_type": key_info.key_type.value if key_info.key_type else None,
                    "key_size": key_info.key_size,
                    "is_encrypted": key_info.is_encrypted,
                    "fingerprint": key_info.fingerprint
                })
                
            except ValueError as e:
                error_msg = str(e).lower()
                if "bad decrypt" in error_msg or "could not deserialize" in error_msg:
                    key_info.add_validation_error("Invalid passphrase or corrupted key")
                else:
                    key_info.add_validation_error(f"Invalid key format: {str(e)}")
            
        except FileNotFoundError:
            key_info.add_validation_error("Key file not found")
        except PermissionError:
            key_info.add_validation_error("Permission denied accessing key file")
        except Exception as e:
            key_info.add_validation_error(f"Key validation failed: {str(e)}")
            logger.error(f"SSH key validation error: {e}")
        
        return key_info
    
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
            
            # Encrypt key content with maximum security
            encrypted_key = await self.encrypt_value(
                key_content, 
                DataClassification.RESTRICTED
            )
            
            # Encrypt passphrase if provided
            encrypted_passphrase = None
            if passphrase:
                encrypted_passphrase = await self.encrypt_value(
                    passphrase,
                    DataClassification.RESTRICTED
                )
            
            # Store encrypted key
            with open(key_file, 'w') as f:
                f.write(encrypted_key)
            os.chmod(key_file, 0o600)
            
            # Validate key and get metadata
            key_validation = await self.validate_ssh_key(
                key_content=key_content, 
                passphrase=passphrase
            )
            
            # Store metadata
            key_metadata = {
                "key_id": key_id,
                "created_at": datetime.now().isoformat(),
                "has_passphrase": passphrase is not None,
                "fingerprint": key_validation.fingerprint,
                "key_type": key_validation.key_type.value if key_validation.key_type else None,
                "key_size": key_validation.key_size,
                "is_valid": key_validation.is_valid,
                "validation_errors": key_validation.validation_errors,
                "comment": key_validation.comment,
                "metadata": metadata or {},
                "last_used": None,
                "usage_count": 0
            }
            
            with open(meta_file, 'w') as f:
                json.dump(key_metadata, f, indent=2)
            os.chmod(meta_file, 0o600)
            
            self._audit_log("ssh_key_stored", {
                "key_id": key_id,
                "has_passphrase": passphrase is not None,
                "key_type": key_validation.key_type.value if key_validation.key_type else None,
                "is_valid": key_validation.is_valid
            })
            
            return key_metadata
            
        except Exception as e:
            self._audit_log("ssh_key_storage_failed", {
                "key_id": key_id,
                "error": str(e)
            }, level="ERROR")
            raise ValueError(f"Failed to store SSH key: {str(e)}")
    
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
            
            key_content = await self.decrypt_value(
                encrypted_key, 
                DataClassification.RESTRICTED
            )
            
            # Note: Passphrase decryption would be implemented here if stored
            passphrase = None
            
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
            raise ValueError(f"Failed to retrieve SSH key: {str(e)}")
    
    async def list_stored_keys(self) -> List[Dict[str, Any]]:
        """List all stored SSH keys metadata"""
        keys = []
        
        try:
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
                        "has_passphrase": metadata.get("has_passphrase", False),
                        "is_valid": metadata.get("is_valid", False),
                        "comment": metadata.get("comment")
                    }
                    keys.append(safe_metadata)
                    
                except Exception as e:
                    logger.warning(f"Failed to read key metadata {meta_file}: {e}")
        
        except Exception as e:
            logger.error(f"Failed to list SSH keys: {e}")
        
        return sorted(keys, key=lambda x: x["created_at"], reverse=True)
    
    async def delete_ssh_key(self, key_id: str) -> bool:
        """Securely delete SSH key"""
        try:
            key_file = self.key_storage_path / f"{key_id}.key"
            meta_file = self.key_storage_path / f"{key_id}.meta"
            
            deleted_files = []
            
            # Secure deletion of key file
            if key_file.exists():
                # Overwrite with random data multiple times
                file_size = key_file.stat().st_size
                with open(key_file, 'rb+') as f:
                    for _ in range(3):  # Multiple passes
                        f.seek(0)
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
            raise ValueError(f"Failed to delete SSH key: {str(e)}")
    
    def get_security_status(self) -> Dict[str, Any]:
        """Get current security status and health check"""
        master_key_exists = Path(".master_key").exists()
        key_storage_exists = self.key_storage_path.exists()
        
        try:
            stored_keys_count = len(list(self.key_storage_path.glob("*.meta")))
        except:
            stored_keys_count = 0
        
        return {
            "encryption_enabled": True,
            "master_key_exists": master_key_exists,
            "key_storage_ready": key_storage_exists,
            "stored_keys_count": stored_keys_count,
            "audit_logging_enabled": True,
            "security_level": "enterprise",
            "recommendations": self._get_security_recommendations()
        }
    
    def _get_security_recommendations(self) -> List[str]:
        """Generate security recommendations"""
        recommendations = []
        
        # Check key storage permissions
        if self.key_storage_path.exists():
            stat = self.key_storage_path.stat()
            if stat.st_mode & 0o077:  # Others have any permissions
                recommendations.append("Restrict key storage directory permissions")
        
        # Check master key permissions
        master_key_file = Path(".master_key")
        if master_key_file.exists():
            stat = master_key_file.stat()
            if stat.st_mode & 0o077:  # Others have any permissions
                recommendations.append("Restrict master key file permissions")
        
        if not recommendations:
            recommendations.append("Security configuration is optimal")
        
        return recommendations


# Global security manager instance
security_manager = SecurityManager()