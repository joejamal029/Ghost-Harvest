"""Quick validation of all security fixes."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import inspect
import ghost_harvest.utils as u_mod
import ghost_harvest.scanner as s_mod
import ghost_harvest.hasher as h_mod
import ghost_harvest.app as a_mod
import ghost_harvest.command as c_mod
import ghost_harvest.manifest as m_mod
from ghost_harvest.command import build_args
from ghost_harvest.constants import DANGEROUS_EXTS, EXEC_SIGS
from ghost_harvest.utils import elevate
from ghost_harvest.scanner import has_double_extension
from pathlib import Path

passed = 0
failed = 0

def check(name, condition):
    global passed, failed
    if condition:
        print(f"  ✅  {name}")
        passed += 1
    else:
        print(f"  ❌  {name}")
        failed += 1

print("=" * 56)
print("  GhostHarvest v2.1 — Security Validation")
print("=" * 56)

# S1: build_args returns list, not string
print("\n[S1] Command injection prevention (shell=False)")
args = build_args("C:\\source", "C:\\dest", 8,
                  restartable=True, dry_run=False, block_exts=True,
                  skip_bloat=True, custom_xd="", save_log=True)
check("build_args returns a list", isinstance(args, list))
check("First arg is 'robocopy'", args[0] == "robocopy")

# Injection path stays as single element
evil = 'C:\\foo" & net user hacker /add & "'
args2 = build_args(evil, "C:\\dest", 8)
check("Injection path is single list element", args2[1] == evil)

# S2: Extension parsing (removeprefix fix)
print("\n[S2] Extension parsing (removeprefix fix)")
blocked_set = {"wsf", "scr", "msi", "js", "exe", "ps1", "dll", "sys"}
check("Double extension detected (.pdf.exe)", has_double_extension(Path("report.pdf.exe"), blocked_set))
check("Single dangerous extension not flagged", not has_double_extension(Path("report.exe"), blocked_set))
check("Safe double extension not flagged", not has_double_extension(Path("report.txt.pdf"), blocked_set))

# S3: elevate() signature — only accepts script path
print("\n[S3] UAC elevation safety")
try:
    src = inspect.getsource(elevate)
except OSError:
    print("  ⚠  Cannot inspect elevate() source – skipping S3 checks")
    src = ""
if src:
    check("elevate() does NOT use ' '.join(sys.argv)", "\" \".join(sys.argv)" not in src)
    check("elevate() only passes sys.argv[0]", "sys.argv[0]" in src)
    check("elevate() uses resolved script path", "Path(sys.argv[0]).resolve()" in src)
    check("elevate() uses quoted script path parameter", "f'\"{script}\"'" in src)
else:
    print("  ⚠  S3 checks skipped – source unavailable")

# S4: /XJ junction exclusion
print("\n[S4] Junction point exclusion")
check("/XJ in default args", "/XJ" in args)

# S5: No bare except in codebase
print("\n[S5] Exception handling")
for mod_name, mod in [
    ("utils", u_mod), ("scanner", s_mod), ("hasher", h_mod),
    ("app", a_mod), ("command", c_mod), ("manifest", m_mod)
]:
    src_lines = inspect.getsource(mod).split("\n")
    bare_excepts = [ln.strip() for ln in src_lines if ln.strip().startswith("except:")]
    check(f"No bare 'except:' in {mod_name}.py", len(bare_excepts) == 0)

# S6: Expanded extension list
print("\n[S6] Expanded dangerous extensions")
ext_set = {e.removeprefix("*.").lower() for e in DANGEROUS_EXTS}
for must_have in [
    "dll", "sys", "cpl", "chm", "docm", "xlsm", "pptm", "psc1", "url"
]:
    check(f"'.{must_have}' in blocklist", must_have in ext_set)

# S7: Expanded magic signatures
print("\n[S7] Expanded magic byte signatures")
check(f"{len(EXEC_SIGS)} signatures (was 5, now 16)", len(EXEC_SIGS) >= 16)
labels = {label for _, _, label in EXEC_SIGS}
for must_have in [
    "CAB", "OLE", "ZIP", "RAR", "7-Zip", "CHM", "SWF", "LNK", "Shebang"
]:
    found = any(must_have in label_str for label_str in labels)
    check(f"Signature for {must_have}", found)

# Test _parse_robocopy_bytes (BUG-004)
print("\n[BUG-004] Pre-flight size parser")
parse = a_mod.GhostHarvest._parse_robocopy_bytes
check("Parse simple commas (12,345,678)", parse("Bytes : 12,345,678") == 12345678)
check("Parse suffix 'm' (12,345,678 m)", parse("Bytes : 12,345,678 m") == 12345678 * 1024**2)
check("Parse suffix 'k' and decimal dot (12,345.6 k)", parse("Bytes : 12,345.6 k") == int(12345.6 * 1024))
check("Parse suffix 'm' and decimal comma (12,3 m)", parse("Bytes : 12,3 m") == int(12.3 * 1024**2))
check("Parse simple raw digits (12345678)", parse("Bytes : 12345678") == 12345678)

# Summary
print(f"\n{'=' * 56}")
print(f"  {passed} passed · {failed} failed")
print(f"{'═' * 56}")
