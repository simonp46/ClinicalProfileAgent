from sqlalchemy.orm import Session

from tests.helpers import seed_therapist_and_session


def test_happy_path_fixture_to_approved_draft(client, db_session: Session) -> None:
    _, session_id = seed_therapist_and_session(db_session)

    login = client.post(
        "/api/v1/auth/login",
        json={"email": "test@example.com", "password": "secret123"},
    )
    assert login.status_code == 200
    access_token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {access_token}"}

    process_response = client.post(f"/api/v1/sessions/{session_id}/process?sync=true", headers=headers)
    assert process_response.status_code == 200

    draft_response = client.post(f"/api/v1/sessions/{session_id}/generate-draft?sync=true", headers=headers)
    assert draft_response.status_code == 200
    draft_id = draft_response.json()["draft_id"]

    approve_response = client.post(
        f"/api/v1/drafts/{draft_id}/approve",
        json={"therapist_review_notes": "Revisado y validado"},
        headers=headers,
    )
    assert approve_response.status_code == 200
    assert approve_response.json()["status"] == "approved"

    detail = client.get(f"/api/v1/sessions/{session_id}", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["session"]["status"] == "approved"