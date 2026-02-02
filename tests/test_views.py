def test_liveness(test_client):
    response = test_client.get("/livez")
    assert response.status_code == 200
    assert response.data == b"OK"


def test_readiness(test_client):
    response = test_client.get("/readyz")
    assert response.status_code == 200
    assert response.data == b"OK"
