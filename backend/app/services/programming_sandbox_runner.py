import asyncio
import shutil
import tempfile
from pathlib import Path
from dataclasses import dataclass

from app.core.config import settings


@dataclass(frozen=True)
class SandboxRunResult:
    stdout: str
    stderr: str
    exit_code: int | None
    timed_out: bool
    output_limited: bool


class SandboxUnavailableError(RuntimeError):
    pass


class DockerSandboxRunner:
    """Execute one Python program in a disposable, network-disabled container."""

    async def run(
        self,
        *,
        code: str,
        stdin_data: str,
        time_limit_ms: int,
        memory_limit_mb: int,
        max_output_bytes: int,
    ) -> SandboxRunResult:
        binary = shutil.which(settings.SANDBOX_DOCKER_BINARY)
        if binary is None:
            raise SandboxUnavailableError(
                "El sandbox de programación no está disponible en este servidor."
            )

        # SANDBOX_WORK_DIR permite que el daemon Docker (por ejemplo, dind)
        # acceda a la misma ruta mediante un volumen compartido.
        with tempfile.TemporaryDirectory(
            prefix="skillmatch-sandbox-",
            dir=settings.SANDBOX_WORK_DIR,
        ) as directory:
            root = Path(directory)
            solution = root / "solution.py"
            solution.write_text(code, encoding="utf-8")

            # Acceso de solo lectura para el usuario sin privilegios (65532).
            root.chmod(0o755)
            solution.chmod(0o644)

            command = [
                binary,
                "run",
                "--rm",
                "--network=none",
                "--cpus=1",
                f"--memory={memory_limit_mb}m",
                "--pids-limit=64",
                "--read-only",
                "--tmpfs=/tmp:rw,noexec,nosuid,size=16m",
                "--cap-drop=ALL",
                "--security-opt=no-new-privileges",
                "--user=65532:65532",
                "-v",
                f"{root}:/workspace:ro",
                "-i",
                settings.SANDBOX_DOCKER_IMAGE,
                "python",
                "/workspace/solution.py",
            ]

            process = await asyncio.create_subprocess_exec(
                *command,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout_task = asyncio.create_task(
                self._read_bounded(process.stdout, max_output_bytes)
            )
            stderr_task = asyncio.create_task(
                self._read_bounded(process.stderr, max_output_bytes)
            )

            try:
                if process.stdin is not None:
                    process.stdin.write(stdin_data.encode("utf-8"))
                    await process.stdin.drain()
                    process.stdin.close()

                await asyncio.wait_for(
                    process.wait(),
                    timeout=time_limit_ms / 1000,
                )

                stdout, stdout_limited = await stdout_task
                stderr, stderr_limited = await stderr_task

                return SandboxRunResult(
                    stdout=stdout,
                    stderr=stderr,
                    exit_code=process.returncode,
                    timed_out=False,
                    output_limited=stdout_limited or stderr_limited,
                )

            except asyncio.TimeoutError:
                process.kill()
                await process.wait()

                for task in (stdout_task, stderr_task):
                    task.cancel()

                await asyncio.gather(
                    stdout_task,
                    stderr_task,
                    return_exceptions=True,
                )

                return SandboxRunResult(
                    stdout="",
                    stderr="Tiempo de ejecución excedido.",
                    exit_code=None,
                    timed_out=True,
                    output_limited=False,
                )

    @staticmethod
    async def _read_bounded(
        stream: asyncio.StreamReader | None,
        limit: int,
    ) -> tuple[str, bool]:
        if stream is None:
            return "", False

        data = bytearray()
        limited = False

        while True:
            chunk = await stream.read(
                min(16_384, max(1, limit + 1 - len(data)))
            )

            if not chunk:
                break

            if len(data) < limit:
                remaining = limit - len(data)
                data.extend(chunk[:remaining])

                if len(chunk) > remaining:
                    limited = True
            else:
                limited = True

        return data.decode("utf-8", errors="replace"), limited