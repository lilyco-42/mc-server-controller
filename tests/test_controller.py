"""Pytest tests for MC Server Controller."""

import pytest
from httpx import ASGITransport, AsyncClient
from unittest.mock import AsyncMock, patch, MagicMock

from mc_controller import app, sv


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


# ─── Frontend ───────────────────────────────────────────
class TestFrontend:
    @pytest.mark.asyncio
    async def test_index_returns_html(self, client):
        r = await client.get("/")
        assert r.status_code == 200
        assert "MC Server Controller" in r.text
        assert "<html" in r.text.lower()

    @pytest.mark.asyncio
    async def test_index_has_controls(self, client):
        r = await client.get("/")
        assert "doStart" in r.text
        assert "doStop" in r.text
        assert "doRestart" in r.text
        assert "send()" in r.text


# ─── Status API ─────────────────────────────────────────
class TestStatus:
    @pytest.mark.asyncio
    async def test_status_returns_running(self, client):
        r = await client.get("/api/status")
        assert r.status_code == 200
        data = r.json()
        assert "running" in data
        assert isinstance(data["running"], bool)

    @pytest.mark.asyncio
    async def test_status_reflects_state(self, client):
        r = await client.get("/api/status")
        data = r.json()
        # Server should not be running in test env
        assert data["running"] is False


# ─── Console API ────────────────────────────────────────
class TestConsole:
    @pytest.mark.asyncio
    async def test_console_returns_lines(self, client):
        r = await client.get("/api/console")
        assert r.status_code == 200
        data = r.json()
        assert "lines" in data
        assert "total" in data
        assert isinstance(data["lines"], list)
        assert isinstance(data["total"], int)

    @pytest.mark.asyncio
    async def test_console_offset(self, client):
        sv.buf = ["line1", "line2", "line3"]
        r = await client.get("/api/console?offset=1")
        data = r.json()
        assert data["lines"] == ["line2", "line3"]
        assert data["total"] == 3
        sv.buf.clear()


# ─── Start API ──────────────────────────────────────────
class TestStart:
    @pytest.mark.asyncio
    async def test_start_when_already_running(self, client):
        with patch.object(type(sv), "alive", new_callable=lambda: property(lambda self: True)):
            r = await client.post("/api/start")
            data = r.json()
            assert data["ok"] == 0
            assert "Already running" in data["msg"]

    @pytest.mark.asyncio
    async def test_start_jar_not_found(self, client):
        with patch.object(type(sv), "alive", new_callable=lambda: property(lambda self: False)), \
             patch("mc_controller.os.path.isfile", return_value=False):
            r = await client.post("/api/start")
            data = r.json()
            assert data["ok"] == 0
            assert "not found" in data["msg"].lower()


# ─── Stop API ───────────────────────────────────────────
class TestStop:
    @pytest.mark.asyncio
    async def test_stop_when_not_running(self, client):
        with patch.object(type(sv), "alive", new_callable=lambda: property(lambda self: False)):
            r = await client.post("/api/stop")
            data = r.json()
            assert data["ok"] == 0
            assert "Not running" in data["msg"]

    @pytest.mark.asyncio
    async def test_stop_sends_stop_command(self, client):
        mock_proc = MagicMock()
        mock_proc.returncode = None
        mock_proc.stdin = AsyncMock()
        mock_proc.wait = AsyncMock(return_value=0)

        with patch.object(type(sv), "alive", new_callable=lambda: property(lambda self: True)), \
             patch.object(sv, "proc", mock_proc):
            r = await client.post("/api/stop")
            data = r.json()
            assert data["ok"] == 1
            mock_proc.stdin.write.assert_called_with(b"stop\n")


# ─── Command API ────────────────────────────────────────
class TestCommand:
    @pytest.mark.asyncio
    async def test_command_when_not_running(self, client):
        with patch.object(type(sv), "alive", new_callable=lambda: property(lambda self: False)):
            r = await client.post("/api/command", data={"command": "/say hello"})
            data = r.json()
            assert data["ok"] == 0
            assert "Not running" in data["msg"]

    @pytest.mark.asyncio
    async def test_command_sends_to_stdin(self, client):
        mock_proc = MagicMock()
        mock_proc.stdin = AsyncMock()

        with patch.object(type(sv), "alive", new_callable=lambda: property(lambda self: True)), \
             patch.object(sv, "proc", mock_proc):
            r = await client.post("/api/command", data={"command": "/say hello"})
            data = r.json()
            assert data["ok"] == 1
            assert "Sent" in data["msg"]
            mock_proc.stdin.write.assert_called_with(b"/say hello\n")

    @pytest.mark.asyncio
    async def test_command_empty_rejected_by_framework(self, client):
        r = await client.post("/api/command", data={"command": ""})
        assert r.status_code == 422


# ─── Server Manager Unit ────────────────────────────────
class TestServerManager:
    def test_alive_when_none(self):
        from mc_controller import Server
        s = Server()
        assert s.alive is False

    def test_alive_when_exited(self):
        from mc_controller import Server
        s = Server()
        s.proc = MagicMock()
        s.proc.returncode = 0
        assert s.alive is False

    def test_alive_when_running(self):
        from mc_controller import Server
        s = Server()
        s.proc = MagicMock()
        s.proc.returncode = None
        assert s.alive is True

    @pytest.mark.asyncio
    async def test_broadcast(self):
        from mc_controller import Server
        s = Server()
        ws1 = AsyncMock()
        ws2 = AsyncMock()
        s.ws = {ws1, ws2}
        await s._cast("test line")
        ws1.send_text.assert_called_once_with("test line")
        ws2.send_text.assert_called_once_with("test line")

    @pytest.mark.asyncio
    async def test_broadcast_removes_dead(self):
        from mc_controller import Server
        s = Server()
        ws_ok = AsyncMock()
        ws_dead = AsyncMock()
        ws_dead.send_text = AsyncMock(side_effect=Exception("disconnected"))
        s.ws = {ws_ok, ws_dead}
        await s._cast("test")
        assert ws_dead not in s.ws
        assert ws_ok in s.ws

    @pytest.mark.asyncio
    async def test_command_when_none(self):
        from mc_controller import Server
        s = Server()
        result = await s.command("/say hi")
        assert result["ok"] == 0

    @pytest.mark.asyncio
    async def test_stop_when_none(self):
        from mc_controller import Server
        s = Server()
        result = await s.stop()
        assert result["ok"] == 0
