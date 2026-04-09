from sqlalchemy.orm import Session

from tests.helpers import seed_therapist_and_session


def test_workspace_webhook_accepts_valid_payload(client, db_session: Session, monkeypatch) -> None:
    _, session_id = seed_therapist_and_session(db_session)

    captured: dict[str, str | None] = {}

    class StubTask:
        @staticmethod
        def delay(sid: str, transcript_name: str | None = None) -> None:
            captured["session_id"] = sid
            captured["transcript_name"] = transcript_name

    monkeypatch.setattr("app.api.routes.webhooks.process_and_generate_task", StubTask())

    response = client.post(
        "/webhooks/google/workspace-events",
        json={
            "eventType": "google.workspace.meet.transcript.finalized",
            "sessionId": session_id,
            "transcriptName": "spaces/AAAA/transcripts/1",
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == "accepted"
    assert captured["session_id"] == session_id
