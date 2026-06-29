import os
import sys
from pathlib import Path

import uvicorn

if __name__ == "__main__":
    # Ensure the `src/` source root is on sys.path so bare imports like
    # `from api import app` resolve when launched via `python -m src`.
    src_root = str(Path(__file__).resolve().parent)
    if src_root not in sys.path:
        sys.path.insert(0, src_root)

    from api import app

    port = int(os.environ.get("PORT", "8001"))
    uvicorn.run(app, host="0.0.0.0", port=port, reload=False)
