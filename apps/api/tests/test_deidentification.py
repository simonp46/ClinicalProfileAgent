from app.infrastructure.adapters.deid_service import DeidentificationService


def test_deidentify_redacts_known_entities() -> None:
    service = DeidentificationService()
    text = "Mi correo es ana@mail.com y mi telefono 3001234567. Vivo en Calle 10 #20-30."

    result = service.deidentify(text, known_names=["Ana"])

    assert "ana@mail.com" not in result.text
    assert "3001234567" not in result.text
    assert any(mapping.entity_type == "email" for mapping in result.mappings)
    assert any(mapping.entity_type == "phone" for mapping in result.mappings)