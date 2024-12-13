from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)

def test_ping():
    response = client.get("/ping")
    assert response.status_code == 200
    # fastapi returns a quoted string in the response
    assert response.text == '"PONG"'