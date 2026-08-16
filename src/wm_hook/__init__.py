"""Pre-commit hook packaging for the watermarks-remover text cleaners.

The cleaning logic is not here — it is vendored byte-exact from
service/scripts/ into _vendor/ (see _vendor/VENDORED.json and
tools/watermarks-hook/refresh.sh). Only the commit-time plumbing is in cli.py.
"""
