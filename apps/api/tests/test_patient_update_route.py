from sqlalchemy.orm import Session

from tests.helpers import seed_therapist_and_session


def test_update_patient_personal_data(client, db_session: Session) -> None:
    _, session_id = seed_therapist_and_session(db_session)

    login = client.post(
        "/api/v1/auth/login",
        json={"email": "test@example.com", "password": "secret123"},
    )
    assert login.status_code == 200
    access_token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {access_token}"}

    update_response = client.patch(
        f"/api/v1/sessions/{session_id}/patient",
        headers=headers,
        json={
            "full_name": "Carla Rios",
            "phone": "+57 3012345678",
            "external_patient_id": "CC-123456",
            "birth_date": "1995-04-20",
            "age": 31,
            "gender": "femenino",
            "address": "Calle 10 # 20-30, Bogota",
            "city": "Bogota",
            "profession": "Psicologa",
            "email": "carla.rios@example.com",
        },
    )

    assert update_response.status_code == 200
    patient_payload = update_response.json()["patient"]
    assert patient_payload["first_name"] == "Carla"
    assert patient_payload["last_name"] == "Rios"
    assert patient_payload["phone"] == "+57 3012345678"
    assert patient_payload["external_patient_id"] == "CC-123456"
    assert patient_payload["birth_date"] == "1995-04-20"
    assert patient_payload["age"] == 31
    assert patient_payload["gender"] == "femenino"
    assert patient_payload["address"] == "Calle 10 # 20-30, Bogota"
    assert patient_payload["city"] == "Bogota"
    assert patient_payload["profession"] == "Psicologa"
    assert patient_payload["email"] == "carla.rios@example.com"

    session_response = client.get(f"/api/v1/sessions/{session_id}", headers=headers)
    assert session_response.status_code == 200
    session_patient = session_response.json()["session"]["patient"]

    assert session_patient["first_name"] == "Carla"
    assert session_patient["last_name"] == "Rios"
    assert session_patient["phone"] == "+57 3012345678"
    assert session_patient["external_patient_id"] == "CC-123456"
    assert session_patient["birth_date"] == "1995-04-20"
    assert session_patient["age"] == 31
    assert session_patient["gender"] == "femenino"
    assert session_patient["address"] == "Calle 10 # 20-30, Bogota"
    assert session_patient["city"] == "Bogota"
    assert session_patient["profession"] == "Psicologa"
    assert session_patient["email"] == "carla.rios@example.com"
