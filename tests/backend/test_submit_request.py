from collections.abc import Iterator
from pathlib import Path, PurePosixPath
import time

from fastapi.testclient import TestClient
import pytest

from dossier.backend.main import create_app
from dossier.backend.openclaw import OpenClawSettings
from tests.backend.fake_gateway import FakeGateway
from tests.backend.rpc import request


@pytest.fixture
def gateway() -> Iterator[FakeGateway]:
    server = FakeGateway()
    yield server
    server.stop()


@pytest.fixture
def exports_dir(tmp_path: Path) -> Path:
    path = tmp_path / "exports"
    path.mkdir()
    return path


@pytest.fixture
def openclaw_client(database_path: Path, gateway: FakeGateway, exports_dir: Path) -> Iterator[TestClient]:
    settings = OpenClawSettings(gateway.url, "secret", "", PurePosixPath("/home/me/.openclaw/workspace/dossier"))
    app = create_app(f"sqlite:///{database_path}", "ws://127.0.0.1:9", settings, exports_dir)
    with TestClient(app) as test_client:
        yield test_client


def test_request_submitted_returns_the_run_and_the_file(
    openclaw_client: TestClient, gateway: FakeGateway, exports_dir: Path
) -> None:
    with openclaw_client.websocket_connect("/api/ws_jsonrpc") as websocket:
        reply, _ = request(websocket, "submit_request", {"id": -2001, "text": "Summarize the decisions"}, request_id=2)

    exported = list(exports_dir.iterdir())
    assert len(exported) == 1
    session_key = gateway.requests[0][2]["sessionKey"]
    assert session_key == f"dossier:-2001:{exported[0].name.removeprefix('-2001-').removesuffix('.sqlite')}"
    assert reply["result"] == {
        "run_id": "run-1",
        "file": f"/home/me/.openclaw/workspace/dossier/{exported[0].name}",
        "session_url": f"{gateway.url}/chat/main/{session_key.replace(':', '/')}",
    }
    assert gateway.requests[0][2]["message"].startswith("Summarize the decisions")


def test_blank_text_is_invalid_and_writes_no_file(openclaw_client: TestClient, exports_dir: Path) -> None:
    with openclaw_client.websocket_connect("/api/ws_jsonrpc") as websocket:
        reply, _ = request(websocket, "submit_request", {"id": -2001, "text": "  \n "}, request_id=2)

    assert (reply["error"]["code"], reply["error"]["message"]) == (-32602, "Invalid params")
    assert list(exports_dir.iterdir()) == []


def test_unknown_chat_is_not_found(openclaw_client: TestClient) -> None:
    with openclaw_client.websocket_connect("/api/ws_jsonrpc") as websocket:
        reply, _ = request(websocket, "submit_request", {"id": 999, "text": "Hi"}, request_id=2)

    assert (reply["error"]["code"], reply["error"]["message"]) == (-32602, "Chat 999 not found")


def test_openclaw_not_configured(client: TestClient, database_path: Path) -> None:
    with client.websocket_connect("/api/ws_jsonrpc") as websocket:
        reply, _ = request(websocket, "submit_request", {"id": -2001, "text": "Hi"}, request_id=2)

    assert (reply["error"]["code"], reply["error"]["message"]) == (-32000, "OpenClaw is not configured")
    assert not list(database_path.parent.glob("*.sqlite"))


def test_two_requests_get_two_sessions(openclaw_client: TestClient, gateway: FakeGateway) -> None:
    with openclaw_client.websocket_connect("/api/ws_jsonrpc") as websocket:
        request(websocket, "submit_request", {"id": -2001, "text": "First"}, request_id=2)
        time.sleep(1.1)
        request(websocket, "submit_request", {"id": -2001, "text": "Second"}, request_id=3)

    first, second = (body["sessionKey"] for _, _, body in gateway.requests)
    assert first != second
