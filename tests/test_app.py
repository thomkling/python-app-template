from app.main import app
from fastapi.testclient import TestClient
from fastapi import HTTPException
import uuid

@app.get("/exception")
async def exception():
    raise HTTPException(status_code=500, detail="exception yo!")

@app.get("/widget/{widget_id}")
async def get_widget(widget_id: uuid.UUID):
    return {"widget_id": widget_id}

client = TestClient(app)

# ping should be available on all apps using the template
def test_ping():
    response = client.get("/ping")
    assert response.status_code == 200
    assert response.json() == "PONG"

# testing that HTTPException raised in the route is handled outside the middleware exception catcher
def test_exception():
    response = client.get("/exception")
    assert response.status_code == 500
    assert response.json() == {"detail":"exception yo!"}

# happy path test
def test_widget():
    response = client.get("/widget/7c3853a3-864a-4513-ac97-c3d6fd3776c9")
    assert response.status_code == 200
    assert response.json() == {"widget_id":"7c3853a3-864a-4513-ac97-c3d6fd3776c9"}