"""
SE7O-SNA Panel v3.0 - Modular Architecture
"""
__version__ = "3.0.0"
__author__ = "SE7O"

from app.state import state  # noqa: E402,F401

try:
    import uvloop
    uvloop.install()
except ImportError:
    pass
