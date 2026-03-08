"""Tests for run_skopeo (subprocess mocked)."""

from __future__ import annotations

import subprocess
from unittest.mock import patch

from regmirror.__main__ import run_skopeo


class TestRunSkopeo:
    def test_success_returns_true(self):
        with patch("subprocess.run") as mock_run:
            result = run_skopeo(["copy", "src", "dst"])
        assert result is True
        mock_run.assert_called_once()

    def test_failure_returns_false(self):
        with patch("subprocess.run", side_effect=subprocess.CalledProcessError(1, "skopeo")):
            result = run_skopeo(["copy", "src", "dst"])
        assert result is False

    def test_dry_run_skips_subprocess(self):
        with patch("subprocess.run") as mock_run:
            result = run_skopeo(["copy", "src", "dst"], dry_run=True)
        assert result is True
        mock_run.assert_not_called()

    def test_skopeo_prepended_to_args(self):
        with patch("subprocess.run") as mock_run:
            run_skopeo(["copy", "src", "dst"])
        cmd = mock_run.call_args[0][0]
        assert cmd[0] == "skopeo"
        assert cmd[1] == "copy"
