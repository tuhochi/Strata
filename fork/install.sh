#!/bin/sh
# Install the signed, prebuilt Apple Silicon fork; no system Python or compiler required.
set -eu
REPOSITORY=https://github.com/tuhochi/Strata
RELEASE=
PINNED=0
while [ "$#" -gt 0 ]; do
  case "$1" in
    --repo) REPOSITORY=$2; shift 2 ;;
    --version) RELEASE=$2; PINNED=1; shift 2 ;;
    --help) echo 'Usage: sh install.sh [--repo https://github.com/OWNER/REPO] [--version v0.2.11-p1]'; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; exit 2 ;;
  esac
done
[ "$(uname -s)" = Darwin ] && [ "$(uname -m)" = arm64 ] || { echo 'This release is for Apple Silicon Macs.' >&2; exit 1; }
[ "$(sw_vers -productVersion | cut -d. -f1)" -ge 15 ] || { echo 'macOS 15 or newer is required.' >&2; exit 1; }
REPOSITORY=${REPOSITORY%.git}
OWNER_REPO=${REPOSITORY#https://github.com/}
printf '%s\n' "$OWNER_REPO" | grep -Eq '^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$' || { echo 'Use a GitHub repository URL.' >&2; exit 2; }
RAW=https://raw.githubusercontent.com/$OWNER_REPO
WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT HUP INT TERM
fetch() { curl --fail --silent --show-error --location --retry 3 --proto '=https' "$1" -o "$2"; }
if [ -z "$RELEASE" ]; then
  fetch "$RAW/patched/fork/LATEST" "$WORK/latest"
  RELEASE=$(tr -d '\r\n' < "$WORK/latest")
fi
printf '%s\n' "$RELEASE" | grep -Eq '^v[0-9]+\.[0-9]+\.[0-9]+(\.[0-9]+)?-p[1-9][0-9]*$' || { echo 'Invalid fork release.' >&2; exit 2; }
FEED=$RAW/$RELEASE/releases/$RELEASE
ROOT=${STRATA_FORK_DATA_DIR:-$HOME/.local/share/strata-fork}
BIN=${STRATA_FORK_BIN_DIR:-$HOME/.local/bin}
mkdir -p "$ROOT/bin" "$BIN"
fetch "$FEED/install.sh" "$WORK/install.sh"
# Upstream's installer verifies the feed signature using the public key in our Control package.
STRATA_FEED="$FEED" STRATA_DATA_DIR="$ROOT" STRATA_BIN_DIR="$ROOT/bin" sh "$WORK/install.sh"
if [ "$PINNED" = 1 ]; then
  printf '%s\n' "$FEED" > "$ROOT/feed-url"
else
  printf '%s\n' "$RAW/patched/releases/stable" > "$ROOT/feed-url"
fi
cat > "$ROOT/strata-fork" <<'LAUNCH'
#!/bin/sh
set -eu
self=$0
while [ -L "$self" ]; do
  dir=$(CDPATH= cd -- "$(dirname -- "$self")" && pwd -P)
  target=$(readlink "$self")
  case $target in /*) self=$target ;; *) self=$dir/$target ;; esac
done
ROOT=$(CDPATH= cd -- "$(dirname -- "$self")" && pwd -P)
export STRATA_DATA_DIR="$ROOT"
export STRATA_COMPONENTS_DIR="$ROOT/components"
export STRATA_UPDATE_FEED="$(cat "$ROOT/feed-url")/strata-feed.json"
export STRATA_TOOL_MASK=1 STRATA_TOOL_NAME_ENUM=1
export STRATA_TOOL_MASK_STRICT=${STRATA_TOOL_MASK_STRICT:-1}
exec "$ROOT/bin/strata" "$@"
LAUNCH
chmod 755 "$ROOT/strata-fork"
ln -sf "$ROOT/strata-fork" "$BIN/strata-fork"
"$ROOT/strata-fork" update --yes --no-control --feed "$FEED"
"$ROOT/strata-fork" --version
printf '\nInstalled %s. Run: %s/strata-fork launch\n' "$RELEASE" "$BIN"
printf 'Existing Strata installations and model files were not replaced.\n'
