"""Env knob access with precedence: explicit env var > sport profile default >
global default. Reads the environment at CALL time (tests and per-run repo
secrets rely on this), never at import."""
import os


def knob(name: str, default, profile=None):
    """Return the raw knob value (string, like os.environ); callers cast."""
    if name in os.environ:
        return os.environ[name]
    defaults = getattr(profile, "defaults", None) or {}
    if name in defaults:
        return defaults[name]
    return default
