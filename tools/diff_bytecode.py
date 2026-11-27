#!/usr/bin/env python3
"""Diff gojq's bytecode (go build -tags gojq_debug) with gojq-hd's, query by query.

Usage: GOJQ_DEBUG_BIN=path/to/gojq-debug tools/diff_bytecode.py tools/suite_queries.txt
"""
import os, re, subprocess, sys, json
HERE = os.path.dirname(os.path.abspath(__file__))
GO = [os.environ.get("GOJQ_DEBUG_BIN", "gojq-debug")]
HD = ["hd", os.path.join(HERE, "..", "build", "release", "gojqhd.cwasm"), "--"]

def listing(cmd, q):
    env = dict(os.environ, GOJQ_DEBUG="stdout")
    p = subprocess.Popen(cmd + ["-n", q], env=env, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, stdin=subprocess.DEVNULL)
    lines = []
    for l in p.stdout:
        if l.startswith("\t" + "-" * 40 + "+"):
            break
        if l.strip():
            lines.append(re.sub(r"\t## .*$", "", l.rstrip("\n")).rstrip())
    p.kill(); p.wait()
    return lines

qs = [l.rstrip("\n") for l in open(sys.argv[1])] if len(sys.argv) > 1 else []
ok = 0
for q in qs:
    g, h = listing(GO, q), listing(HD, q)
    if g == h:
        ok += 1
    else:
        print(f"DIFF {q!r}: go {len(g)} codes, hd {len(h)} codes")
        for i, (a, b) in enumerate(zip(g, h)):
            if a != b:
                print(f"   first difference at line {i}:\n     go: {a}\n     hd: {b}")
                break
print(f"{ok}/{len(qs)} identical")
