import os

os.environ.setdefault("SHIBOKEN_DISABLE", "1")
os.environ.setdefault("PYDEVD_DISABLE_FILE_VALIDATION", "1")

try:
    import six
except Exception:
    six = None

if six is not None:
    importer = getattr(six, "_importer", None)
    if importer is not None and not hasattr(importer, "_path"):
        importer._path = []
