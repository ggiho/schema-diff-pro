"""
Constants for the Schema Diff Pro backend.
Guido says: "Explicit is better than implicit."
"""

from typing import Tuple, FrozenSet


# ============================================================================
# Connection Error Patterns
# ============================================================================
# Used for retry logic - these errors indicate transient connection issues
# that may be resolved by retrying

CONNECTION_ERROR_PATTERNS: Tuple[str, ...] = (
    "lost connection to mysql server",
    "mysql server has gone away",
    "connection timeout",
    "broken pipe",
    "connection refused",
    "connection reset",
    "network is unreachable",
    "no route to host",
    "connection timed out",
)


def is_connection_error(error_message: str) -> bool:
    """
    Check if an error message indicates a connection-related issue.
    
    Args:
        error_message: The error message to check
        
    Returns:
        True if the error appears to be connection-related
    """
    error_lower = error_message.lower()
    return any(pattern in error_lower for pattern in CONNECTION_ERROR_PATTERNS)


# ============================================================================
# Critical Failure Patterns
# ============================================================================
# These errors indicate fundamental failures that should stop the comparison

CRITICAL_FAILURE_PATTERNS: Tuple[str, ...] = (
    "failed to discover any table data",
    "both chunked and fallback discovery failed",
    "database may be unreachable",
    "access denied",
    "unknown database",
)


def is_critical_failure(error_message: str) -> bool:
    """
    Check if an error message indicates a critical failure that should stop processing.
    
    Args:
        error_message: The error message to check
        
    Returns:
        True if the error is critical and processing should stop
    """
    error_lower = error_message.lower()
    return any(pattern in error_lower for pattern in CRITICAL_FAILURE_PATTERNS)


# ============================================================================
# Retry Configuration
# ============================================================================

DEFAULT_MAX_RETRIES: int = 3
DEFAULT_RETRY_DELAY_SECONDS: int = 2
MAX_RETRY_DELAY_SECONDS: int = 30


def calculate_retry_delay(attempt: int, base_delay: int = DEFAULT_RETRY_DELAY_SECONDS) -> int:
    """
    Calculate retry delay with exponential backoff.
    
    Args:
        attempt: Current attempt number (0-indexed)
        base_delay: Base delay in seconds
        
    Returns:
        Delay in seconds (capped at MAX_RETRY_DELAY_SECONDS)
    """
    delay = base_delay * (2 ** attempt)
    return min(delay, MAX_RETRY_DELAY_SECONDS)


# ============================================================================
# SSH Tunnel Configuration
# ============================================================================

SSH_TUNNEL_DEFAULT_TIMEOUT: int = 120
SSH_TUNNEL_DEFAULT_PORT_RANGE_START: int = 10000
SSH_TUNNEL_DEFAULT_PORT_RANGE_SIZE: int = 1000


# ============================================================================
# Batch Processing Configuration
# ============================================================================

# Batch sizes for different scenarios
BATCH_SIZE_SSH_TUNNEL: int = 2  # Ultra-small batches for SSH tunnel stability
BATCH_SIZE_LOCAL: int = 5      # Larger batches for local/direct connections
BATCH_SIZE_DEFAULT: int = 5
