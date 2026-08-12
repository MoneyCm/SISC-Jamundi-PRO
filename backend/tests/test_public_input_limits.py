import pytest
from pydantic import ValidationError

from api.ia import CitizenChatRequest
from api.participacion import ProposalCreate, SecureReportCreate


def test_citizen_chat_limits_message_and_history_size():
    with pytest.raises(ValidationError):
        CitizenChatRequest(message="x" * 1001)

    with pytest.raises(ValidationError):
        CitizenChatRequest(
            message="consulta",
            history=[{"sender": "user", "text": "hola"}] * 9,
        )


def test_public_forms_reject_oversized_free_text():
    with pytest.raises(ValidationError):
        ProposalCreate(
            title="Propuesta valida",
            description="x" * 3001,
            category="Seguridad",
            barrio="Centro",
        )

    with pytest.raises(ValidationError):
        SecureReportCreate(
            tipo="Riesgo",
            barrio="Centro",
            fecha="2026-08-12",
            hora="12:30",
            descripcion="x" * 4001,
            es_anonimo=True,
        )
