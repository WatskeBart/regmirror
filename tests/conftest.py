"""Shared fixtures for regmirror tests."""

from __future__ import annotations

import argparse
import json

import pytest


@pytest.fixture
def tmp_dir(tmp_path):
    return tmp_path


@pytest.fixture
def sample_manifest():
    return {
        "dockerio_library_nginx-1.25.tar": {
            "original": "nginx:1.25",
            "registry": "docker.io",
            "image": "library/nginx",
            "tag": "1.25",
            "digest": "sha256:" + "a" * 64,
        }
    }


@pytest.fixture
def make_args():
    """Return a factory that builds argparse.Namespace with sensible defaults."""

    def _make(**kwargs):
        defaults = dict(
            src_tls_verify=None,
            src_creds=None,
            authfile=None,
            dest_tls_verify=None,
            dest_creds=None,
            remove_signatures=False,
            force=False,
            dry_run=False,
            continue_on_error=False,
        )
        defaults.update(kwargs)
        return argparse.Namespace(**defaults)

    return _make
