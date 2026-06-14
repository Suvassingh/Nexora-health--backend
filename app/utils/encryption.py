
import os
from cryptography.fernet import Fernet

ENCRYPTION_KEY = os.environ.get("HEALTH_RECORDS_ENCRYPTION_KEY")
if not ENCRYPTION_KEY:
    raise ValueError("HEALTH_RECORDS_ENCRYPTION_KEY environment variable not set")

cipher = Fernet(ENCRYPTION_KEY.encode())

def encrypt_text(plaintext: str | None) -> str | None:

    if not plaintext:
        return None
    return cipher.encrypt(plaintext.encode()).decode()

def decrypt_text(ciphertext: str | None) -> str | None:
    if not ciphertext:
        return None
    return cipher.decrypt(ciphertext.encode()).decode()