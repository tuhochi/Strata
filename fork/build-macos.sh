#!/bin/bash
# Run on atlas or another Apple Silicon builder, from an immutable source snapshot.
set -euo pipefail
SOURCE=$(cd "$(dirname "$0")/.." && pwd)
BUILD_ROOT=${STRATA_FORK_BUILD_ROOT:-$HOME/builds/strata-fork}
PYTHON=${STRATA_BUILD_PYTHON:-/opt/homebrew/bin/python3.12}
SOURCE_COMMIT=${STRATA_SOURCE_COMMIT:?Set STRATA_SOURCE_COMMIT to the exact archived source commit}
[[ $(uname -s) == Darwin && $(uname -m) == arm64 ]] || { echo 'Apple Silicon macOS builder required.' >&2; exit 1; }
META=$("$PYTHON" -c 'import json,sys; d=json.load(open(sys.argv[1])); print(d["release"],d["component_version"],d["minimum_macos"],d["llama_cpp_commit"])' "$SOURCE/fork/release.json")
read -r RELEASE COMPONENT MIN_OS LLAMA_COMMIT <<< "$META"
VENV="$BUILD_ROOT/venv"
if [[ ! -x "$VENV/bin/python" ]]; then "$PYTHON" -m venv "$VENV"; fi
"$VENV/bin/pip" install --disable-pip-version-check -r "$SOURCE/requirements.txt" -r "$SOURCE/requirements-build.txt"
export PATH="$VENV/bin:$PATH"
DEPS="$BUILD_ROOT/deps"
mkdir -p "$DEPS"
if [[ ! -d "$DEPS/llama.cpp/.git" ]]; then git clone --filter=blob:none --no-checkout https://github.com/ggml-org/llama.cpp.git "$DEPS/llama.cpp"; fi
git -C "$DEPS/llama.cpp" fetch --depth 1 origin "$LLAMA_COMMIT"
git -C "$DEPS/llama.cpp" checkout --detach "$LLAMA_COMMIT"
python - "$SOURCE" "$DEPS" <<'PY'
import json,pathlib,urllib.request,hashlib,zipfile,sys
source,deps=map(pathlib.Path,sys.argv[1:]);meta=json.loads((source/'fork/release.json').read_text());archive=deps/'metal-cpp.zip'
if not archive.exists():urllib.request.urlretrieve(meta['metal_cpp_url'],archive)
if hashlib.sha256(archive.read_bytes()).hexdigest()!=meta['metal_cpp_sha256']:raise SystemExit('metal-cpp checksum mismatch')
with zipfile.ZipFile(archive) as z:z.extractall(deps/'metal-cpp-extract')
PY
BUILD="$BUILD_ROOT/builds/$SOURCE_COMMIT/metal"
OUT="$BUILD_ROOT/artifacts/$SOURCE_COMMIT"
cmake -S "$SOURCE/metal" -B "$BUILD" -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_OSX_DEPLOYMENT_TARGET="$MIN_OS" -DSTRATA_FORK_ENGINE_VERSION="$COMPONENT" -DSTRATA_BUILD_ID="$SOURCE_COMMIT" -DSTRATA_GGML_DIR="$DEPS/llama.cpp" -DMETAL_CPP_DIR="$DEPS/metal-cpp-extract/metal-cpp" -DGGML_NATIVE=OFF
cmake --build "$BUILD" --target strata --parallel 6
export MACOSX_DEPLOYMENT_TARGET="$MIN_OS"
"$BUILD/strata" --version
mkdir -p "$OUT/engine-stage/metal/engine-msl" "$OUT/engine-stage/metal/kernels" "$OUT/engine-stage/metal/data"
cp "$BUILD/strata" "$OUT/engine-stage/strata"
cp "$SOURCE"/metal/kernels/*.metal "$OUT/engine-stage/metal/kernels/"
cp "$SOURCE"/metal/src/engine/msl/*.metal "$OUT/engine-stage/metal/engine-msl/"
cp "$SOURCE/third_party/ggml/ggml-common.h" "$OUT/engine-stage/metal/ggml-common.h"
cp "$SOURCE/data/draft_vocab.bin" "$SOURCE/data/expert-profile.bin" "$OUT/engine-stage/metal/data/"
cp "$SOURCE/LICENSE" "$OUT/engine-stage/"
python - "$SOURCE" "$OUT" "$SOURCE_COMMIT" <<'PY'
import json,pathlib,platform,subprocess,sys
source,out=map(pathlib.Path,sys.argv[1:3]);meta=json.loads((source/'fork/release.json').read_text());build={**meta,'source_commit':sys.argv[3],'builder':{'platform':platform.platform(),'architecture':platform.machine(),'sdk':subprocess.check_output(['xcrun','--show-sdk-version'],text=True).strip(),'compiler':subprocess.check_output(['clang','--version'],text=True).splitlines()[0]}}
(out/'engine-stage/BUILD.json').write_text(json.dumps(build,indent=2)+'\n')
PY
bash "$SOURCE/packaging/build_vision_mac.sh" --llama "$DEPS/llama.cpp" --out "$OUT/engine-stage" --build "$BUILD_ROOT/builds/$SOURCE_COMMIT/vision" --jobs 6
python "$SOURCE/packaging/package_engine.py" --src "$OUT/engine-stage" --backend metal --version "$COMPONENT" --platform macos-arm64 --arch apple-gpu --build-id "$SOURCE_COMMIT" --include 'metal/**' --include 'data/**' --out "$OUT/engine"
python "$SOURCE/packaging/package_terminal.py" --out "$OUT/control" --target darwin-arm64 --version "$COMPONENT" --commit "$SOURCE_COMMIT" --cache "$DEPS/python-cache"
python "$SOURCE/fork/verify_terminal.py" "$OUT/control/strata-terminal-$COMPONENT-darwin-arm64.tar.gz"
printf 'Build artifacts: %s\n' "$OUT"
