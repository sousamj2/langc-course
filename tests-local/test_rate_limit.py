import pytest
from fastapi.testclient import TestClient
from app.main import app

def test_rate_limiter():
    with TestClient(app) as client:
        responses = []
        for i in range(30):
            response = client.post(
                "/chat",
                json={"message": f"Request {i}", "thread_id": "test-rate-limit"}
            )
            responses.append(response.status_code)
            
        print("Responses:", responses)
        assert 429 in responses
