"""
SE7O-SNA Panel v3.1 - Modular Architecture
"""
__version__ = "3.1.0"
__author__ = "SE7O"

from app.state import state  # noqa: E402,F401

try:
    import uvloop
    uvloop.install()
except ImportError:
    pass
