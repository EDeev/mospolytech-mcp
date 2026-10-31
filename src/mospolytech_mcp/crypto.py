# Шифрование токенов ЛК в БД (Fernet) и ключи доступа к серверу (в БД — только SHA-256).

from __future__ import annotations

import hashlib
import secrets

from cryptography.fernet import Fernet, InvalidToken

API_KEY_PREFIX = "mpk_"


class SecretKeyMissingError(RuntimeError):
    def __init__(self) -> None:
        super().__init__(
            "MCP_SECRET_KEY не задан — без него нельзя хранить токены личного кабинета. "
            "Сгенерируйте: python -m mospolytech_mcp.crypto"
        )


class TokenCipher:
    def __init__(self, key: str | None) -> None:
        self._fernet = Fernet(key.encode()) if key else None

    @property
    def available(self) -> bool:
        return self._fernet is not None

    def _require(self) -> Fernet:
        if self._fernet is None:
            raise SecretKeyMissingError()
        return self._fernet

    def encrypt(self, value: str) -> str:
        if not value:
            return ""
        return self._require().encrypt(value.encode()).decode()

    def decrypt(self, value: str) -> str:
        if not value:
            return ""
        try:
            return self._require().decrypt(value.encode()).decode()
        except InvalidToken as exc:
            raise ValueError("токен не расшифровывается — сменился MCP_SECRET_KEY?") from exc


def new_api_key() -> str:
    return API_KEY_PREFIX + secrets.token_urlsafe(32)


def hash_api_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


if __name__ == "__main__":
    print(Fernet.generate_key().decode())
