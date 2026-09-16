from typing import Any, Protocol

from app.modules.calling.exceptions import KnowledgeBaseUnavailableError


class ClientKBReader(Protocol):
    def search(self, *, user_id: str, lead_id: str, query: str, limit: int = 6) -> list[dict[str, Any]]: ...


class ClientKBTool:
    def __init__(self, reader: ClientKBReader) -> None:
        self.reader = reader

    def search(self, *, user_id: str, lead_id: str, query: str) -> dict[str, Any]:
        results = self.reader.search(user_id=user_id, lead_id=lead_id, query=query, limit=6)
        if results is None:
            raise KnowledgeBaseUnavailableError("Client KB is not available")
        return {"results": results}
