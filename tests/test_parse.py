"""Tests for parse_image_ref."""

from __future__ import annotations

import pytest

from regmirror.__main__ import parse_image_ref


class TestParseImageRef:
    def test_bare_name_defaults(self):
        p = parse_image_ref("nginx")
        assert p["registry"] == "docker.io"
        assert p["image"] == "nginx"
        assert p["tag"] == "latest"
        assert p["digest"] is None

    def test_name_with_tag(self):
        p = parse_image_ref("nginx:1.25")
        assert p["registry"] == "docker.io"
        assert p["image"] == "nginx"
        assert p["tag"] == "1.25"
        assert p["digest"] is None

    def test_explicit_docker_io_not_parsed_as_registry(self):
        # The regex does not extract two-segment domains as a registry;
        # docker.io/library/nginx is treated as the image name with default registry.
        p = parse_image_ref("docker.io/library/nginx:1.25")
        assert p["registry"] == "docker.io"   # falls back to default
        assert p["image"] == "docker.io/library/nginx"
        assert p["tag"] == "1.25"

    def test_gcr_io_not_parsed_as_registry(self):
        # gcr.io is treated as part of the image name, not the registry field.
        p = parse_image_ref("gcr.io/project/app:v1")
        assert p["registry"] == "docker.io"   # falls back to default
        assert p["image"] == "gcr.io/project/app"
        assert p["tag"] == "v1"

    def test_quay_io_not_parsed_as_registry(self):
        p = parse_image_ref("quay.io/prometheus/prometheus:v2.51.0")
        assert p["registry"] == "docker.io"   # falls back to default
        assert p["image"] == "quay.io/prometheus/prometheus"
        assert p["tag"] == "v2.51.0"

    def test_localhost_with_port_parsed_as_registry(self):
        # Port-based refs ARE extracted as registry.
        p = parse_image_ref("localhost:5000/myimage:test")
        assert p["registry"] == "localhost:5000"
        assert p["image"] == "myimage"
        assert p["tag"] == "test"

    def test_digest_pinned(self):
        digest = "sha256:" + "a" * 64
        p = parse_image_ref(f"myimage@{digest}")
        assert p["digest"] == digest
        assert p["tag"] is None

    def test_digest_pinned_with_domain_in_image(self):
        # Domain-based prefix ends up in the image field.
        digest = "sha256:" + "b" * 64
        p = parse_image_ref(f"gcr.io/project/app@{digest}")
        assert p["registry"] == "docker.io"   # falls back to default
        assert p["image"] == "gcr.io/project/app"
        assert p["digest"] == digest
        assert p["tag"] is None

    def test_original_preserved(self):
        ref = "nginx:1.25"
        p = parse_image_ref(ref)
        assert p["original"] == ref

    def test_whitespace_stripped(self):
        p = parse_image_ref("  nginx:1.25  ")
        assert p["image"] == "nginx"
        assert p["tag"] == "1.25"

    def test_invalid_ref_raises(self):
        with pytest.raises(ValueError, match="Cannot parse"):
            parse_image_ref("!!invalid!!")
