# langgraph-klaim-lab

Lab belajar **LangGraph dari nol, langkah demi langkah**. Satu proyek utuh: agent **klaim reimbursement karyawan**.

Kamu mulai dari graph 1 node (1 superstep), lalu menambah satu konsep per langkah sampai sistem lengkap, dibagi mengikuti 3 hari pelatihan:

> **Hari 1:** state & superstep → reducer → routing → structured output → **function calling** → **MCP** → **RAG** (juga sebagai tool) → **evaluasi**
>
> **Hari 2:** paralel & `Send` → evaluator-optimizer → checkpoint & time travel → human-in-the-loop → retry & resume → supervisor / handoff / planner → streaming → **tracing** → **FastAPI + Docker** → Studio
>
> **Hari 3:** guardrail input/output → **data confidential** → injeksi lewat tool/MCP & **least privilege** → **approval aksi berisiko** & **secret management** → capstone

Domainnya jauh lebih sederhana daripada `ggf-qc-agent`, tapi keluasan materi LangGraph-nya sama.

👉 **Mulai dari [`LAB.md`](LAB.md)** (Langkah 0–25, dibagi per Hari 1/2/3 pelatihan, lengkap dengan kode, contoh output, eksperimen, dan test).

## Quick start

```bash
cd ~/Learning/langgraph-klaim-lab
uv sync
cp -n .env.example .env                       # LLM_MODE=mock: tanpa API key
mkdir -p app && touch app/__init__.py         # lalu kerjakan Langkah 1 (kamu menulis app/ dan app.py)
```

## Cara menjalankan

Tidak ada perintah bantu khusus. Semuanya file Python biasa dan `pytest`:

| Perintah | Kegunaan |
|---|---|
| `uv run app.py "Proses klaim KLM-002"` | Jalankan graph dan tampilkan **setiap superstep**: node yang jalan dan apa yang ditulis ke state. `app.py` kamu tulis sendiri di Langkah 1 |
| `uv run app.py --chat` | **Chat interaktif**: ketik permintaan berkali-kali. Mulai Langkah 13 setiap permintaan tersimpan sebagai thread, mulai Langkah 14 bisa menjawab persetujuan atasan |
| `uv run app.py --gambar` | Gambar graph (ASCII) |
| `uv run app.py "..." --thread t1` | Pakai thread tertentu (Langkah 13) |
| `uv run app.py --thread t1 --riwayat` / `--dari <id>` / `--status` | Daftar checkpoint / time travel / state terakhir (Langkah 13) |
| `uv run app.py --thread t1 --lanjut setujui` | Jawab interrupt (human-in-the-loop, Langkah 14) |
| `uv run evaluasi.py` | Evaluasi perilaku agent dengan dataset kasus (Langkah 9) |
| `uv run app.py --mcp` | Daftar tool yang ditawarkan MCP server (Langkah 7) |
| `uv run mcp_server/hr_finance.py --http` + `MCP_HR_FINANCE_URL=http://127.0.0.1:8001/mcp` | MCP lewat Streamable HTTP: server jalan sendiri, agent terhubung lewat URL (Langkah 7.4) |
| `uv run app.py --potongan` / `--rag "..."` | Potongan dokumen / cari langsung di ChromaDB (Langkah 8) |
| `uv run pytest tests/test_langkah05.py` | Test langkah 5 (`uv run pytest` = semua test) |
| `uv run app.py --jejak <thread>` | Tracer lokal: pohon node, LLM, dan tool beserta durasinya (Langkah 18) |
| `uv run api.py` | API HTTP di http://127.0.0.1:8000/docs (Langkah 19) |
| `docker compose up --build` | Jalankan API di Docker (Langkah 19) |
| `uv run app.py --audit <thread>` | Audit data confidential di checkpoint dan jejak (Langkah 22) |
| `uv run langgraph dev` | LangGraph Studio di browser |
| F5 di VS Code | Debugger dengan breakpoint di node (`.vscode/launch.json`) |
| `cd _kunci/langkah-05 && uv run app.py "..."` | Jalankan kunci jawaban langkah 5 |

## Isi folder

```
langgraph-klaim-lab/
├── LAB.md               # panduan lab langkah demi langkah  ← mulai di sini
├── app/                 # KAMU yang menulis isinya
├── app.py               # KAMU yang menulis: menjalankan graph dari terminal
├── mcp_server/         # KAMU yang menulis: MCP server (HR/Finance, vendor "nakal", template capstone)
├── evaluasi.py         # KAMU yang menulis: evaluasi agent + kasus_eval.jsonl (Langkah 9)
├── api.py, Dockerfile  # KAMU yang menulis: API HTTP + kemasan Docker (Langkah 19)
├── tests/               # test_langkahNN.py, satu file per langkah
├── scripts/             # bangun_kunci.py: alat pengelola lab (membangun _kunci/ dari LAB.md)
├── data/
│   ├── klaim.json       # 5 klaim latihan (KLM-001 ... KLM-005)
│   ├── karyawan.json    # profil + sisa anggaran ("API HR")
│   ├── kebijakan.json   # aturan yang dipakai kode
│   └── kebijakan/*.md   # aturan versi teks (untuk RAG ChromaDB)
├── _kunci/langkah-NN/   # kunci jawaban per langkah: app/, app.py, langgraph.json (dibangkitkan dari LAB.md)
├── _arsip/              # versi lama lab (sebelum dirombak) + kode app/ lamamu
├── .env.example         # konfigurasi; default LLM_MODE=mock
└── pyproject.toml, uv.lock
```

## Untuk pengelola lab

Semua kode kunci jawaban berasal dari blok kode di LAB.md (komentar `<!-- kode: ... -->`). Setelah mengubah LAB.md:

```bash
uv run scripts/bangun_kunci.py --uji --output   # bangun ulang _kunci/, uji langkah N dengan test 1..N, isi contoh output
```

Semua data di `data/` sintetis.
