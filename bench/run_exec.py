#!/usr/bin/env python3
"""Execution-time comparison: gojq (Go, no YAML) vs gojq-hd (faithful port) (hd -> Wasm, run by `hd`)."""
import json, os, shlex, subprocess, sys

# S: the folder holding gojq-noyaml-bin, big.json and medium.json
S = os.environ.get("BENCH_DIR", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
GO = [os.path.join(S, "gojq-noyaml-bin")]
HD = ["hd", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "build", "release", "gojqhd.cwasm"), "--"]

# (name, args, input file or None)
W = [
    ("startup (-n 1)", ["-n", "1"], None),
    ("identity, pretty (12 MB)", ["."], "big.json"),
    ("identity, compact (12 MB)", ["-c", "."], "big.json"),
    ("sum a field", ["map(.score) | add"], "big.json"),
    ("select + project", ["[.[] | select(.id % 2 == 0) | .name] | length"], "big.json"),
    ("group_by", ["-c", "group_by(.id % 10) | map(length)"], "big.json"),
    ("sort_by", ["sort_by(-.id) | .[0].id"], "big.json"),
    ("nested update |=", ["-c", "map(.nested.y |= map(. * 2)) | .[99999].nested"], "big.json"),
    ("[paths] | length", ["[paths] | length"], "big.json"),
    ("regex test", ['[.[].name | select(test("^user[0-9]*7$"))] | length'], "big.json"),
    ("gsub (1 MB)", ['[.[].name | gsub("user"; "u")] | length'], "medium.json"),
    ("tojson | fromjson", ["tojson | fromjson | length"], "big.json"),
    ("to_entries/from_entries (1 MB)", ["map(to_entries | from_entries) | length"], "medium.json"),
    ("range 1M | map | add", ["-n", "[range(1000000)] | map(. * 2) | add"], None),
    ("reduce 1M", ["-n", "reduce range(1000000) as $i (0; . + $i)"], None),
    ("recursion fib(22)", ["-n", "def fib: if . < 2 then . else (. - 1 | fib) + (. - 2 | fib) end; 22 | fib"], None),
    ("join 100k strings", ["-n", '[range(100000) | tostring] | join(",") | length'], None),
    ("bigint 500!", ["-n", "def f: if . > 1 then . * (. - 1 | f) else 1 end; 500 | f | tostring | length"], None),
    ("todate/fromdate 100k", ["-n", "[range(100000) | todate | fromdate] | add"], None),
]

def cmd(base, args, f):
    parts = base + args + ([f] if f else [])
    s = " ".join(shlex.quote(p) for p in parts)
    return s + " > /dev/null" + ("" if f else " < /dev/null")

def output(base, args, f):
    r = subprocess.run(base + args + ([f] if f else []), cwd=S, capture_output=True, stdin=subprocess.DEVNULL)
    return r.stdout, r.returncode

rows = []
only = sys.argv[1:]
for name, args, f in W:
    if only and not any(o in name for o in only):
        continue
    g, gc = output(GO, args, f)
    h, hc = output(HD, args, f)
    same = g == h and gc == hc
    out = os.path.join(S, "bench", "port_exec_" + str(len(rows)) + ".json")
    subprocess.run(["hyperfine", "--warmup", "1", "--min-runs", "5", "--max-runs", "10", "-N" if False else "--shell=sh",
                    "--export-json", out, "-n", "go", cmd(GO, args, f), "-n", "hd", cmd(HD, args, f)],
                   cwd=S, capture_output=True)
    res = json.load(open(out))["results"]
    tg = res[0]["mean"]; th = res[1]["mean"]
    rows.append((name, tg, th, same))
    print(f"{name:34s} go {tg*1000:9.1f} ms   hd {th*1000:9.1f} ms   hd/go {th/tg:6.2f}x   {'same output' if same else 'OUTPUT DIFFERS'}", flush=True)

json.dump(rows, open(os.path.join(S, "bench", "port_exec_summary.json"), "w"))
