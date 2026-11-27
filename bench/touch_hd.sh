#!/bin/sh
# Restore pristine sources from $SNAPSHOT (a copy of src/), then add a new
# function to every module, so that a build recompiles all of the project's
# own code. Usage: SNAPSHOT=/path/to/copy bench/touch_hd.sh
set -e
cd "$(dirname "$0")/.."
n=$(date +%s%N)
for f in $(cd "$SNAPSHOT" && find src -name '*.hd'); do
    cp "$SNAPSHOT/$f" "$f"
    case $f in */mod.hd) ;; *) printf '\nfn bench_touch_%s() -> i64: %s\n' "$n" "$n" >> "$f";; esac
done
