"""Jalankan graph klaim langsung, tanpa alat bantu.

    uv run app.py
    uv run app.py "Proses klaim KLM-002"
"""

import sys

from app.graph import graph

permintaan = sys.argv[1] if len(sys.argv) > 1 else "Proses klaim KLM-002"

hasil = graph.invoke({"permintaan": permintaan})
print(hasil)
