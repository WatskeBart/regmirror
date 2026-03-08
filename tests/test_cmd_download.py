"""Tests for cmd_download (subprocess mocked)."""

from __future__ import annotations

import json
import subprocess
from unittest.mock import MagicMock, patch

import pytest

from regmirror.__main__ import RemoteInfo, cmd_download, load_manifest


DIGEST_A = "sha256:" + "a" * 64
DIGEST_B = "sha256:" + "b" * 64


def _successful_run(*args, **kwargs):
    return MagicMock()


def _failing_run(*args, **kwargs):
    raise subprocess.CalledProcessError(1, "skopeo")


def _remote_info(digest=DIGEST_A, sigs=False):
    return RemoteInfo(digest=digest, has_embedded_signatures=sigs)


class TestCmdDownload:
    def _run(self, tmp_path, images_content, make_args, **extra):
        images_file = tmp_path / "images.txt"
        images_file.write_text(images_content)
        args = make_args(
            file=str(images_file),
            output=str(tmp_path / "tarballs"),
            **extra,
        )
        return cmd_download(args)

    def test_missing_images_file_returns_1(self, tmp_path, make_args):
        args = make_args(file=str(tmp_path / "missing.txt"), output=str(tmp_path / "out"))
        assert cmd_download(args) == 1

    def test_empty_images_file_returns_1(self, tmp_path, make_args):
        assert self._run(tmp_path, "# comment only\n\n", make_args) == 1

    def test_fresh_download_success(self, tmp_path, make_args):
        with (
            patch("subprocess.run", side_effect=_successful_run),
            patch("regmirror.__main__.inspect_remote", return_value=_remote_info()),
        ):
            result = self._run(tmp_path, "nginx:1.25\n", make_args)
        assert result == 0
        manifest = load_manifest(tmp_path / "tarballs")
        assert len(manifest) == 1

    def test_manifest_written_after_download(self, tmp_path, make_args):
        with (
            patch("subprocess.run", side_effect=_successful_run),
            patch("regmirror.__main__.inspect_remote", return_value=_remote_info()),
        ):
            self._run(tmp_path, "nginx:1.25\n", make_args)
        manifest = load_manifest(tmp_path / "tarballs")
        entry = next(iter(manifest.values()))
        assert entry["original"] == "nginx:1.25"
        assert entry["digest"] == DIGEST_A

    def test_digest_pinned_existing_tarball_skipped(self, tmp_path, make_args):
        digest_hex = "a" * 64
        ref = f"nginx@sha256:{digest_hex}"
        tarballs = tmp_path / "tarballs"
        tarballs.mkdir()
        # Create a fake tarball so it "exists"
        from regmirror.__main__ import ref_to_filename
        (tarballs / ref_to_filename(ref)).touch()

        with patch("subprocess.run") as mock_run:
            result = self._run(tmp_path, f"{ref}\n", make_args)

        mock_run.assert_not_called()
        assert result == 0

    def test_tag_based_up_to_date_skipped(self, tmp_path, make_args):
        tarballs = tmp_path / "tarballs"
        tarballs.mkdir()
        from regmirror.__main__ import ref_to_filename, save_manifest
        filename = ref_to_filename("nginx:1.25")
        (tarballs / filename).touch()
        save_manifest(tarballs, {
            filename: {
                "original": "nginx:1.25",
                "registry": "docker.io",
                "image": "library/nginx",
                "tag": "1.25",
                "digest": DIGEST_A,
            }
        })

        with (
            patch("subprocess.run") as mock_run,
            patch("regmirror.__main__.inspect_remote", return_value=_remote_info(DIGEST_A)),
        ):
            result = self._run(tmp_path, "nginx:1.25\n", make_args)

        mock_run.assert_not_called()
        assert result == 0

    def test_tag_based_outdated_redownloads(self, tmp_path, make_args):
        tarballs = tmp_path / "tarballs"
        tarballs.mkdir()
        from regmirror.__main__ import ref_to_filename, save_manifest
        filename = ref_to_filename("nginx:1.25")
        (tarballs / filename).touch()
        save_manifest(tarballs, {
            filename: {
                "original": "nginx:1.25",
                "registry": "docker.io",
                "image": "library/nginx",
                "tag": "1.25",
                "digest": DIGEST_A,
            }
        })

        with (
            patch("subprocess.run", side_effect=_successful_run) as mock_run,
            patch("regmirror.__main__.inspect_remote", return_value=_remote_info(DIGEST_B)),
        ):
            result = self._run(tmp_path, "nginx:1.25\n", make_args)

        mock_run.assert_called_once()
        assert result == 0

    def test_remote_inspect_failure_skips(self, tmp_path, make_args):
        tarballs = tmp_path / "tarballs"
        tarballs.mkdir()
        from regmirror.__main__ import ref_to_filename
        filename = ref_to_filename("nginx:1.25")
        (tarballs / filename).touch()

        with (
            patch("subprocess.run") as mock_run,
            patch("regmirror.__main__.inspect_remote", return_value=RemoteInfo(None, False)),
        ):
            result = self._run(tmp_path, "nginx:1.25\n", make_args)

        mock_run.assert_not_called()
        assert result == 0

    def test_force_redownloads(self, tmp_path, make_args):
        tarballs = tmp_path / "tarballs"
        tarballs.mkdir()
        from regmirror.__main__ import ref_to_filename
        (tarballs / ref_to_filename("nginx:1.25")).touch()

        with (
            patch("subprocess.run", side_effect=_successful_run) as mock_run,
            patch("regmirror.__main__.inspect_remote", return_value=_remote_info()),
        ):
            result = self._run(tmp_path, "nginx:1.25\n", make_args, force=True)

        mock_run.assert_called_once()
        assert result == 0

    def test_skopeo_failure_returns_1(self, tmp_path, make_args):
        with (
            patch("subprocess.run", side_effect=_failing_run),
            patch("regmirror.__main__.inspect_remote", return_value=_remote_info()),
        ):
            result = self._run(tmp_path, "nginx:1.25\n", make_args)
        assert result == 1

    def test_comments_and_blank_lines_ignored(self, tmp_path, make_args):
        content = "# header\n\nnginx:1.25\n# another comment\n\n"
        with (
            patch("subprocess.run", side_effect=_successful_run),
            patch("regmirror.__main__.inspect_remote", return_value=_remote_info()),
        ):
            result = self._run(tmp_path, content, make_args)
        manifest = load_manifest(tmp_path / "tarballs")
        assert len(manifest) == 1
        assert result == 0
