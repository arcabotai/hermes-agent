"""Inert ``python -c`` literals are data, not lifecycle commands (#141164).

Branch D of the lifecycle pattern is a raw-text match, so a ``python -c`` payload that only builds
a dict and prints it was refused because its string values happened to read ``KILL`` ... ``Hermes``
... ``gateway``. A payload that provably cannot reach a process API (no imports, no attribute
access, only a few pure builtins called) is masked like a data-sink argument; anything that could
execute keeps the plain-regex verdict.
"""

import pytest

from cron.lifecycle_guard import contains_gateway_lifecycle_command_or_referenced_script as guard

ISSUE_PROBE = (
    "/usr/bin/python3 -B -c 'payload={\"purpose\":\"KILL/wait\",\"component\":\"Hermes\","
    "\"layer\":\"gateway\"}; print(\"diagnostic-only\", len(payload))'"
)


@pytest.mark.parametrize("command", [
    ISSUE_PROBE,
    "python3 -c 'print(\"kill the hermes gateway\")'",
    "python -u -c 'note = \"pkill -f hermes gateway\"; print(note[:5])'",
    "python3.12 -c 'n = 2; print(f\"{n} KILL Hermes gateway\", sorted([2, 1]))'",
])
def test_inert_python_payload_is_allowed(command, tmp_path):
    assert guard(command, cwd=str(tmp_path)) is False


@pytest.mark.parametrize("command", [
    # Payloads that can execute something keep the plain-regex block.
    "python3 -c 'import subprocess; subprocess.run([\"pkill\", \"-f\", \"hermes gateway\"])'",
    "python3 -c 'import os; os.system(\"hermes gateway restart\")'",
    "python3 -c '__import__(\"os\").system(\"pkill -f hermes gateway\")'",
    "python3 -c 'x = \"pkill -f hermes gateway\"; exec(x)'",
    "python3 -c 'print = exec; print(\"pkill -f hermes gateway\")'",
    "python3 -c 'print(\"x\").__class__(\"pkill -f hermes gateway\")'",
    # Interactive mode reads more code after the payload; unknown flags are not reasoned about.
    "python3 -i -c 'print(\"pkill -f hermes gateway\")'",
    "python3 -W ignore -c 'print(\"pkill -f hermes gateway\")'",
    # Only the payload is masked: argv after it and other segments are still scanned.
    "python3 -c 'print(1)' pkill -f 'hermes gateway'",
    "python3 -c 'print(1)'; pkill -f 'hermes gateway'",
    "python3 -c 'print(1)' && hermes gateway restart",
    # Not Python: the exemption is interpreter-specific.
    "node -e 'console.log(\"pkill -f hermes gateway\")'",
    # A Python payload that does not parse is uncertain.
    "python3 -c 'print(\"pkill -f hermes gateway\"'",
])
def test_executable_or_uncertain_payload_stays_blocked(command, tmp_path):
    assert guard(command, cwd=str(tmp_path)) is True
