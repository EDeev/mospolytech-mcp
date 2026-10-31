# Пакет mospolytech-mcp: MCP-сервер с доступом к open_api и lk_api Политеха.

__version__ = "1.0.0"

from .api import UniversityAPI  # noqa: E402

__all__ = ["UniversityAPI", "__version__"]
