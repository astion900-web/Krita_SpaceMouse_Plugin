from krita import Krita
from .spacemouse_plugin import SpaceMouseExtension

Krita.instance().addExtension(SpaceMouseExtension(Krita.instance()))