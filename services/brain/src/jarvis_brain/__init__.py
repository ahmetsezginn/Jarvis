"""JARVIS local intent runtime and trusted Core client."""

from jarvis_brain.core.client import JarvisCoreClient, open_application
from jarvis_brain.intelligence.runtime import JarvisBrain

__all__ = ["JarvisBrain", "JarvisCoreClient", "open_application"]
__version__ = "0.2.0"
