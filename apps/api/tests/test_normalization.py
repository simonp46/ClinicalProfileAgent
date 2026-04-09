from app.application.services.transcript_pipeline_types import TranscriptEntry
from app.infrastructure.adapters.transcript_normalizer import TranscriptNormalizer


def test_normalizer_sorts_merges_and_labels() -> None:
    normalizer = TranscriptNormalizer()
    entries = [
        TranscriptEntry(sequence_no=2, speaker_label="Paciente", text="Estoy cansada"),
        TranscriptEntry(sequence_no=1, speaker_label="Terapeuta", text="Hola"),
        TranscriptEntry(sequence_no=3, speaker_label="Paciente", text="y ansiosa"),
    ]

    result = normalizer.normalize_entries(
        entries,
        therapist_name="Terapeuta",
        patient_name="Paciente",
    )

    assert len(result) == 2
    assert result[0].speaker_label == "THERAPIST"
    assert result[1].speaker_label == "PATIENT"
    assert "Estoy cansada y ansiosa" in result[1].text