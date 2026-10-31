# HTTP-страницы рядом с MCP: /health для мониторинга и деплоя, /login — вход без передачи пароля через LLM.

from __future__ import annotations

import html
import time
from collections import defaultdict, deque
from typing import TYPE_CHECKING
from urllib.parse import parse_qs

from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, Response

from . import __version__
from .auth import AuthError

if TYPE_CHECKING:
    from mcp.server.mcpserver import MCPServer

    from .server import Services

LOGIN_ATTEMPTS = 5
LOGIN_WINDOW = 300.0

_PAGE = """<!doctype html>
<html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Mospolytech MCP — вход</title>
<style>
 body {{ font-family: system-ui, sans-serif; background: #f4f5f7; color: #1d1f23; margin: 0; padding: 32px 16px; }}
 main {{ max-width: 520px; margin: 0 auto; background: #fff; border-radius: 12px; padding: 28px; box-shadow: 0 1px 4px #0002; }}
 h1 {{ font-size: 22px; margin: 0 0 8px; }}
 p {{ line-height: 1.5; }}
 label {{ display: block; margin: 14px 0 4px; font-weight: 600; }}
 input {{ width: 100%; box-sizing: border-box; padding: 10px; border: 1px solid #c8ccd4; border-radius: 8px; font-size: 15px; }}
 button {{ margin-top: 18px; padding: 10px 18px; border: 0; border-radius: 8px; background: #6b2fd6; color: #fff; font-size: 15px; cursor: pointer; }}
 pre {{ background: #f0f1f4; padding: 12px; border-radius: 8px; white-space: pre-wrap; word-break: break-all; }}
 .error {{ color: #b3261e; }}
 @media (prefers-color-scheme: dark) {{
  body {{ background: #15171b; color: #e6e7ea; }} main {{ background: #1f2228; box-shadow: none; }}
  input {{ background: #15171b; color: #e6e7ea; border-color: #3a3f48; }} pre {{ background: #15171b; }}
 }}
</style></head><body><main>{body}</main></body></html>"""

_FORM = """<h1>Вход в Mospolytech MCP</h1>
<p>Логин и пароль от личного кабинета e.mospolytech.ru. Пароль используется один раз и не сохраняется —
сервер получит токены ЛК и выдаст вам персональный ключ для MCP-клиента.</p>
{error}
<form method="post">
 <label for="login">Логин</label><input id="login" name="login" autocomplete="username" required>
 <label for="password">Пароль</label><input id="password" name="password" type="password" autocomplete="current-password" required>
 <button type="submit">Войти</button>
</form>"""

_DONE = """<h1>Готово, {name}</h1>
<p>Ваш персональный ключ — показывается один раз:</p>
<pre>{key}</pre>
<p>Добавьте его в настройки MCP-клиента как заголовок:</p>
<pre>Authorization: Bearer {key}</pre>
<p>Пример для клиента с конфигом в JSON:</p>
<pre>{config}</pre>
<p>Выйти и отозвать все ключи — инструмент <code>lk_logout</code>.</p>"""


def add_web_routes(mcp: MCPServer, svc: Services) -> None:
    attempts: dict[str, deque[float]] = defaultdict(deque)

    def limited(ip: str) -> bool:
        now = time.monotonic()
        queue = attempts[ip]
        while queue and now - queue[0] > LOGIN_WINDOW:
            queue.popleft()
        if len(queue) >= LOGIN_ATTEMPTS:
            return True
        queue.append(now)
        return False

    @mcp.custom_route("/health", methods=["GET"], include_in_schema=False)
    async def health(_: Request) -> Response:
        try:
            index = await svc.teachers.status()
        except Exception as exc:
            return JSONResponse({"status": "error", "error": str(exc)[:200]}, status_code=503)
        return JSONResponse({"status": "ok", "version": __version__, "teacher_index": index})

    @mcp.custom_route("/login", methods=["GET", "POST"], include_in_schema=False)
    async def login_page(request: Request) -> Response:
        if request.method == "GET":
            return HTMLResponse(_PAGE.format(body=_FORM.format(error="")))

        ip = request.client.host if request.client else "?"
        if limited(ip):
            error = '<p class="error">Слишком много попыток — подождите пять минут.</p>'
            return HTMLResponse(_PAGE.format(body=_FORM.format(error=error)), status_code=429)

        form = parse_qs((await request.body()).decode("utf-8", "replace"))
        login = (form.get("login") or [""])[0]
        password = (form.get("password") or [""])[0]
        try:
            result = await svc.auth.login(login, password)
        except AuthError as exc:
            error = f'<p class="error">{html.escape(str(exc))}</p>'
            return HTMLResponse(_PAGE.format(body=_FORM.format(error=error)), status_code=401)

        base = svc.settings.public_url or str(request.base_url).rstrip("/")
        config = (
            '{\n  "mcpServers": {\n    "mospolytech": {\n'
            f'      "url": "{base}/mcp",\n'
            f'      "headers": {{ "Authorization": "Bearer {result.api_key}" }}\n'
            "    }\n  }\n}"
        )
        body = _DONE.format(
            name=html.escape(result.full_name),
            key=html.escape(result.api_key),
            config=html.escape(config),
        )
        return HTMLResponse(_PAGE.format(body=body), headers={"Cache-Control": "no-store"})
