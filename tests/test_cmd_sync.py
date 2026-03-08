"""Tests for cmd_sync (mocked cmd_download + cmd_upload)."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from regmirror.__main__ import cmd_sync


class TestCmdSync:
    def _args(self, make_args, tmp_path, **extra):
        images_file = tmp_path / "images.txt"
        images_file.write_text("nginx:1.25\n")
        return make_args(
            file=str(images_file),
            output=str(tmp_path / "tarballs"),
            registry="my.registry.tld",
            **extra,
        )

    def test_both_succeed_returns_0(self, tmp_path, make_args):
        args = self._args(make_args, tmp_path)
        with (
            patch("regmirror.__main__.cmd_download", return_value=0) as mock_dl,
            patch("regmirror.__main__.cmd_upload", return_value=0) as mock_ul,
        ):
            result = cmd_sync(args)
        assert result == 0
        mock_dl.assert_called_once()
        mock_ul.assert_called_once()

    def test_download_failure_aborts_upload(self, tmp_path, make_args):
        args = self._args(make_args, tmp_path, continue_on_error=False)
        with (
            patch("regmirror.__main__.cmd_download", return_value=1),
            patch("regmirror.__main__.cmd_upload", return_value=0) as mock_ul,
        ):
            result = cmd_sync(args)
        assert result == 1
        mock_ul.assert_not_called()

    def test_download_failure_with_continue_on_error_proceeds(self, tmp_path, make_args):
        args = self._args(make_args, tmp_path, continue_on_error=True)
        with (
            patch("regmirror.__main__.cmd_download", return_value=1),
            patch("regmirror.__main__.cmd_upload", return_value=0) as mock_ul,
        ):
            result = cmd_sync(args)
        mock_ul.assert_called_once()

    def test_output_dir_passed_to_upload_as_dir(self, tmp_path, make_args):
        tarballs = str(tmp_path / "tarballs")
        args = self._args(make_args, tmp_path)
        with (
            patch("regmirror.__main__.cmd_download", return_value=0),
            patch("regmirror.__main__.cmd_upload", return_value=0) as mock_ul,
        ):
            cmd_sync(args)
        # cmd_sync sets args.dir = args.output before calling upload
        assert args.dir == args.output
