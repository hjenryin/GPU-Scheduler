"""
True integration tests for CLI commands using Click's CliRunner and a live head node.
"""

import os
import json
import socket
import time

import pytest
from click.testing import CliRunner

from scheduler.cli.main import cli
from scheduler.core.config import Config, HeadConfig, WorkerConfig, StorageConfig
from scheduler.head.orchestrator import Orchestrator


def _find_free_port() -> int:
    s = socket.socket()
    s.bind(("", 0))
    port = s.getsockname()[1]
    s.close()
    return port


@pytest.fixture(scope="module")
def cli_runner():
    return CliRunner()


@pytest.fixture(scope="module")
def live_head(tmp_path_factory):
    """Start a real head node (uvicorn in thread) and set up an isolated HOME with config."""
    tmp_home = tmp_path_factory.mktemp("home")
    os.environ["HOME"] = str(tmp_home)

    # Create ~/.scheduler directory
    scheduler_dir = tmp_home / ".scheduler"
    scheduler_dir.mkdir(parents=True, exist_ok=True)

    # Allocate free port and temp data dir
    port = _find_free_port()
    data_dir = tmp_home / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    # Write config file so CLI discovers the correct address
    config_path = scheduler_dir / "config.yaml"
    config = Config(
        address=f"localhost:{port}",
        head=HeadConfig(port=port, scheduling_interval=1, heartbeat_timeout=10),
        worker=WorkerConfig(
            temp_dir=str(tmp_home / "tmp"),
            log_dir=str(tmp_home / "logs"),
            work_dir=str(tmp_home / "work"),
        ),
        storage=StorageConfig(backend="file", data_dir=str(data_dir)),
    )

    # Dump config YAML
    import yaml

    with open(config_path, "w") as f:
        yaml.safe_dump(config.to_dict(), f)

    # Start orchestrator
    orchestrator = Orchestrator(config)
    orchestrator.start()

    # Give API server time to start
    time.sleep(1.5)

    try:
        yield {"port": port, "home": str(tmp_home), "config": config, "orchestrator": orchestrator}
    finally:
        orchestrator.stop(graceful=True)
        time.sleep(0.5)


class TestCLIIntegration:
    def test_submit_and_list_jobs_json(self, cli_runner, live_head, tmp_path):
        # Create a simple script file
        script_path = tmp_path / "echo.py"
        script_path.write_text("print('hello')\n")

        # Submit job (async so we don't wait)
        result = cli_runner.invoke(
            cli,
            ["submit", str(script_path), "--req", "1", "--async"],
        )

        assert result.exit_code == 0, result.output
        assert "Job submitted successfully" in result.output

        # List jobs as JSON
        result = cli_runner.invoke(cli, ["jobs", "--format", "json"])
        assert result.exit_code == 0, result.output

        data = json.loads(result.output)
        assert isinstance(data, list)
        assert len(data) >= 1
        # Verify at least one job references our script name
        assert any("echo.py" in (j.get("script") or "") for j in data)

    def test_cancel_job(self, cli_runner, live_head, tmp_path):
        # Create script and submit
        script = tmp_path / "sleep.py"
        script.write_text("import time\ntime.sleep(1)\n")
        submit = cli_runner.invoke(cli, ["submit", str(script), "--req", "1", "--async"]) 
        assert submit.exit_code == 0, submit.output

        # Extract Job ID from output
        job_line = next((ln for ln in submit.output.splitlines() if ln.startswith("Job ID:")), None)
        assert job_line is not None
        job_id = job_line.split(":", 1)[1].strip()

        # Cancel the job
        cancel = cli_runner.invoke(cli, ["cancel", job_id])
        assert cancel.exit_code == 0, cancel.output

    def test_jobs_limit_and_table(self, cli_runner):
        # Just verify command wires end-to-end with live server
        res = cli_runner.invoke(cli, ["jobs", "--format", "table", "--limit", "5"]) 
        assert res.exit_code == 0, res.output


