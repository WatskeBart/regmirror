# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.2.0] - 2026-03-03

### Added

- `inspect_remote()` helper that fetches the raw image manifest via
  `skopeo inspect --raw`, computing the manifest digest and detecting embedded
  signatures in a single network call. Returns a `RemoteInfo` named tuple with
  `digest` and `has_embedded_signatures` fields.
- Digest tracking in `manifest.json`: after a successful download of a tag-based
  image the resolved `sha256:` digest is stored, enabling update detection on
  subsequent runs.
- Auto-detection of old-style embedded image signatures (Docker Content Trust /
  Notary v1): when detected, `--remove-signatures` is applied automatically and
  an info message is logged. Modern cosign/sigstore signatures are stored as
  separate OCI artifacts and are not affected by this detection.

### Changed

- Tag-based refs (e.g. `nginx:latest`) with an existing tarball now check the
  remote digest before deciding to skip. The tarball is re-downloaded automatically
  when the tag has moved to a newer image.
- Digest-pinned refs (e.g. `nginx@sha256:...`) are always skipped when the tarball
  exists — their content is immutable by definition.
- If the remote manifest fetch fails (network error, auth failure, etc.) a warning
  is logged and the existing tarball is kept. `--force` can be used to override.
- `--remove-signatures` on `download` and `sync` now acts as an explicit override
  in addition to the new auto-detection; passing the flag always strips signatures
  regardless of whether they were detected.

## [1.1.0] - 2026-03-01

### Added

- `__version__`, `__author__`, and `__description__` module-level metadata.
- Colored terminal logging via `_ColorFormatter`: DEBUG=cyan, INFO=green,
  WARNING=yellow, ERROR=red, CRITICAL=bold red. Falls back to plain formatting
  when stderr is not a TTY.

## [1.0.0] - 2026-02-23

### Added

- Initial release.
- `download` command: pull images listed in a text file to OCI tarballs via
  `skopeo copy`.
- `upload` command: push tarballs to a private registry with source-registry
  path rewriting (e.g. `docker.io` → `<registry>/dockerio`).
- `sync` command: download and upload in a single step.
- `list` command: display manifest contents and preview upload targets.
- `manifest.json` sidecar file mapping tarball filenames to original image
  references, making the conversion fully reversible.
- `--force` flag to re-download existing tarballs unconditionally.
- `--dry-run` flag to print `skopeo` commands without executing them.
- `--src-tls-verify` / `--dest-tls-verify` flags for registries with
  self-signed certificates.
- `--src-creds` / `--dest-creds` flags for registry authentication.
- `--authfile` flag to pass a Docker-compatible `auth.json`.
- `--remove-signatures` flag to strip image signatures during copy.

[Unreleased]: https://github.com/WatskeBart/regmirror/compare/1.2.0...HEAD
[1.2.0]: https://github.com/WatskeBart/regmirror/compare/1.1.0...1.2.0
[1.1.0]: https://github.com/WatskeBart/regmirror/compare/1.0.0...1.1.0
[1.0.0]: https://github.com/WatskeBart/regmirror/releases/tag/1.0.0
