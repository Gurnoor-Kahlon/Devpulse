import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

spec = importlib.util.spec_from_file_location(
    "local_stack", Path(__file__).parents[1] / "local_stack.py"
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_init_is_idempotent_and_does_not_print_generated_credential(tmp_path, capsys):
    path = tmp_path / "compose.env"
    module.initialize(path)
    original = path.read_text()
    module.initialize(path)
    assert path.read_text() == original
    assert original.partition("=")[2].strip() not in capsys.readouterr().out


def test_backup_refuses_existing_file(tmp_path):
    path = tmp_path / "saved.dump"
    path.write_bytes(b"earlier backup")
    with pytest.raises(FileExistsError):
        module.backup(None, "devpulse", path)
    assert path.read_bytes() == b"earlier backup"


def test_failed_backup_removes_only_new_partial_file(tmp_path):
    class Failed:
        def command(self, *args, **kwargs):
            kwargs["stdout"].write(b"partial")
            raise module.StackError("unavailable")

    path = tmp_path / "new.dump"
    with pytest.raises(module.StackError):
        module.backup(Failed(), "devpulse", path)
    assert not path.exists()


@pytest.mark.parametrize(
    "name",
    ["devpulse", "devpulse_test", "postgres", "devpulse_restore_x_test; DROP DATABASE devpulse"],
)
def test_restore_never_targets_application_or_untrusted_database_names(tmp_path, name):
    with pytest.raises(module.StackError):
        module.restore(None, tmp_path / "missing.dump", name)


def test_restore_refuses_existing_database_before_any_mutation(tmp_path):
    calls = []
    stack = SimpleNamespace(sql=lambda *args: calls.append(args) or "1")
    with pytest.raises(module.StackError, match="already exists"):
        module.restore(stack, tmp_path / "missing.dump", "devpulse_restore_old_test")
    assert len(calls) == 1 and calls[0][1].startswith("SELECT")


def test_restore_rejects_invalid_archive_before_database_creation(tmp_path):
    calls = []
    stack = SimpleNamespace(sql=lambda *args: calls.append(args) or "")
    path = tmp_path / "invalid.dump"
    path.write_bytes(b"not a backup")
    with pytest.raises(module.StackError, match="custom-format"):
        module.restore(stack, path, "devpulse_restore_new_test")
    assert len(calls) == 1 and calls[0][1].startswith("SELECT")


def test_restore_child_receives_archive_from_byte_zero(tmp_path, monkeypatch):
    import os

    calls = []
    stack = SimpleNamespace(
        sql=lambda *args: calls.append(args) or "", prefix=["docker", "compose"], env={}
    )
    archive = tmp_path / "archive.dump"
    archive.write_bytes(b"PGDMP" + b"payload" * 1000)

    def child(command, **kwargs):
        assert os.read(kwargs["stdin"].fileno(), 5) == b"PGDMP"
        assert "--single-transaction" in command and "--exit-on-error" in command
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(module.subprocess, "run", child)
    module.restore(stack, archive, "devpulse_restore_new_test")
    assert calls[-1][1] == 'CREATE DATABASE "devpulse_restore_new_test" OWNER devpulse'
