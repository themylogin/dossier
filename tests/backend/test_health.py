from fastapi.testclient import TestClient


def test_health_is_503_without_a_link_to_the_downloader(client: TestClient) -> None:
    response = client.get("/api/health")

    assert response.status_code == 503
    assert response.json() == {"status": "downloader unavailable"}


def test_health_is_ok_with_a_link_to_the_downloader(linked_client: TestClient) -> None:
    response = linked_client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
