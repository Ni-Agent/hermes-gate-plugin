# Release packaging

Requires Git and Python 3. Run from a clean source checkout. Set `VERSION` to the
manifest version and create the matching local tag before packaging. For this
candidate:

```sh
VERSION=0.1.0-beta.1
# Run once for a new release; an existing tag must already identify this HEAD.
git tag "v$VERSION"
mkdir -p dist
git archive --format=tar.gz --prefix=hermes-gate-plugin/ \
  -o "dist/hermes-gate-$VERSION.tar.gz" "v$VERSION"
git bundle create "dist/hermes-gate-$VERSION.bundle" HEAD main "v$VERSION"
VERSION="$VERSION" python3 - <<'PY'
import hashlib, os, pathlib
version = os.environ['VERSION']
root = pathlib.Path('dist')
paths = [root / f'hermes-gate-{version}.tar.gz', root / f'hermes-gate-{version}.bundle']
(root / f'SHA256SUMS-{version}').write_text(''.join(
    hashlib.sha256(path.read_bytes()).hexdigest() + '  ' + path.name + '\n'
    for path in paths))
PY
(cd dist && sha256sum -c "SHA256SUMS-$VERSION")
git bundle verify "dist/hermes-gate-$VERSION.bundle"
```

The bundle advertises `HEAD` for a normal fresh clone and includes `main` and the current release tag with complete history, so recipients
can clone and use the native installer. The source archive contains tracked files.
Checksums use basenames and verify from the artifact directory. Confirm that
`main`, `HEAD` and the version tag identify the same tested commit before packaging.

# Publication reference

Publication is a separate action. The public repository is
[Ni-Agent/hermes-gate-plugin](https://github.com/Ni-Agent/hermes-gate-plugin).
Set its URL as `origin` if no origin exists:
`git remote add origin https://github.com/Ni-Agent/hermes-gate-plugin.git`.
If an origin already exists, verify it before publishing. Authenticate Git and
GitHub CLI first. After reviewing the candidate, push the existing tag
and publish the prerelease with these two commands:

```sh
git push origin main "v$VERSION"
gh release create "v$VERSION" "dist/hermes-gate-$VERSION.tar.gz" \
  "dist/hermes-gate-$VERSION.bundle" "dist/SHA256SUMS-$VERSION" \
  --repo Ni-Agent/hermes-gate-plugin --prerelease --title "Gate for Hermes $VERSION" --notes-file README.md
```

Never move a published tag. Retain the tested source commit and checksums with the
release. No publication credentials or agent tokens belong in release artifacts.
