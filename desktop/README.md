# Kontext Studio desktop

A macOS-first Tauri shell around the existing local server. It bundles CPython
and every Python package the app needs, so a user downloads a DMG and opens it
without installing a toolchain.

## Layout

```text
desktop/
  runtime.lock.json        # pinned python-build-standalone assets
  requirements/kernel.txt  # offline kernel packages (mirrors the runtime default)
  scripts/assemble.py      # builds resources/python + resources/wheelhouse
  scripts/make-dmg.sh      # hdiutil DMG (no Finder automation)
  splash/index.html        # local page shown while Python starts
  src-tauri/               # Tauri shell
```

## Build the runtime

```bash
pnpm run build:shared
pnpm run desktop:assemble
```

The assembly script downloads the pinned CPython, installs the `desktop` wheel
profile into the interpreter's own site-packages, and downloads the kernel
wheelhouse. Output goes to `desktop/src-tauri/resources/` and is gitignored.
`pnpm run desktop:build` then writes
`dist/Kontext-Studio-<version>-macOS-<arch>.dmg`.

Pass `--wheel <path>` to reuse a wheel built elsewhere, `--skip-app-build` to
reuse the current `app/dist`, or `--arch arm64|x64|win-x64` to cross-assemble.

## Notes

- The desktop wheel profile drops the warehouse drivers (`psycopg`, `pymysql`,
  `pyodbc`, `oracledb`, `teradatasql`); those connectors are not available in
  the desktop build.
- The kernel packages are duplicated in the wheelhouse on purpose: the kernel
  venv is isolated from the server environment.
- `build-info.json` records the resolved packages and assembled sizes.
