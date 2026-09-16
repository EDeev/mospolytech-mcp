# Диалоги и сообщения личного кабинета (ФЛК-006, ФЛК-007).

from __future__ import annotations

from typing import Any

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
        form = {"id": dialogue_id, "text": text}
        return await self.lk_post_form("newMessage=1", form)  # type: ignore[attr-defined]
