"""The classic CLI honours the persisted ``display.tui_theme`` pin (#144550).

The TUI's /theme writes ``display.tui_theme: light|dark`` and the Ink TUI bridges it to
HERMES_TUI_THEME. The classic CLI read only the env var, so the pin was ignored there and a
terminal that answers neither OSC 11 nor DA1 paid the probe's full 1s safety net on every
launch with no config-level way out.
"""

from __future__ import annotations

import os
import sys
import time

import pytest


_LIGHT_ENV = ("HERMES_LIGHT", "HERMES_TUI_LIGHT", "HERMES_TUI_THEME", "HERMES_TUI_BACKGROUND", "COLORFGBG")


@pytest.fixture
def cli_mod(monkeypatch):
    import cli as _cli

    monkeypatch.setattr(_cli, "_LIGHT_MODE_CACHE", None)
    for var in _LIGHT_ENV:
        monkeypatch.delenv(var, raising=False)
    return _cli


@pytest.fixture
def probe_calls(cli_mod, monkeypatch):
    """Record OSC 11 probes; the probe answers 'no colour' like a mute terminal."""
    calls: list[int] = []

    def _probe() -> str | None:
        calls.append(1)
        return None

    monkeypatch.setattr(cli_mod, "_query_osc11_background", _probe)
    return calls


def _pin(cli_mod, monkeypatch, value):
    display = dict(cli_mod.CLI_CONFIG.get("display") or {})
    if value is None:
        display.pop("tui_theme", None)
    else:
        display["tui_theme"] = value
    monkeypatch.setitem(cli_mod.CLI_CONFIG, "display", display)


class TestConfiguredThemePin:
    @pytest.mark.parametrize("value", ["light", "Light", " LIGHT "])
    def test_light_pin_forces_light_without_probing(self, cli_mod, probe_calls, monkeypatch, value):
        _pin(cli_mod, monkeypatch, value)
        assert cli_mod._detect_light_mode() is True
        assert probe_calls == []

    def test_dark_pin_forces_dark_without_probing(self, cli_mod, probe_calls, monkeypatch):
        _pin(cli_mod, monkeypatch, "dark")
        assert cli_mod._detect_light_mode() is False
        assert probe_calls == []

    def test_dark_pin_beats_a_light_colorfgbg(self, cli_mod, probe_calls, monkeypatch):
        _pin(cli_mod, monkeypatch, "dark")
        monkeypatch.setenv("COLORFGBG", "0;15")
        assert cli_mod._detect_light_mode() is False

    @pytest.mark.parametrize("value", [None, "auto", "", "sepia", 7])
    def test_auto_or_unknown_pin_still_probes(self, cli_mod, probe_calls, monkeypatch, value):
        _pin(cli_mod, monkeypatch, value)
        assert cli_mod._detect_light_mode() is False
        assert probe_calls == [1]

    def test_non_mapping_display_section_still_probes(self, cli_mod, probe_calls, monkeypatch):
        monkeypatch.setitem(cli_mod.CLI_CONFIG, "display", "dark")
        assert cli_mod._detect_light_mode() is False
        assert probe_calls == [1]

    def test_env_theme_outranks_the_pin(self, cli_mod, probe_calls, monkeypatch):
        _pin(cli_mod, monkeypatch, "dark")
        monkeypatch.setenv("HERMES_TUI_THEME", "light")
        assert cli_mod._detect_light_mode() is True

    def test_hermes_light_outranks_the_pin(self, cli_mod, probe_calls, monkeypatch):
        _pin(cli_mod, monkeypatch, "light")
        monkeypatch.setenv("HERMES_LIGHT", "0")
        assert cli_mod._detect_light_mode() is False


# Real PTY, real config.yaml: importing cli primes detection before prompt_toolkit owns the
# tty. On a mute terminal (answers nothing) the pin must skip the probe entirely.
_CHILD_SRC = r"""
import os, sys, time
sys.path.insert(0, os.environ["HERMES_REPO"])
t0 = time.monotonic()
import cli
print("LIGHT:%r" % (cli._LIGHT_MODE_CACHE,), flush=True)
print("IMPORT_S:%.3f" % (time.monotonic() - t0), flush=True)
"""


def _run_mute_child(tmp_path, pin):
    import pty

    home = tmp_path / "home"
    home.mkdir()
    if pin is not None:
        (home / "config.yaml").write_text(f"display:\n  tui_theme: {pin}\n", encoding="utf-8")
    env = dict(os.environ, HERMES_REPO=str(_repo_root()), HERMES_HOME=str(home))
    for var in ("SSH_CONNECTION", "SSH_CLIENT", "SSH_TTY", *_LIGHT_ENV):
        env.pop(var, None)
    pid, master = pty.fork()
    if pid == 0:  # child
        os.execvpe(sys.executable, [sys.executable, "-c", _CHILD_SRC], env)
    os.set_blocking(master, False)
    out = b""
    deadline = time.monotonic() + 60
    try:
        # Read to EOF: the child exits right after its last print (EIO on Linux PTYs).
        while time.monotonic() < deadline:
            try:
                chunk = os.read(master, 4096)
            except BlockingIOError:
                time.sleep(0.01)
                continue
            except OSError:
                break
            if not chunk:
                break
            out += chunk
    finally:
        os.close(master)
        os.waitpid(pid, 0)
    return out


def _repo_root():
    import pathlib

    return pathlib.Path(__file__).resolve().parents[2]


@pytest.mark.platforms("posix")  # POSIX PTY test
class TestPinOnAMuteTerminal:
    def test_dark_pin_sends_no_osc11_query(self, tmp_path):
        out = _run_mute_child(tmp_path, "dark")
        assert b"LIGHT:False" in out, out
        assert b"\x1b]11;?" not in out, "the pin must skip the OSC 11 probe"

    def test_light_pin_sends_no_osc11_query(self, tmp_path):
        out = _run_mute_child(tmp_path, "light")
        assert b"LIGHT:True" in out, out
        assert b"\x1b]11;?" not in out

    def test_without_a_pin_the_mute_terminal_is_still_probed(self, tmp_path):
        out = _run_mute_child(tmp_path, None)
        assert b"LIGHT:False" in out, out
        assert b"\x1b]11;?" in out, "auto keeps the probe"
