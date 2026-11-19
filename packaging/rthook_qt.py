"""Runtime hook for FilterLab PyInstaller bundle.

Configures Qt platform plugin paths and PortAudio/libsndfile/SciPy dynamic library resolution
when executing inside a frozen standalone bundle on macOS and Windows.
"""

import os
import sys

if getattr(sys, "frozen", False):
    bundle_dir = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))

    plugin_dirs = [
        os.path.join(bundle_dir, "PySide6", "plugins"),
        os.path.join(bundle_dir, "plugins"),
        os.path.join(bundle_dir, "PySide6", "Qt", "plugins"),
    ]
    for pdir in plugin_dirs:
        if os.path.isdir(pdir):
            os.environ["QT_PLUGIN_PATH"] = pdir
            break

    lib_candidates = [
        os.path.join(bundle_dir, "_sounddevice_data", "portaudio-binaries"),
        os.path.join(bundle_dir, "_soundfile_data"),
        os.path.join(bundle_dir, "numpy.libs"),
        os.path.join(bundle_dir, "scipy.libs"),
    ]
    for lib_dir in lib_candidates:
        if os.path.isdir(lib_dir):
            if sys.platform == "win32":
                os.environ["PATH"] = lib_dir + os.path.pathsep + os.environ.get("PATH", "")
                if hasattr(os, "add_dll_directory"):
                    try:
                        os.add_dll_directory(lib_dir)
                    except Exception:
                        pass
            elif sys.platform == "darwin":
                dyld = os.environ.get("DYLD_LIBRARY_PATH", "")
                os.environ["DYLD_LIBRARY_PATH"] = lib_dir + (":" + dyld if dyld else "")
