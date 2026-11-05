"""
Checks every URL name used in templates and Python files against the real
URL configuration, so errors like  'resumeapp' is not a registered namespace
are found in one go instead of one page at a time.

Run from the folder that contains manage.py:

    python manage.py shell -c "exec(open('check_urls.py', encoding='utf-8').read())"
"""
import re
from pathlib import Path

from django.urls import NoReverseMatch, reverse

TEMPLATE_TAG = re.compile(r"\{%\s*url\s+(['\"])([^'\"]+)\1")
PYTHON_CALL = re.compile(r"(?:redirect|reverse)\(\s*(['\"])([^'\"]+)\1")


def problem(name):
    """Return None if the name can be reversed, else the error message."""
    error = None
    for args in ([], [1]):
        try:
            reverse(name, args=args)
            return None
        except NoReverseMatch as exc:
            error = str(exc)
    return error


files = list(Path("resumeapp").rglob("*.html"))
files += [
    p for p in Path("resumeapp").glob("*.py")
    if not p.name.startswith("test") and p.name != "tests.py"
]

checked, failures = 0, []
for path in sorted(files):
    text = path.read_text(encoding="utf-8")
    pattern = TEMPLATE_TAG if path.suffix == ".html" else PYTHON_CALL
    for match in pattern.finditer(text):
        name = match.group(2)
        checked += 1
        error = problem(name)
        if error:
            line = text.count("\n", 0, match.start()) + 1
            failures.append((path, line, name, error))

print("Checked %d URL references in %d files." % (checked, len(files)))
if failures:
    print("PROBLEMS FOUND:")
    for path, line, name, error in failures:
        print("  %s line %d: '%s'\n      %s" % (path, line, name, error))
else:
    print("All URL names resolve.")