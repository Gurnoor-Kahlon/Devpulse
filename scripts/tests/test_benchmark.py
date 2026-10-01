"""Safety boundaries and evidence calculations, without Docker or a database."""

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "backend"))
import benchmark  # noqa: E402

spec = importlib.util.spec_from_file_location(
    "benchmark_workload", ROOT / "containers/benchmark/workload.py"
)
workload = importlib.util.module_from_spec(spec)
spec.loader.exec_module(workload)


def settings(environment="test", database="devpulse_test", host="postgres"):
    return SimpleNamespace(
        environment=environment,
        database_url=SimpleNamespace(
            get_secret_value=lambda: f"postgresql+psycopg://fixture@{host}/{database}"
        ),
    )


@pytest.mark.parametrize(
    "config,empty",
    [
        (settings(environment="production"), True),
        (settings(database="devpulse"), True),
        (settings(host="localhost"), True),
        (settings(), False),
    ],
)
def test_guard_rejects_non_disposable_or_populated_database(config, empty):
    with pytest.raises(ValueError, match="empty disposable"):
        workload.guard(config, empty)


def test_nearest_rank_percentiles_are_not_averages_or_fabricated_when_empty():
    assert workload.distribution([])["p95_ms"] is None
    result = workload.distribution(list(range(1, 101)))
    assert result == {"samples": 100, "p50_ms": 50, "p95_ms": 95, "max_ms": 100}


def args(tmp_path):
    return SimpleNamespace(
        env_file=tmp_path / "compose.env",
        output=tmp_path / "report.json",
        web_port=23000,
        mail_port=28025,
        rounds=1,
    )


def test_existing_evidence_is_never_overwritten(tmp_path):
    options = args(tmp_path)
    options.output.write_text("previous evidence")
    with pytest.raises(FileExistsError):
        benchmark.run(options)
    assert options.output.read_text() == "previous evidence"


def test_existing_project_is_never_cleaned_up(tmp_path, monkeypatch):
    calls = []

    class Existing:
        prefix = []

        def __init__(self, *args, **kwargs):
            pass

        def command(self, *args):
            calls.append(args)
            return "existing-container"

    monkeypatch.setattr(benchmark, "Stack", Existing)
    with pytest.raises(benchmark.StackError, match="existing project"):
        benchmark.run(args(tmp_path))
    assert len(calls) == 1


def test_failed_startup_cleans_only_new_project_and_saves_failure(tmp_path, monkeypatch):
    import json

    calls = []

    class Failing:
        prefix = []

        def __init__(self, project, *args, **kwargs):
            assert project.startswith("devpulse-benchmark-")

        def command(self, *args):
            calls.append(args)
            if args[0] == "up":
                raise benchmark.StackError("fixture unavailable")
            return ""

    monkeypatch.setattr(benchmark, "Stack", Failing)
    options = args(tmp_path)
    with pytest.raises(benchmark.StackError, match="fixture unavailable"):
        benchmark.run(options)
    assert calls[-1] == ("down", "--volumes", "--remove-orphans", "--timeout", "30")
    result = json.loads(options.output.read_text())
    assert result["disposable_project_removed"]
    assert not result["passed"] and not result["milestone_19_volume_met"]


def test_nonzero_worker_exit_cannot_leave_a_passing_report(tmp_path, monkeypatch):
    import io
    import json

    class Disposable:
        prefix = []
        env = {}

        def __init__(self, *args, **kwargs):
            pass

        def command(self, *args):
            return ""

    class Child:
        stdout = io.StringIO('{"report":{"passed":true,"milestone_19_volume_met":true}}\n')

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def wait(self):
            return 1

    monkeypatch.setattr(benchmark, "Stack", Disposable)
    monkeypatch.setattr(benchmark, "docker_metadata", lambda: {})
    monkeypatch.setattr(benchmark, "source_fingerprint", lambda: {})
    monkeypatch.setattr(benchmark.subprocess, "Popen", lambda *args, **kwargs: Child())
    monkeypatch.setattr(
        benchmark.subprocess, "run", lambda *args, **kwargs: SimpleNamespace(stdout="image-id")
    )
    options = args(tmp_path)
    with pytest.raises(benchmark.StackError, match="correctness"):
        benchmark.run(options)
    result = json.loads(options.output.read_text())
    assert result["disposable_project_removed"]
    assert not result["passed"] and not result["milestone_19_volume_met"]


def test_fixture_counts_only_real_probe_responses():
    import threading
    from http.server import ThreadingHTTPServer

    import httpx

    fixture_spec = importlib.util.spec_from_file_location(
        "benchmark_fixture", ROOT / "containers/benchmark/server.py"
    )
    fixture = importlib.util.module_from_spec(fixture_spec)
    fixture_spec.loader.exec_module(fixture)
    with ThreadingHTTPServer(("127.0.0.1", 0), fixture.Handler) as server:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with httpx.Client(
                base_url=f"http://127.0.0.1:{server.server_port}", timeout=2, trust_env=False
            ) as client:
                assert client.get("/health").status_code == 200
                assert client.get("/stats").json()["completed_responses"] == 0
                assert client.get("/missing").status_code == 404
                assert client.get("/stats").json()["completed_responses"] == 0
                for _ in range(2):
                    response = client.get("/probe")
                    assert response.status_code == 200
                    assert int(response.headers["content-length"]) == 36
                assert client.get("/stats").json()["completed_responses"] == 2
        finally:
            server.shutdown()
            thread.join(timeout=3)
