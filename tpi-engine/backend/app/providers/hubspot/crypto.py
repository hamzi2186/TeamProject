from cryptography.fernet import Fernet, InvalidToken

from app.providers.hubspot.errors import ConnectionRevokedError


class TokenCipher:
    def __init__(self, key: str) -> None:
        self._fernet = Fernet(key.encode())

    def encrypt(self, token: str) -> str:
        return self._fernet.encrypt(token.encode()).decode()

    def decrypt(self, encrypted_token: str) -> str:
        try:
            return self._fernet.decrypt(encrypted_token.encode()).decode()
        except InvalidToken as exc:
            raise ConnectionRevokedError("Stored HubSpot credential cannot be decrypted") from exc
