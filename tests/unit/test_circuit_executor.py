from __future__ import annotations

import pytest

from app.exceptions import InvalidCircuitError
from app.services.circuit_executor import QiskitCircuitExecutor
from tests.helpers import hadamard_qasm


def test_executor_runs_hadamard() -> None:
    result = QiskitCircuitExecutor(shots=1024).execute(hadamard_qasm())
    assert sum(result.values()) == 1024
    assert set(result).issubset({"0", "1"})


def test_executor_rejects_invalid_qasm() -> None:
    with pytest.raises(InvalidCircuitError, match=r"Invalid QASM3 circuit: .+") as err:
        QiskitCircuitExecutor().validate("this is not qasm")
    assert not str(err.value).rstrip().endswith(":")
