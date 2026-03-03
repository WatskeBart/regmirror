# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.2.0] - 2026-03-03

### Added
- `get_remote_digest()` helper that queries the registry via `skopeo inspect` to
  retrieve the current manifest digest of an image reference without downloading it.
- Digest tracking in `manifest.json`: after a successful download of a tag-based
  image the resolved `sha256:` digest is now stored, enabling update detection on
  subsequent runs.

### Changed
- Tag-based refs (e.g. `nginx:latest`) with an existing tarball now check the
  remote digest before deciding to skip. The tarball is re-downloaded automatically
  when the tag has moved to a newer image.
- Digest-pinned refs (e.g. `nginx@sha256:...`) are always skipped when the tarball
  exists — their content is immutable by definition.
- If the remote digest check fails (network error, auth failure, etc.) a warning is
  logged and the existing tarball is kept. `--force` can be used to override.

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
