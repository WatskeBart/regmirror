"""Integration test fixtures — manages a local registry:3 Podman container."""

from __future__ import annotations

import subprocess
import time

import pytest


@pytest.fixture(scope="session")
def local_registry():
    """Start a local registry:3 Podman container for the test session.

    Yields the registry address (e.g. ``localhost:5001``).
    The container is removed after the session regardless of test outcome.

    Requires Podman to be installed and running.
    """
    name = "regmirror-test-registry"
    port = 5001  # use 5001 to avoid clashing with other services on 5000

    subprocess.run(
        [
            "podman", "run", "-d",
            "--name", name,
            "-p", f"{port}:5000",
            "registry:3",
        ],
        check=True,
    )

    # Give the registry a moment to become ready
    time.sleep(2)

    yield f"localhost:{port}"

    subprocess.run(["podman", "rm", "-f", name], check=True)
