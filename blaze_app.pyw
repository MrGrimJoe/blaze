"""Double-click (or run with pythonw) to open Blaze without a console window. The installer's shortcut runs this."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from blaze.launcher import main

raise SystemExit(main())
