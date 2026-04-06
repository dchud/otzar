import os
import string
import threading

BASE62_CHARS = string.digits + string.ascii_lowercase + string.ascii_uppercase
_lock = threading.Lock()


def encode_base62(n):
    """Encode an integer as a base62 string."""
    if n == 0:
        return BASE62_CHARS[0]
    result = []
    while n > 0:
        n, remainder = divmod(n, 62)
        result.append(BASE62_CHARS[remainder])
    return "".join(reversed(result))


def get_prefix():
    """Return the configured record ID prefix."""
    return os.environ.get("RECORD_ID_PREFIX", "otzar-")


def generate_record_id(sequence_number):
    """Generate a record ID from a sequence number.

    Uses the configured prefix and base62 encoding.
    Example: sequence 1000 -> "otzar-g8"
    """
    prefix = get_prefix()
    encoded = encode_base62(sequence_number)
    return f"{prefix}{encoded}"
