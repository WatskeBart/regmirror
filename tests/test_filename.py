"""Tests for ref_to_filename."""

from __future__ import annotations

from regmirror.__main__ import ref_to_filename


class TestRefToFilename:
    def test_simple_name_tag(self):
        assert ref_to_filename("nginx:1.25") == "nginx-1.25.tar"

    def test_name_only_no_tag(self):
        assert ref_to_filename("nginx") == "nginx.tar"

    def test_path_with_registry_domain(self):
        # Dots are kept; slashes become _, colons become -
        result = ref_to_filename("docker.io/library/nginx:1.25")
        assert result == "docker.io_library_nginx-1.25.tar"

    def test_gcr_path(self):
        result = ref_to_filename("gcr.io/project/app:v1")
        assert result == "gcr.io_project_app-v1.tar"

    def test_digest_ref_truncates_hash(self):
        # Use two distinct hex chars so we can verify truncation
        prefix = "a" * 12
        suffix = "b" * 52
        digest_hex = prefix + suffix
        ref = f"myimage@sha256:{digest_hex}"
        result = ref_to_filename(ref)
        assert result.endswith(".tar")
        # Hash portion kept in filename
        # result looks like "myimage@sha256-aaaaaaaaaaaa.tar"
        hash_in_name = result.split("sha256-")[1][:-4]  # strip ".tar"
        # Only first 12 chars of the hash should be present
        assert hash_in_name == prefix
        # The suffix chars (b) must not appear
        assert "b" not in hash_in_name

    def test_digest_with_registry_domain(self):
        digest_hex = "c" * 64
        ref = f"gcr.io/project/app@sha256:{digest_hex}"
        result = ref_to_filename(ref)
        assert result.endswith(".tar")
        assert "sha256-" in result
        # Only 12 chars of hash kept
        hash_part = result.split("sha256-")[1].split(".tar")[0]
        assert len(hash_part) == 12
