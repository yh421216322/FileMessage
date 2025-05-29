"""
Manages PIN hashing and verification for the LAN File Sharer application.
"""
import hashlib
import logging

logger = logging.getLogger(__name__)

def hash_pin(pin: str) -> str:
    """
    Hashes a 4-digit PIN using SHA256.

    Args:
        pin: The 4-digit PIN string to hash.

    Returns:
        The hexadecimal representation of the hashed PIN.

    Raises:
        ValueError: If the PIN is not a 4-digit string.
    """
    if not isinstance(pin, str) or not pin.isdigit() or len(pin) != 4:
        err_msg = "PIN must be a 4-digit string."
        logger.error(f"hash_pin validation error: {err_msg} (Received: '{pin}')")
        raise ValueError(err_msg)
    
    pin_bytes = pin.encode('utf-8')
    hashed_pin = hashlib.sha256(pin_bytes).hexdigest()
    return hashed_pin

def verify_pin(hashed_pin: str, pin_attempt: str) -> bool:
    """
    Verifies a PIN attempt against a stored hashed PIN.

    Args:
        hashed_pin: The stored hashed PIN.
        pin_attempt: The 4-digit PIN attempt string.

    Returns:
        True if the PIN attempt matches the stored hash, False otherwise.
        
    Raises:
        ValueError: If the pin_attempt is not a 4-digit string.
    """
    if not isinstance(pin_attempt, str) or not pin_attempt.isdigit() or len(pin_attempt) != 4:
        err_msg = "PIN attempt must be a 4-digit string."
        logger.error(f"verify_pin validation error: {err_msg} (Received: '{pin_attempt}')")
        raise ValueError(err_msg)
        
    attempt_hashed = hash_pin(pin_attempt) # hash_pin already logs its own errors if any
    return attempt_hashed == hashed_pin
