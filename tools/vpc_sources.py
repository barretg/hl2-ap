"""List the source files a Valve VPC project compiles, for our CMake build.

Valve builds the SDK with VPC, which generates Visual Studio projects. We build
with CMake and clang-cl instead, but the file lists stay Valve's: this reads the
.vpc scripts and prints the C/C++ sources one per line, so the CMake build never
carries a hand-copied list that drifts from the SDK.

Only what the SDK's server, client, tier1 and mathlib scripts use is supported:
$Macro, $Include, $Folder, $File, -$File and [conditions]. Per-file
$Configuration blocks are skipped (they only set precompiled-header options).

    python tools/vpc_sources.py <sdk>/src/game/server/server_episodic.vpc
"""

import argparse
import os
import re
import sys

# The platform we build for, as VPC sees it: 32-bit Windows, Source SDK, a
# modern compiler (VS2013 is the newest VPC knows about).
DEFAULT_DEFINES = {"WIN32", "WINDOWS", "SOURCESDK", "VS2013"}

SOURCE_EXTS = (".cpp", ".c", ".cc", ".cxx")

TOKEN = re.compile(r'"(?:[^"\\]|\\.)*"|\[[^\]]*\]|[{}]|[^\s{}"\[]+')


def eval_condition(cond, defines):
    """Evaluate a VPC condition such as `$WIN32 && !$X360`."""
    expr = cond.strip()[1:-1]
    expr = re.sub(r"\$(\w+)", lambda m: str(m.group(1).upper() in defines), expr)
    expr = expr.replace("&&", " and ").replace("||", " or ")
    expr = re.sub(r"!(?!=)", " not ", expr)
    return bool(eval(expr, {"__builtins__": {}}))


class Resolver:
    def __init__(self, defines):
        self.defines = defines
        self.macros = {}
        self.files = []
        self.libs = []

    def expand(self, text):
        for _ in range(8):
            new = re.sub(r"\$(\w+)",
                         lambda m: self.macros.get(m.group(1).upper(), m.group(0)), text)
            if new == text:
                break
            text = new
        return text

    def path(self, raw, base_dir):
        p = self.expand(raw.strip('"')).replace("\\", "/")
        return os.path.normpath(os.path.join(base_dir, p))

    def load(self, vpc, project_dir=None):
        vpc = os.path.normpath(vpc)
        # Paths in included scripts resolve against the top-level project's dir.
        project_dir = project_dir or os.path.dirname(vpc)
        with open(vpc, encoding="utf-8", errors="replace") as f:
            text = re.sub(r"//[^\n]*", "", f.read())
        # `\` at line end continues a $File list onto the next line.
        text = re.sub(r"\\[ \t]*\r?\n", " ", text)
        tokens = TOKEN.findall(text)
        self.walk(tokens, project_dir)

    def walk(self, toks, project_dir):
        i = 0
        n = len(toks)

        def cond_at(j):
            return j < n and toks[j].startswith("[")

        def skip_block(j):
            depth = 0
            while j < n:
                if toks[j] == "{":
                    depth += 1
                elif toks[j] == "}":
                    depth -= 1
                    if depth == 0:
                        return j + 1
                j += 1
            return j

        while i < n:
            t = toks[i]
            key = t.lower()
            if key == "$macro":
                name, value = toks[i + 1], toks[i + 2].strip('"')
                i += 3
                ok = True
                if cond_at(i):
                    ok = eval_condition(toks[i], self.defines)
                    i += 1
                if ok:
                    self.macros[name.upper()] = value
            elif key in ("$macrorequired", "$macrorequiredallowempty"):
                i += 2
                while i < n and toks[i].startswith('"'):
                    i += 1
            elif key == "$include":
                target = toks[i + 1]
                i += 2
                ok = True
                if cond_at(i):
                    ok = eval_condition(toks[i], self.defines)
                    i += 1
                if ok:
                    inc = self.path(target, project_dir)
                    if os.path.exists(inc):
                        self.load(inc, project_dir)
            elif key in ("$file", "-$file", "$lib", "$libexternal", "$implib",
                         "$implibexternal"):
                # A $File may list several quoted names; a $Lib names one,
                # quoted or bare.
                i += 1
                names = [toks[i]]
                i += 1
                while key.endswith("$file") and i < n and toks[i].startswith('"'):
                    names.append(toks[i])
                    i += 1
                ok = True
                if cond_at(i):
                    ok = eval_condition(toks[i], self.defines)
                    i += 1
                if i < n and toks[i] == "{":
                    i = skip_block(i)
                if not ok:
                    continue
                if key == "$file":
                    for nm in names:
                        p = self.path(nm, project_dir)
                        if p.lower().endswith(SOURCE_EXTS) and p not in self.files:
                            self.files.append(p)
                elif key == "-$file":
                    for nm in names:
                        p = self.path(nm, project_dir)
                        if p in self.files:
                            self.files.remove(p)
                else:
                    self.libs.append(self.expand(names[0].strip('"')))
            elif key in ("$project", "$folder"):
                # `$Project "name"`/`$Folder "name"` [cond] { ... }: walk inside.
                i += 1
                if i < n and toks[i].startswith('"'):
                    i += 1
                ok = True
                if cond_at(i):
                    ok = eval_condition(toks[i], self.defines)
                    i += 1
                if i < n and toks[i] == "{":
                    end = skip_block(i)
                    if ok:
                        self.walk(toks[i + 1:end - 1], project_dir)
                    i = end
            elif key == "$configuration":
                i += 1
                if i < n and toks[i].startswith('"'):
                    i += 1
                if i < n and toks[i] == "{":
                    i = skip_block(i)
            elif t == "{":
                i = skip_block(i)
            else:
                i += 1


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("vpc")
    ap.add_argument("-D", dest="define", action="append", default=[],
                    help="extra VPC condition define (without $)")
    ap.add_argument("--libs", action="store_true", help="print $Lib names instead")
    args = ap.parse_args(argv)
    r = Resolver(DEFAULT_DEFINES | {d.upper() for d in args.define})
    r.load(os.path.abspath(args.vpc))
    out = r.libs if args.libs else r.files
    for item in out:
        print(item.replace(os.sep, "/"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
