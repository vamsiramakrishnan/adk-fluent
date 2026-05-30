"""Feature #6 — CLI subcommands (new, run, doctor, serve, visualize dispatch)."""

from __future__ import annotations

import sys
import textwrap

import pytest

from adk_fluent.cli import main


def _write_sample_module(tmp_path, monkeypatch, name="sample_cli_agent"):
    """Write an importable module exposing builders and put it on sys.path."""
    mod_path = tmp_path / f"{name}.py"
    mod_path.write_text(
        textwrap.dedent(
            """
            from adk_fluent import Agent

            root_agent = (
                Agent("sample", "gemini-2.5-flash")
                .instruct("You are helpful.")
                .mock(["mocked-reply"])
            )

            other_agent = Agent("other", "gemini-2.5-flash").instruct("hi")
            """
        )
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    # Ensure a fresh import each call.
    sys.modules.pop(name, None)
    return name


# --------------------------------------------------------------------------- #
# new
# --------------------------------------------------------------------------- #
class TestNew:
    def test_creates_expected_files(self, tmp_path, capsys):
        main(["new", "myproj", "--dir", str(tmp_path)])
        base = tmp_path / "myproj"
        assert (base / "agent.py").is_file()
        assert (base / "__init__.py").is_file()
        assert (base / "README.md").is_file()

    def test_agent_file_has_root_agent(self, tmp_path):
        main(["new", "myproj", "--dir", str(tmp_path)])
        text = (tmp_path / "myproj" / "agent.py").read_text()
        assert "root_agent" in text
        assert "Agent(" in text

    def test_prints_created_paths(self, tmp_path, capsys):
        main(["new", "myproj", "--dir", str(tmp_path)])
        out = capsys.readouterr().out
        assert "agent.py" in out
        assert "myproj" in out

    def test_refuses_existing_dir(self, tmp_path, capsys):
        (tmp_path / "myproj").mkdir()
        with pytest.raises(SystemExit) as exc:
            main(["new", "myproj", "--dir", str(tmp_path)])
        assert exc.value.code == 1
        assert "already exists" in capsys.readouterr().err


# --------------------------------------------------------------------------- #
# doctor
# --------------------------------------------------------------------------- #
class TestDoctor:
    def test_prints_diagnostics(self, tmp_path, monkeypatch, capsys):
        name = _write_sample_module(tmp_path, monkeypatch)
        main(["doctor", f"{name}:root_agent"])
        out = capsys.readouterr().out
        assert out.strip()  # produced a report

    def test_missing_attr_errors(self, tmp_path, monkeypatch, capsys):
        name = _write_sample_module(tmp_path, monkeypatch)
        with pytest.raises(SystemExit) as exc:
            main(["doctor", f"{name}:nope"])
        assert exc.value.code == 1
        assert "not found" in capsys.readouterr().err

    def test_bad_module_errors(self, capsys):
        with pytest.raises(SystemExit) as exc:
            main(["doctor", "no_such_module_xyz:root_agent"])
        assert exc.value.code == 1
        assert "could not import" in capsys.readouterr().err

    def test_ambiguous_module_errors(self, tmp_path, monkeypatch, capsys):
        name = _write_sample_module(tmp_path, monkeypatch)
        with pytest.raises(SystemExit) as exc:
            main(["doctor", name])  # two builders, no attr
        assert exc.value.code == 1
        assert "multiple builders" in capsys.readouterr().err


# --------------------------------------------------------------------------- #
# run
# --------------------------------------------------------------------------- #
class TestRun:
    def test_run_with_prompt_prints_response(self, tmp_path, monkeypatch, capsys):
        name = _write_sample_module(tmp_path, monkeypatch)
        main(["run", f"{name}:root_agent", "--prompt", "hello"])
        out = capsys.readouterr().out
        assert "mocked-reply" in out

    def test_run_reads_stdin(self, tmp_path, monkeypatch, capsys):
        import io

        name = _write_sample_module(tmp_path, monkeypatch)
        monkeypatch.setattr(sys, "stdin", io.StringIO("hi there"))
        main(["run", f"{name}:root_agent"])
        assert "mocked-reply" in capsys.readouterr().out


# --------------------------------------------------------------------------- #
# serve
# --------------------------------------------------------------------------- #
class TestServe:
    def test_prints_adk_command(self, tmp_path, monkeypatch, capsys):
        name = _write_sample_module(tmp_path, monkeypatch)
        main(["serve", f"{name}:root_agent", "--port", "9001"])
        out = capsys.readouterr().out
        assert "adk web" in out
        assert "9001" in out


# --------------------------------------------------------------------------- #
# dispatch / help / unknown
# --------------------------------------------------------------------------- #
class TestDispatch:
    def test_top_level_help_exits_zero(self, capsys):
        with pytest.raises(SystemExit) as exc:
            main(["--help"])
        assert exc.value.code == 0
        assert "doctor" in capsys.readouterr().out

    @pytest.mark.parametrize("cmd", ["doctor", "run", "new", "serve", "visualize"])
    def test_subcommand_help_exits_zero(self, cmd, capsys):
        with pytest.raises(SystemExit) as exc:
            main([cmd, "--help"])
        assert exc.value.code == 0

    def test_no_command_prints_help_and_exits(self, capsys):
        with pytest.raises(SystemExit) as exc:
            main([])
        assert exc.value.code == 1

    def test_unknown_command_errors(self, capsys):
        with pytest.raises(SystemExit) as exc:
            main(["frobnicate"])
        # argparse rejects an invalid subcommand choice with exit code 2.
        assert exc.value.code == 2
