from sqlalchemy.orm import Session

from tests.helpers import seed_therapist_and_session


def test_pdf_file_endpoint_supports_inline_and_download(client, db_session: Session) -> None:
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

    create_doc = client.post(f"/api/v1/drafts/{draft_id}/create-google-doc", headers=headers)
    assert create_doc.status_code == 200
    document_id = create_doc.json()["document_id"]

    inline_pdf = client.get(
        f"/api/v1/documents/{document_id}/file?format=pdf&disposition=inline",
        headers=headers,
    )
    assert inline_pdf.status_code == 200
    assert "application/pdf" in inline_pdf.headers.get("content-type", "")
    assert inline_pdf.headers.get("content-disposition", "").startswith("inline")

    attachment_pdf = client.get(
        f"/api/v1/documents/{document_id}/file?format=pdf&disposition=attachment",
        headers=headers,
    )
    assert attachment_pdf.status_code == 200
    assert attachment_pdf.headers.get("content-disposition", "").startswith("attachment")


def test_regenerate_then_create_and_delete_document(client, db_session: Session) -> None:
    _, session_id = seed_therapist_and_session(db_session)

    login = client.post(
        "/api/v1/auth/login",
        json={"email": "test@example.com", "password": "secret123"},
    )
    assert login.status_code == 200
    access_token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {access_token}"}

    assert client.post(f"/api/v1/sessions/{session_id}/process?sync=true", headers=headers).status_code == 200

    first_draft = client.post(f"/api/v1/sessions/{session_id}/generate-draft?sync=true", headers=headers)
    assert first_draft.status_code == 200
    first_draft_id = first_draft.json()["draft_id"]

    first_doc = client.post(f"/api/v1/drafts/{first_draft_id}/create-google-doc", headers=headers)
    assert first_doc.status_code == 200
    first_document_id = first_doc.json()["document_id"]

    regenerated = client.post(f"/api/v1/sessions/{session_id}/regenerate-draft?sync=true", headers=headers)
    assert regenerated.status_code == 200
    regenerated_draft_id = regenerated.json()["draft_id"]
    assert regenerated_draft_id

    second_doc = client.post(f"/api/v1/drafts/{regenerated_draft_id}/create-google-doc", headers=headers)
    assert second_doc.status_code == 200
    second_document_id = second_doc.json()["document_id"]
    assert second_document_id != first_document_id

    delete_response = client.delete(f"/api/v1/documents/{second_document_id}", headers=headers)
    assert delete_response.status_code == 200
    assert delete_response.json()["status"] == "deleted"

    deleted_file = client.get(
        f"/api/v1/documents/{second_document_id}/file?format=pdf&disposition=attachment",
        headers=headers,
    )
    assert deleted_file.status_code == 404
