# Диалоги и сообщения личного кабинета (ФЛК-006, ФЛК-007).

from __future__ import annotations

from typing import Any
from urllib.parse import quote

from .models import Dialogue, DialogueMessage


class MessagesMixin:
    async def get_dialogues(self) -> list[Dialogue]:
        raw = await self.lk_get("getMsgDialogues")  # type: ignore[attr-defined]
        return [Dialogue.from_dict(d) for d in raw or []]

    async def get_dialogue_messages(self, dialogue_id: str) -> list[DialogueMessage]:
        raw = await self.lk_get(  # type: ignore[attr-defined]
            f"getMessagesInDialogue={dialogue_id}"
        )
        if isinstance(raw, list):
            return [DialogueMessage.from_dict(m) for m in raw]
        return []

    async def get_group_chat(self) -> str:
        raw = await self.lk_get("getGroupChat")  # type: ignore[attr-defined]
        return (raw or {}).get("link") or ""

    async def send_message(self, dialogue_id: str, text: str) -> Any:
        # формат из фронтенда ЛК (2026-10-07): адресат — в query (to_dialogue / to_id / to_group),
        # текст — поле text в multipart/form-data; id диалога из getMsgDialogues уже percent-encoded
        return await self.lk_post_multipart(  # type: ignore[attr-defined]
            f"newMessage=1&to_dialogue={dialogue_id}", {"text": text}
        )

    async def send_group_message(self, group: str, text: str) -> Any:
        # то же, адресат — вся учебная группа (во фронтенде ЛК — «Группе: 241-327»)
        return await self.lk_post_multipart(  # type: ignore[attr-defined]
            f"newMessage=1&to_group={quote(group)}", {"text": text}
        )
