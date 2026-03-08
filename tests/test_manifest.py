"""Tests for load_manifest and save_manifest."""

from __future__ import annotations

import json

from regmirror.__main__ import load_manifest, save_manifest


class TestLoadManifest:
    def test_missing_file_returns_empty_dict(self, tmp_path):
        result = load_manifest(tmp_path)
        assert result == {}

    def test_loads_existing_file(self, tmp_path, sample_manifest):
        manifest_path = tmp_path / "manifest.json"
        manifest_path.write_text(json.dumps(sample_manifest))
        result = load_manifest(tmp_path)
        assert result == sample_manifest


class TestSaveManifest:
    def test_creates_manifest_file(self, tmp_path, sample_manifest):
        save_manifest(tmp_path, sample_manifest)
        assert (tmp_path / "manifest.json").exists()

    def test_round_trip(self, tmp_path, sample_manifest):
        save_manifest(tmp_path, sample_manifest)
        loaded = load_manifest(tmp_path)
        assert loaded == sample_manifest

    def test_file_is_valid_json_with_indent(self, tmp_path, sample_manifest):
        save_manifest(tmp_path, sample_manifest)
        raw = (tmp_path / "manifest.json").read_text()
        # Should be pretty-printed with 2-space indent
        assert "  " in raw
        parsed = json.loads(raw)
        assert parsed == sample_manifest

    def test_overwrites_existing(self, tmp_path):
        save_manifest(tmp_path, {"old": {}})
        save_manifest(tmp_path, {"new": {}})
        loaded = load_manifest(tmp_path)
        assert "new" in loaded
        assert "old" not in loaded
