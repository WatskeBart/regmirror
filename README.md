# regmirror

Mirror container images through OCI tarballs to a private registry.

`regmirror` uses [skopeo](https://github.com/containers/skopeo) to pull images from any public or private registry, store them as OCI archive tarballs on disk, and re-push them to a private registry with automatic domain path rewriting.

## Why?

Air-gapped or restricted environments often can't reach public registries directly. `regmirror` lets you:

1. Pull images on a machine with internet access
2. Transfer the tarballs to the restricted environment (USB, S3, SCP, etc.)
3. Push them to an internal registry with predictable, collision-free names

## Requirements

- Python 3.10+
- [`skopeo`](https://github.com/containers/skopeo) installed and on `$PATH`

## Installation

```bash
uv tool install regmirror
```

Or run without installing:

```bash
uvx regmirror
```

Alternatively with pipx/pip:

```bash
pipx install regmirror
# or
pip install regmirror
```

## Usage

### Download images to tarballs

```bash
./regmirror.py download -f images.txt -o ./tarballs
```

### Upload tarballs to a private registry

```bash
./regmirror.py upload -d ./tarballs -r my.registry.tld
```

### Download and upload in one step

```bash
./regmirror.py sync -f images.txt -o ./tarballs -r my.registry.tld
```

### Preview the manifest and upload targets

```bash
./regmirror.py list -d ./tarballs -r my.registry.tld
```

## Image list file

The `-f` / `--file` argument points to a plain text file with one image reference per line. Lines starting with `#` are ignored.

```
# Example images.txt
nginx:1.25
docker.io/library/redis:7
gcr.io/google-containers/pause:3.9
quay.io/prometheus/prometheus:v2.51.0
```

## Name rewriting

Source registry domains are flattened into a path prefix to avoid conflicts:

| Source | Target |
| -------- | -------- |
| `docker.io/library/nginx:1.25` | `my.registry.tld/dockerio/library/nginx:1.25` |
| `gcr.io/project/app:v1` | `my.registry.tld/gcrio/project/app:v1` |
| `quay.io/prometheus/prometheus:v2.51.0` | `my.registry.tld/quayio/prometheus/prometheus:v2.51.0` |

## manifest.json

Every `download` run writes a `manifest.json` into the tarball directory. This file maps each tarball filename back to its original image reference, making the conversion fully reversible without fragile filename encoding.

```json
{
  "nginx-1.25.tar": {
    "original": "nginx:1.25",
    "registry": "docker.io",
    "image": "library/nginx",
    "tag": "1.25",
    "digest": "sha256:a484819eb60211f5299034ac80f6a681b06f89e476600f94c25bde91c7f7e88c"
  }
}
```

After a successful download the resolved `sha256:` digest is stored alongside the tag. On subsequent runs `regmirror` uses this digest to detect whether the tag now points to a newer image — if it does, the tarball is re-downloaded automatically. Use `--force` to re-download unconditionally regardless of the stored digest.

The `upload` and `list` commands require this file to be present.

## Command reference

### `download`

| Flag | Default | Description |
| ------ | --------- | ------------- |
| `-f`, `--file` | *(required)* | Text file with image references |
| `-o`, `--output` | `./tarballs` | Directory to write tarballs and manifest |
| `--force` | false | Re-download tarballs unconditionally, ignoring stored digest |
| `--src-tls-verify BOOL` | — | Override TLS verification for the source registry |
| `--src-creds USER:PASS` | — | Credentials for the source registry |
| `--authfile FILE` | — | Path to a Docker-compatible `auth.json` |
| `--remove-signatures` | auto | Strip embedded image signatures; applied automatically when detected, or pass explicitly to always strip |

### `upload`

| Flag | Default | Description |
| ------ | --------- | ------------- |
| `-d`, `--dir` | `./tarballs` | Directory containing tarballs and manifest |
| `-r`, `--registry` | *(required)* | Target registry (e.g. `my.registry.tld`) |
| `--dest-tls-verify BOOL` | — | Override TLS verification for the target registry |
| `--dest-creds USER:PASS` | — | Credentials for the target registry |
| `--authfile FILE` | — | Path to a Docker-compatible `auth.json` |
| `--remove-signatures` | false | Strip image signatures during push |

### `sync`

Accepts all flags from both `download` and `upload`, plus:

| Flag | Default | Description |
| ------ | --------- | ------------- |
| `--continue-on-error` | false | Continue with upload even if some downloads failed |

### `list`

| Flag | Default | Description |
| ------ | --------- | ------------- |
| `-d`, `--dir` | `./tarballs` | Directory containing the manifest |
| `-r`, `--registry` | — | Preview what the upload targets would be |

## Building the package

Install the build tools:

```bash
pip install build hatchling
```

Build both the wheel and source distribution:

```bash
python -m build
```

This outputs `dist/regmirror-<version>-py3-none-any.whl` and
`dist/regmirror-<version>.tar.gz`.

Install locally to test before publishing:

```bash
uv tool install dist/regmirror-*.whl
# or
pipx install dist/regmirror-*.whl
```

Publish to PyPI:

```bash
pip install twine
twine upload dist/*
```

## Global flags

| Flag | Description |
| ------ | ------------- |
| `--dry-run` | Print skopeo commands without executing them |
| `--version` | Print version and exit |
