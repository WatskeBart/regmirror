"""Tests for inspect_remote (subprocess mocked)."""

from __future__ import annotations

import hashlib
import json
import subprocess
from unittest.mock import MagicMock, patch

import pytest

from regmirror.__main__ import RemoteInfo, inspect_remote


SIMPLE_MANIFEST = {"schemaVersion": 2, "mediaType": "application/vnd.docker.distribution.manifest.v2+json"}
SIGNED_MANIFEST = {**SIMPLE_MANIFEST, "signatures": [{"protected": "abc"}]}


def _make_result(manifest: dict) -> MagicMock:
    raw = json.dumps(manifest).encode()
    mock = MagicMock()
    mock.stdout = raw
    return mock


class TestInspectRemote:
    def test_returns_digest_on_success(self, make_args):
        raw = json.dumps(SIMPLE_MANIFEST).encode()
        expected_digest = "sha256:" + hashlib.sha256(raw).hexdigest()
        with patch("subprocess.run", return_value=_make_result(SIMPLE_MANIFEST)) as mock_run:
            result = inspect_remote("nginx:latest", make_args())
        assert result.digest == expected_digest
        assert result.has_embedded_signatures is False

    def test_detects_embedded_signatures(self, make_args):
        with patch("subprocess.run", return_value=_make_result(SIGNED_MANIFEST)):
            result = inspect_remote("nginx:latest", make_args())
        assert result.has_embedded_signatures is True

    def test_called_process_error_returns_none(self, make_args):
        with patch("subprocess.run", side_effect=subprocess.CalledProcessError(1, "skopeo")):
            result = inspect_remote("nginx:latest", make_args())
        assert result == RemoteInfo(digest=None, has_embedded_signatures=False)

    def test_json_decode_error_returns_none(self, make_args):
        mock = MagicMock()
        mock.stdout = b"not-json"
        with patch("subprocess.run", return_value=mock):
            result = inspect_remote("nginx:latest", make_args())
        assert result == RemoteInfo(digest=None, has_embedded_signatures=False)

    def test_src_tls_verify_false_forwarded(self, make_args):
        with patch("subprocess.run", return_value=_make_result(SIMPLE_MANIFEST)) as mock_run:
            inspect_remote("nginx:latest", make_args(src_tls_verify=False))
        cmd = mock_run.call_args[0][0]
        assert "--tls-verify=false" in cmd

    def test_src_tls_verify_true_forwarded(self, make_args):
        with patch("subprocess.run", return_value=_make_result(SIMPLE_MANIFEST)) as mock_run:
            inspect_remote("nginx:latest", make_args(src_tls_verify=True))
        cmd = mock_run.call_args[0][0]
        assert "--tls-verify=true" in cmd

    def test_src_creds_forwarded(self, make_args):
        with patch("subprocess.run", return_value=_make_result(SIMPLE_MANIFEST)) as mock_run:
            inspect_remote("nginx:latest", make_args(src_creds="user:pass"))
        cmd = mock_run.call_args[0][0]
        assert "--creds" in cmd
        assert "user:pass" in cmd

    def test_authfile_forwarded(self, make_args):
        with patch("subprocess.run", return_value=_make_result(SIMPLE_MANIFEST)) as mock_run:
            inspect_remote("nginx:latest", make_args(authfile="/path/auth.json"))
        cmd = mock_run.call_args[0][0]
        assert "--authfile" in cmd
        assert "/path/auth.json" in cmd

    def test_target_prefixed_with_docker_transport(self, make_args):
        with patch("subprocess.run", return_value=_make_result(SIMPLE_MANIFEST)) as mock_run:
            inspect_remote("nginx:latest", make_args())
        cmd = mock_run.call_args[0][0]
        assert "docker://nginx:latest" in cmd
