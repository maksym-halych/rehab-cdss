"""Location of the shared data/ folder: <repository root>/data, outside api/.

In Docker, the code is in /app/src/, so this path is /data. docker-compose.yaml mounts data/ there.
"""

from pathlib import Path

# api/src/module_2_reasoning/paths.py → repository root
DATA_DIR = Path(__file__).resolve().parents[3] / "data"
