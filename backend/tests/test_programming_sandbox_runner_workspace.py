"""S8: sandbox workspace location (SANDBOX_WORK_DIR) and permissions readable by the sandbox uid."""

import os
import stat
import tempfile
from pathlib import Path

import pytest

from app.services import programming_sandbox_runner as runner_module
from app.services.programming_sandbox_runner import DockerSandboxRunner

FAKE_DOCKER = "/opt/fake/bin/docker"
CODE = "print(sum(map(int, input().split())))\n"


class _FakeStream:
    async def read(self, _size: int) -> bytes:
        return b""


class _FakeStdin:
    def write(self, _data: bytes) -> None:
        pass

    async def drain(self) -> None:
        pass

    def close(self) -> None:
        pass


class _FakeProcess:
    returncode = 0

    def __init__(self) -> None:
        self.stdin = _FakeStdin()
        self.stdout = _FakeStream()
        self.stderr = _FakeStream()

    async def wait(self) -> int:
        return 0

    def kill(self) -> None:
        pass


@pytest.fixture
def observed(monkeypatch):
    """Record argv and the mounted workspace state while the fake container 'runs'."""
    seen: dict = {}

    async def fake_exec(*argv, **_kwargs):
        mount = argv[argv.index("-v") + 1]
        host_dir = Path(mount.removesuffix(":/workspace:ro"))
        solution = host_dir / "solution.py"
        seen["argv"] = list(argv)
        seen["host_dir"] = host_dir
        seen["dir_mode"] = stat.S_IMODE(os.stat(host_dir).st_mode)
        seen["file_mode"] = stat.S_IMODE(os.stat(solution).st_mode)
        seen["content"] = solution.read_text(encoding="utf-8")
        return _FakeProcess()

    monkeypatch.setattr(runner_module.shutil, "which", lambda _name: FAKE_DOCKER)
    monkeypatch.setattr(runner_module.asyncio, "create_subprocess_exec", fake_exec)
    return seen


def _expected_argv(host_dir: Path) -> list[str]:
    return [
        FAKE_DOCKER,
        "run",
        "--rm",
        "--network=none",
        "--cpus=1",
        "--memory=128m",
        "--pids-limit=64",
        "--read-only",
        "--tmpfs=/tmp:rw,noexec,nosuid,size=16m",
        "--cap-drop=ALL",
        "--security-opt=no-new-privileges",
        "--user=65532:65532",
        "-v",
        f"{host_dir}:/workspace:ro",
        "-i",
        runner_module.settings.SANDBOX_DOCKER_IMAGE,
        "python",
        "/workspace/solution.py",
    ]


async def _run() -> None:
    result = await DockerSandboxRunner().run(
        code=CODE,
        stdin_data="2 3\n",
        time_limit_ms=1000,
        memory_limit_mb=128,
        max_output_bytes=4096,
    )
    assert result.exit_code == 0
    assert result.timed_out is False


async def test_workspace_is_created_inside_configured_sandbox_work_dir(observed, monkeypatch, tmp_path):
    monkeypatch.setattr(runner_module.settings, "SANDBOX_WORK_DIR", str(tmp_path))

    await _run()

    host_dir = observed["host_dir"]
    assert host_dir.parent == tmp_path
    assert host_dir.name.startswith("skillmatch-sandbox-")
    assert observed["argv"] == _expected_argv(host_dir)
    assert not host_dir.exists(), "the workspace must be removed after the run"
    assert list(tmp_path.iterdir()) == []


async def test_workspace_is_readable_by_the_sandbox_uid(observed, monkeypatch, tmp_path):
    monkeypatch.setattr(runner_module.settings, "SANDBOX_WORK_DIR", str(tmp_path))

    await _run()

    assert observed["dir_mode"] == 0o755
    assert observed["file_mode"] == 0o644
    assert observed["content"] == CODE


async def test_unset_sandbox_work_dir_keeps_system_temp_location(observed, monkeypatch):
    monkeypatch.setattr(runner_module.settings, "SANDBOX_WORK_DIR", None)

    await _run()

    host_dir = observed["host_dir"]
    assert host_dir.parent == Path(tempfile.gettempdir())
    assert host_dir.name.startswith("skillmatch-sandbox-")
    assert observed["argv"] == _expected_argv(host_dir)
    assert observed["dir_mode"] == 0o755
    assert observed["file_mode"] == 0o644
    assert observed["content"] == CODE
    assert not host_dir.exists()
