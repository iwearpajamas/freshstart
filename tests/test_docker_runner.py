"""DockerExecRunner unit tests using a fake Popen."""

import subprocess

from freshstart.docker.runner import DockerExecRunner, OutputCollector


class FakeStream:
    def __init__(self, data=""):
        self._data = data

    def read(self, n=-1):
        if n is None or n < 0:
            n = len(self._data)
        chunk = self._data[:n]
        self._data = self._data[n:]
        return chunk

    def close(self):
        pass


class FakePopen:
    def __init__(self, stdout_data="", stderr_data="", timeout=False, returncode=0):
        self.stdout = FakeStream(stdout_data)
        self.stderr = FakeStream(stderr_data)
        self.returncode = None
        self._timeout = timeout
        self._rc = returncode

    def wait(self, timeout=None):
        if self._timeout:
            raise subprocess.TimeoutExpired(cmd="docker exec", timeout=timeout)
        self.returncode = self._rc
        return self._rc

    def kill(self):
        self.returncode = -9


class TestOutputCollector:
    def test_collects_text(self):
        collector = OutputCollector(100)
        collector.append("hello")
        collector.append(" world")
        assert collector.text == "hello world"
        assert collector.truncated is False

    def test_truncates_over_limit(self):
        collector = OutputCollector(5)
        collector.append("hello world")
        assert collector._kept == 5
        assert collector.truncated is True
        assert "output truncated" in collector.text

    def test_empty_appends(self):
        collector = OutputCollector(10)
        collector.append("")
        assert collector.text == ""


class TestDockerExecRunner:
    def test_run_returns_exit_code_and_output(self):
        from unittest import mock

        fake = FakePopen(stdout_data="hello stdout\n")
        with mock.patch("freshstart.docker.runner.subprocess.Popen", return_value=fake):
            runner = DockerExecRunner()
            result = runner.run("cid", ["echo", "hi"], "/workspace", 10, 1000)
        assert result.returncode == 0
        assert "hello stdout" in result.stdout
        assert result.timed_out is False
        assert result.error is None

    def test_run_timeout(self):
        from unittest import mock

        fake = FakePopen(timeout=True)
        with mock.patch("freshstart.docker.runner.subprocess.Popen", return_value=fake):
            runner = DockerExecRunner()
            result = runner.run("cid", ["sleep", "60"], "/workspace", 1, 1000)
        assert result.timed_out is True
        assert result.error is not None
        assert "timed out" in result.error

    def test_run_nonzero_exit(self):
        from unittest import mock

        fake = FakePopen(stdout_data="", returncode=3)
        with mock.patch("freshstart.docker.runner.subprocess.Popen", return_value=fake):
            runner = DockerExecRunner()
            result = runner.run("cid", ["false"], "/workspace", 10, 1000)
        assert result.returncode == 3
        assert result.timed_out is False
