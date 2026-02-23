# regmirror

Mirror container images through OCI tarballs to a private registry.

`regmirror` uses [skopeo](https://github.com/containers/skopeo) to pull images from any public or private registry, store them as OCI archive tarballs on disk, and re-push them to a private registry with automatic domain path rewriting.

## Why?

Air-gapped or restricted environments often can't reach public registries directly. `regmirror` lets you:

1. Pull images on a machine with internet access
2. Transfer the tarballs to the restricted environment (USB, S3, SCP, etc.)
3. Push them to an internal registry with predictable, collision-free names

## Requirements

- Python 3.8+
- [`skopeo`](https://github.com/containers/skopeo) installed and on `$PATH`

## Installation

```bash
git clone <repo>
chmod +x regmirror.py
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
    "digest": null
  }
}
```

The `upload` and `list` commands require this file to be present.

## Command reference

### `download`

| Flag | Default | Description |
| ------ | --------- | ------------- |
| `-f`, `--file` | *(required)* | Text file with image references |
| `-o`, `--output` | `./tarballs` | Directory to write tarballs and manifest |
| `--force` | false | Re-download tarballs that already exist |
| `--src-tls-verify BOOL` | — | Override TLS verification for the source registry |
| `--src-creds USER:PASS` | — | Credentials for the source registry |

### `upload`

| Flag | Default | Description |
| ------ | --------- | ------------- |
| `-d`, `--dir` | `./tarballs` | Directory containing tarballs and manifest |
| `-r`, `--registry` | *(required)* | Target registry (e.g. `my.registry.tld`) |
| `--dest-tls-verify BOOL` | — | Override TLS verification for the target registry |
| `--dest-creds USER:PASS` | — | Credentials for the target registry |

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

## Global flags

| Flag | Description |
| ------ | ------------- |
| `--dry-run` | Print skopeo commands without executing them |
