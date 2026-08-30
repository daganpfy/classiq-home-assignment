from __future__ import annotations

from qiskit import QuantumCircuit, qasm3


def hadamard_qasm() -> str:
    circuit = QuantumCircuit(1, 1)
    circuit.h(0)
    circuit.measure(0, 0)
    return qasm3.dumps(circuit)


def bell_qasm() -> str:
    circuit = QuantumCircuit(2, 2)
    circuit.h(0)
    circuit.cx(0, 1)
    circuit.measure([0, 1], [0, 1])
    return qasm3.dumps(circuit)
