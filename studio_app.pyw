"""Opens Blaze Studio (the desktop window) without a console window. The installer's second shortcut runs this."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from blaze.launcher import main_studio

raise SystemExit(main_studio())
