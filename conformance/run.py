#!/usr/bin/env python3
"""Run gojq's cli/test.yaml cases (converted to gojq-cli-tests.json) against gojq-hd.

Build first: `hd build --release` in the package folder.

Usage: runtests.py [-v] [-k SUBSTRING] [--fail-list FILE]
"""
import json, os, subprocess, sys, concurrent.futures as cf

HERE = os.path.dirname(os.path.abspath(__file__))
BIN = os.path.join(HERE, "..", "build", "release", "gojqhd.cwasm")
CWD = HERE
TESTS = json.load(open(os.path.join(HERE, "gojq-cli-tests.json")))

args = sys.argv[1:]
verbose = "-v" in args
filt = None
if "-k" in args:
    filt = args[args.index("-k") + 1]

def run(tc):
    env = dict(os.environ)
    env["NO_COLOR"] = ""
    env["GOJQ_COLORS"] = ""
    # gojq's cli_test.go sets time.Local to a fixed zone 7 hours behind UTC
    env["TZ"] = os.environ.get("TEST_TZ", "Etc/GMT+7")
    for e in tc.get("env", []) or []:
        k, v = e.split("=", 1)
        env[k] = v
    cmd = os.environ.get("GOJQ_CMD")
    prefix = cmd.split() if cmd else ["hd", BIN, "--"]
    argv = prefix + [str(a) for a in (tc.get("args") or [])]
    inp = tc.get("input")
    try:
        p = subprocess.run(argv, input=(inp if inp is not None else "").encode(), cwd=CWD, env=env,
                           capture_output=True, timeout=20)
    except subprocess.TimeoutExpired:
        return tc, False, "TIMEOUT", "", "", -1
    out = p.stdout.decode("utf-8", "replace")
    err = p.stderr.decode("utf-8", "replace")
    code = p.returncode
    expected = tc.get("expected") or ""
    want_err = tc.get("error") or ""
    want_code = tc.get("exit_code") or 0
    problems = []
    if not want_err:
        if code != want_code:
            problems.append(f"exit code: got {code}, want {want_code}")
        if out != expected:
            problems.append("stdout differs")
        if err != "":
            problems.append("unexpected stderr")
    else:
        if "DEBUG:" in err:
            if code != 0:
                problems.append(f"exit code: got {code}, want 0")
        elif want_code:
            if code != want_code:
                problems.append(f"exit code: got {code}, want {want_code}")
        elif code != 5:
            problems.append(f"exit code: got {code}, want 5")
        if out != expected:
            problems.append("stdout differs")
        got = err.replace("gojq: ", "")
        if not (got.startswith(want_err) or got.endswith(want_err)):
            problems.append("stderr differs")
    return tc, not problems, "; ".join(problems), out, err, code

cases = [t for t in TESTS if filt is None or filt in t["name"]]
passed = 0
fails = []
with cf.ThreadPoolExecutor(max_workers=8) as ex:
    for tc, ok, why, out, err, code in ex.map(run, cases):
        if ok:
            passed += 1
        else:
            fails.append((tc, why, out, err, code))
for tc, why, out, err, code in fails:
    print(f"FAIL {tc['name']}: {why}")
    if verbose:
        print("  args:", tc.get("args"))
        print("  input:", repr(tc.get("input"))[:300])
        print("  want out:", repr(tc.get("expected"))[:400])
        print("  got  out:", repr(out)[:400])
        if tc.get("error") or err:
            print("  want err:", repr(tc.get("error"))[:300])
            print("  got  err:", repr(err)[:300])
print(f"{passed}/{len(cases)} passed")
if "--fail-list" in args:
    open(args[args.index("--fail-list") + 1], "w").write("\n".join(f[0]["name"] for f in fails))
