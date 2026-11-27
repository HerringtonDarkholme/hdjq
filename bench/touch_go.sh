#!/bin/sh
# Restore gojq's pristine sources from $SNAPSHOT, then add a new function to
# every file of its own packages, so that `go build` recompiles them.
# Usage: GOJQ=/path/to/gojq SNAPSHOT=/path/to/copy bench/touch_go.sh
set -e
cd "$GOJQ"
n=$(date +%s%N); i=0
for f in $(cd "$SNAPSHOT" && find . -name '*.go'); do
    i=$((i + 1))
    cp "$SNAPSHOT/$f" "$f"
    printf '\nfunc benchTouch%s_%s() int { return %s }\n' "$n" "$i" "$n" >> "$f"
done
