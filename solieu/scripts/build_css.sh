#!/bin/sh
set -eu

TAILWIND_VERSION="v4.3.5"
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
BIN="$ROOT/.tools/tailwindcss"
INPUT="$ROOT/static/css/app.css"
OUTPUT="$ROOT/static/css/app.generated.css"

if [ ! -x "$BIN" ]; then
  mkdir -p "$(dirname "$BIN")"
  curl --fail --location --retry 3 \
    "https://github.com/tailwindlabs/tailwindcss/releases/download/$TAILWIND_VERSION/tailwindcss-macos-arm64" \
    --output "$BIN"
  chmod +x "$BIN"
fi

"$BIN" -i "$INPUT" -o "$OUTPUT" --minify
printf 'Built %s with Tailwind CSS %s\n' "$OUTPUT" "$TAILWIND_VERSION"
