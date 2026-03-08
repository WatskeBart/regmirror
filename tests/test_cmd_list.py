"""Tests for cmd_list."""

from __future__ import annotations

import argparse

from regmirror.__main__ import cmd_list, save_manifest


class TestCmdList:
    def _args(self, tmp_path, registry=None):
        return argparse.Namespace(dir=str(tmp_path), registry=registry)

    def test_no_manifest_returns_1(self, tmp_path):
        result = cmd_list(self._args(tmp_path))
        assert result == 1

    def test_with_manifest_no_registry_shows_dash(self, tmp_path, sample_manifest, capsys):
        save_manifest(tmp_path, sample_manifest)
        result = cmd_list(self._args(tmp_path))
        assert result == 0
        out = capsys.readouterr().out
        assert "—" in out

    def test_with_manifest_and_registry_shows_target(self, tmp_path, sample_manifest, capsys):
        save_manifest(tmp_path, sample_manifest)
        result = cmd_list(self._args(tmp_path, registry="my.registry.tld"))
        assert result == 0
        out = capsys.readouterr().out
        assert "my.registry.tld" in out

    def test_original_ref_shown(self, tmp_path, sample_manifest, capsys):
        save_manifest(tmp_path, sample_manifest)
        cmd_list(self._args(tmp_path))
        out = capsys.readouterr().out
        assert "nginx:1.25" in out
