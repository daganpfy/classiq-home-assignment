from __future__ import annotations

from app.exceptions import InvalidCircuitError


class QiskitCircuitExecutor:
    def __init__(self, shots: int = 1024) -> None:
        self._shots = shots
        self._simulator = None

    def validate(self, qasm: str) -> None:
        self._loads(qasm)

    def execute(self, qasm: str) -> dict[str, int]:
        from qiskit import transpile

        circuit = self._loads(qasm)
        simulator = self._get_simulator()
        transpiled = transpile(circuit, simulator)
        job = simulator.run(transpiled, shots=self._shots)
        counts = job.result().get_counts()
        return {str(bitstring): int(count) for bitstring, count in counts.items()}

    def _get_simulator(self):
        if self._simulator is None:
            from qiskit_aer import AerSimulator

            self._simulator = AerSimulator()
        return self._simulator

    @staticmethod
    def _loads(qasm: str):
        try:
            from qiskit import qasm3

            return qasm3.loads(qasm)
        except Exception as exc:
            reason = str(exc).strip().strip('"') or "could not parse the payload"
            raise InvalidCircuitError(f"Invalid QASM3 circuit: {reason}") from exc
