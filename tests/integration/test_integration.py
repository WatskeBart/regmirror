"""End-to-end integration tests using a real local registry:3 container.

Run with:
    pytest tests/integration/ -v

Requirements:
    - Podman installed and running
    - skopeo installed on the host
"""

from __future__ import annotations

import json
import subprocess

import pytest

from regmirror.__main__ import cmd_download, cmd_upload, cmd_sync, load_manifest

# A small public image to keep test runs fast (~700 KB compressed)
TEST_IMAGE = "busybox:1.36"

pytestmark = pytest.mark.integration


def _skopeo_available() -> bool:
    try:
        subprocess.run(["skopeo", "--version"], check=True, capture_output=True)
        return True
    except (FileNotFoundError, subprocess.CalledProcessError):
        return False


def _podman_available() -> bool:
    try:
        subprocess.run(["podman", "info"], check=True, capture_output=True)
        return True
    except (FileNotFoundError, subprocess.CalledProcessError):
        return False


skip_if_no_tools = pytest.mark.skipif(
    not (_skopeo_available() and _podman_available()),
    reason="skopeo and Podman must be installed",
)


@skip_if_no_tools
class TestDownloadUploadCycle:
    def _images_file(self, tmp_path, content=TEST_IMAGE):
        f = tmp_path / "images.txt"
        f.write_text(content + "\n")
        return f

    def _download_args(self, make_args, images_file, output_dir):
        return make_args(
            file=str(images_file),
            output=str(output_dir),
            src_tls_verify=True,
        )

    def _upload_args(self, make_args, tarballs_dir, registry):
        return make_args(
            dir=str(tarballs_dir),
            registry=registry,
            dest_tls_verify=False,  # local registry uses plain HTTP
        )

    def test_download_creates_tarball_and_manifest(self, tmp_path, make_args):
        images_file = self._images_file(tmp_path)
        tarballs = tmp_path / "tarballs"
        args = self._download_args(make_args, images_file, tarballs)

        result = cmd_download(args)

        assert result == 0
        manifest = load_manifest(tarballs)
        assert len(manifest) == 1
        entry = next(iter(manifest.values()))
        assert entry["original"] == TEST_IMAGE
        assert entry["digest"] is not None
        # The tarball file must exist on disk
        tarball_path = tarballs / next(iter(manifest.keys()))
        assert tarball_path.exists()

    def test_upload_to_local_registry(self, tmp_path, make_args, local_registry):
        images_file = self._images_file(tmp_path)
        tarballs = tmp_path / "tarballs"

        # Download first
        dl_args = self._download_args(make_args, images_file, tarballs)
        assert cmd_download(dl_args) == 0

        # Upload to local registry
        ul_args = self._upload_args(make_args, tarballs, local_registry)
        result = cmd_upload(ul_args)
        assert result == 0

        # Verify image is reachable in the local registry via skopeo inspect
        manifest = load_manifest(tarballs)
        entry = next(iter(manifest.values()))
        from regmirror.__main__ import rewrite_for_registry
        target_ref = rewrite_for_registry(entry, local_registry)
        inspect = subprocess.run(
            ["skopeo", "inspect", "--tls-verify=false", f"docker://{target_ref}"],
            capture_output=True,
        )
        assert inspect.returncode == 0, f"skopeo inspect failed: {inspect.stderr.decode()}"

    def test_sync_end_to_end(self, tmp_path, make_args, local_registry):
        images_file = self._images_file(tmp_path)
        tarballs = tmp_path / "tarballs"
        args = make_args(
            file=str(images_file),
            output=str(tarballs),
            registry=local_registry,
            src_tls_verify=True,
            dest_tls_verify=False,
            continue_on_error=False,
        )

        result = cmd_sync(args)
        assert result == 0

        manifest = load_manifest(tarballs)
        assert len(manifest) == 1

    def test_second_download_skips_unchanged(self, tmp_path, make_args):
        """Re-running download on an up-to-date tarball should skip without calling skopeo copy."""
        from unittest.mock import patch

        images_file = self._images_file(tmp_path)
        tarballs = tmp_path / "tarballs"

        # First download (real)
        args = self._download_args(make_args, images_file, tarballs)
        assert cmd_download(args) == 0

        # Second download — skopeo copy must NOT be called
        with patch("subprocess.run") as mock_run:
            # Allow skopeo inspect --raw (used by inspect_remote) to run for real
            # by only intercepting calls that start with ["skopeo", "copy", ...]
            original_run = subprocess.run

            def selective_mock(cmd, *a, **kw):
                if len(cmd) > 1 and cmd[1] == "copy":
                    raise AssertionError("skopeo copy should not be called on up-to-date image")
                return original_run(cmd, *a, **kw)

            mock_run.side_effect = selective_mock
            result = cmd_download(args)

        assert result == 0
