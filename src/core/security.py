import os
import hmac
import hashlib
import bcrypt


def newkey(n: int) -> str:
    """Generate a cryptographically secure random key."""
    return os.urandom(n).hex()


def new_sk() -> str:
    """Generate a new secret key."""
    return f"sk-{newkey(32)}"


def new_rk() -> str:
    """Generate a new recovery key."""
    return f"rk-{newkey(48)}"


def new_branch_master_key() -> str:
    """Generate a master key for branch moderation."""
    return f"bmk-{newkey(32)}"


def _prepare_key_for_bcrypt(key: str) -> bytes:
    """
    Prepare a key for bcrypt hashing.
    Bcrypt has a 72 byte limit, so we hash longer keys with SHA256 first.
    """
    key_bytes = key.encode('utf-8')
    if len(key_bytes) > 72:
        # Hash with SHA256 for longer keys
        return hashlib.sha256(key_bytes).hexdigest().encode('utf-8')
    return key_bytes


def hash_key(key: str) -> str:
    """
    Hash a key (secret key or recovery key) using bcrypt.

    Args:
        key: The plain text key to hash

    Returns:
        The bcrypt hash as a string
    """
    salt = bcrypt.gensalt(rounds=12)
    key_bytes = _prepare_key_for_bcrypt(key)
    hashed = bcrypt.hashpw(key_bytes, salt)
    return hashed.decode('utf-8')


def verify_key(plain_key: str, hashed_key: str) -> bool:
    """
    Verify a key against its bcrypt hash using constant-time comparison.

    Args:
        plain_key: The plain text key to verify
        hashed_key: The bcrypt hash to compare against

    Returns:
        True if the key matches, False otherwise
    """
    try:
        key_bytes = _prepare_key_for_bcrypt(plain_key)
        return bcrypt.checkpw(key_bytes, hashed_key.encode('utf-8'))
    except (ValueError, TypeError):
        return False


def constant_time_compare(a: str, b: str) -> bool:
    """
    Perform a constant-time string comparison to prevent timing attacks.
    
    Args:
        a: First string to compare
        b: Second string to compare
        
    Returns:
        True if strings are equal, False otherwise
    """
    return hmac.compare_digest(a.encode('utf-8'), b.encode('utf-8'))


# Legacy aliases for backward compatibility
def hash_master_key(master_key: str) -> str:
    """
    Hash a branch master key using bcrypt.
    
    Args:
        master_key: The plain text master key to hash
        
    Returns:
        The bcrypt hash as a string
    """
    return hash_key(master_key)


def verify_master_key(master_key: str, hashed_key: str) -> bool:
    """
    Verify a master key against its bcrypt hash.
    
    Args:
        master_key: The plain text master key to verify
        hashed_key: The bcrypt hash to compare against
        
    Returns:
        True if the key matches, False otherwise
    """
    return verify_key(master_key, hashed_key)