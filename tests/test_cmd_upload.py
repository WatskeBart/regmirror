"""Tests for cmd_upload (subprocess mocked)."""

from __future__ import annotations

import subprocess
from unittest.mock import patch

from regmirror.__main__ import cmd_upload, save_manifest


DIGEST_A = "sha256:" + "a" * 64

MANIFEST = {
    "nginx-1.25.tar": {
        "original": "nginx:1.25",
        "registry": "docker.io",
        "image": "library/nginx",
        "tag": "1.25",
        "digest": DIGEST_A,
    }
}


class TestCmdUpload:
    def _args(self, make_args, tarballs_dir, registry="my.registry.tld", **extra):
        return make_args(dir=str(tarballs_dir), registry=registry, **extra)

    def test_no_manifest_returns_1(self, tmp_path, make_args):
        args = self._args(make_args, tmp_path)
        assert cmd_upload(args) == 1

    def test_missing_tarball_logged_and_errors(self, tmp_path, make_args):
        save_manifest(tmp_path, MANIFEST)
        # tarball file NOT created
        args = self._args(make_args, tmp_path)
        with patch("subprocess.run") as mock_run:
            result = cmd_upload(args)
        mock_run.assert_not_called()
        assert result == 1

    def test_successful_upload_returns_0(self, tmp_path, make_args):
        save_manifest(tmp_path, MANIFEST)
        (tmp_path / "nginx-1.25.tar").touch()
        args = self._args(make_args, tmp_path)
        with patch("subprocess.run"):
            result = cmd_upload(args)
        assert result == 0

    def test_skopeo_failure_returns_1(self, tmp_path, make_args):
        save_manifest(tmp_path, MANIFEST)
        (tmp_path / "nginx-1.25.tar").touch()
        args = self._args(make_args, tmp_path)
        with patch("subprocess.run", side_effect=subprocess.CalledProcessError(1, "skopeo")):
            result = cmd_upload(args)
        assert result == 1

    def test_dest_tls_verify_false_forwarded(self, tmp_path, make_args):
        save_manifest(tmp_path, MANIFEST)
        (tmp_path / "nginx-1.25.tar").touch()
        args = self._args(make_args, tmp_path, dest_tls_verify=False)
        with patch("subprocess.run") as mock_run:
            cmd_upload(args)
        cmd = mock_run.call_args[0][0]
        assert "--dest-tls-verify=false" in cmd

    def test_dest_creds_forwarded(self, tmp_path, make_args):
        save_manifest(tmp_path, MANIFEST)
        (tmp_path / "nginx-1.25.tar").touch()
        args = self._args(make_args, tmp_path, dest_creds="user:pass")
        with patch("subprocess.run") as mock_run:
            cmd_upload(args)
        cmd = mock_run.call_args[0][0]
        assert "--dest-creds" in cmd
        assert "user:pass" in cmd

    def test_remove_signatures_forwarded(self, tmp_path, make_args):
        save_manifest(tmp_path, MANIFEST)
        (tmp_path / "nginx-1.25.tar").touch()
        args = self._args(make_args, tmp_path, remove_signatures=True)
        with patch("subprocess.run") as mock_run:
            cmd_upload(args)
        cmd = mock_run.call_args[0][0]
        assert "--remove-signatures" in cmd

    def test_target_ref_rewritten(self, tmp_path, make_args):
        save_manifest(tmp_path, MANIFEST)
        (tmp_path / "nginx-1.25.tar").touch()
        args = self._args(make_args, tmp_path, registry="my.registry.tld")
        with patch("subprocess.run") as mock_run:
            cmd_upload(args)
        cmd = mock_run.call_args[0][0]
        target_arg = next(a for a in cmd if "my.registry.tld" in a)
        # MANIFEST has a digest so the target uses @sha256:... not :1.25
        assert "dockerio/library/nginx@sha256:" in target_arg

    def test_authfile_forwarded(self, tmp_path, make_args):
        save_manifest(tmp_path, MANIFEST)
        (tmp_path / "nginx-1.25.tar").touch()
        args = self._args(make_args, tmp_path, authfile="/etc/auth.json")
        with patch("subprocess.run") as mock_run:
            cmd_upload(args)
        cmd = mock_run.call_args[0][0]
        assert "--dest-authfile" in cmd
        assert "/etc/auth.json" in cmd
