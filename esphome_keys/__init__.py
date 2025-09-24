"""
Deterministic secret derivation for ESPHome.
- derive_api_key(device_name, master_secret)
- derive_ota_password(device_name, master_secret)
"""

from __future__ import annotations
import base64
import hashlib
import hmac
from typing import Union

BytesLike = Union[str, bytes, bytearray]

def _as_bytes(x: BytesLike) -> bytes:
    if isinstance(x, (bytes, bytearray)):
        return bytes(x)
    return str(x).encode("utf-8")

def _derive(label: str, device_name: str, master_secret: BytesLike) -> bytes:
    """HMAC-SHA256(master_secret, f'{label}:{device_name}')"""
    msg = f"{label}:{device_name}"
    return hmac.new(_as_bytes(master_secret), _as_bytes(msg), hashlib.sha256).digest()

def derive_api_key(device_name: str, master_secret: BytesLike) -> str:
    """
    Returns base64 string suitable for ESPHome api encryption key.
    """
    digest = _derive("api", device_name, master_secret)
    return base64.b64encode(digest).decode("ascii")

def derive_ota_password(device_name: str, master_secret: BytesLike, length: int = 32) -> str:
    """
    Returns a short base64 string for OTA password (default 32 chars).
    """
    digest = _derive("ota", device_name, master_secret)
    b64 = base64.b64encode(digest).decode("ascii")
    return b64[:max(8, length)]  # keep it usable; min reasonable length
