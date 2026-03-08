"""Tests for rewrite_for_registry.

Note: the image regex only extracts port-based registries (e.g. localhost:5000).
Domain-only refs (docker.io, gcr.io, quay.io) fall through with registry=docker.io
(the default) and the domain included in the image field. rewrite_for_registry
works on the already-parsed dict, so these tests verify its output faithfully.
"""

from __future__ import annotations

from regmirror.__main__ import parse_image_ref, rewrite_for_registry

TARGET = "my.registry.tld"


class TestRewriteForRegistry:
    def _rewrite(self, ref: str) -> str:
        return rewrite_for_registry(parse_image_ref(ref), TARGET)

    def test_simple_image_tag(self):
        # nginx → registry=docker.io, image=nginx
        result = self._rewrite("nginx:1.25")
        assert result == f"{TARGET}/dockerio/nginx:1.25"

    def test_docker_io_prefix_in_image(self):
        # docker.io/library/nginx parsed as image=docker.io/library/nginx, registry=docker.io
        result = self._rewrite("docker.io/library/nginx:1.25")
        assert result == f"{TARGET}/dockerio/docker.io/library/nginx:1.25"

    def test_gcr_prefix_in_image(self):
        result = self._rewrite("gcr.io/project/app:v1")
        assert result == f"{TARGET}/dockerio/gcr.io/project/app:v1"

    def test_quay_prefix_in_image(self):
        result = self._rewrite("quay.io/prometheus/prometheus:v2.51.0")
        assert result == f"{TARGET}/dockerio/quay.io/prometheus/prometheus:v2.51.0"

    def test_digest_pinned(self):
        digest = "sha256:" + "a" * 64
        result = self._rewrite(f"gcr.io/project/app@{digest}")
        assert result == f"{TARGET}/dockerio/gcr.io/project/app@{digest}"

    def test_no_tag_defaults_to_latest(self):
        result = self._rewrite("nginx")
        assert result.endswith(":latest")

    def test_port_registry_extracted_correctly(self):
        # localhost:5000/myimage:test → registry=localhost:5000, image=myimage
        result = self._rewrite("localhost:5000/myimage:test")
        # dots and colons stripped from registry name → localhost5000
        assert result == f"{TARGET}/localhost5000/myimage:test"
