# langgraph-klaim-lab

Lab belajar **LangGraph dari nol, langkah demi langkah**. Satu proyek utuh: agent **klaim reimbursement karyawan**.

Kamu mulai dari graph 1 node (1 superstep), lalu menambah satu konsep per langkah sampai graph lengkap:

> state & superstep → edge berurutan → reducer → conditional edge → paralel & join → map-reduce `Send` → LLM structured output → guardrail → **RAG ChromaDB** → loop evaluator-optimizer → checkpointer & time travel → human-in-the-loop (`interrupt`) → `RetryPolicy` & idempotensi → streaming → **LangGraph Studio** → supervisor / handoff / planner → LLM sungguhan

Domainnya jauh lebih sederhana daripada `ggf-qc-agent`, tapi keluasan materi LangGraph-nya sama.

👉 **Mulai dari [`LAB.md`](LAB.md)** (Langkah 0–17, lengkap dengan kode, contoh output, eksperimen, dan test).

## Quick start

```bash
cd ~/Learning/langgraph-klaim-lab
uv sync
cp -n .env.example .env                       # LLM_MODE=mock: tanpa API key
KUNCI=akhir uv run cek                        # semua kunci jawaban lolos = environment sehat
KUNCI=akhir uv run chat                       # coba sistem jadinya: ketik "Proses klaim KLM-001"
mkdir -p app && touch app/__init__.py         # lalu kerjakan Langkah 1
```

## Alat bantu

| Perintah | Kegunaan |
|---|---|
| `uv run chat` | **Chat di terminal**: ketik permintaan, dapat jawaban; interrupt dijawab langsung sebagai atasan; kode `app/` dimuat ulang otomatis |
| `uv run lihat "Proses klaim KLM-002"` | Jalankan graph di `app/` dan tampilkan **setiap superstep**: node yang jalan, apa yang ditulis ke state, node berikutnya |
| `uv run lihat ... --ringkas` / `--lengkap` | Satu baris per superstep / isi state lengkap |
| `uv run lihat --thread t1 --lanjut setujui` | Jawab interrupt (human-in-the-loop) dari proses baru |
| `uv run lihat --thread t1 --riwayat` / `--dari <id>` | Daftar checkpoint / time travel (replay, fork) |
| `uv run lihat ... --mode updates` | Stream mentah (`updates`, `values`, `custom`, `messages`, `debug`) |
| `uv run lihat --gambar` | Gambar graph (ASCII + Mermaid) |
| `uv run cek 5` | Test langkah 1 sampai 5 (`--hanya` untuk langkah 5 saja) |
| `uv run langgraph dev` | LangGraph Studio di browser |
| F5 di VS Code | Debugger dengan breakpoint di node (`.vscode/launch.json`) |
| `KUNCI=5 uv run lihat ...` / `KUNCI=5 uv run cek 5` | Jalankan / uji kunci jawaban langkah 5 |

## Isi folder

```
langgraph-klaim-lab/
├── LAB.md               # panduan lab langkah demi langkah  ← mulai di sini
├── app/                 # KAMU yang menulis isinya
├── tests/               # test_langkah01.py ... test_langkah17.py
├── lab/                 # alat bantu: chat.py, lihat.py, cek.py, kunci.py (tidak perlu ditulis)
├── data/
│   ├── klaim.json       # 5 klaim latihan (KLM-001 ... KLM-005)
│   ├── karyawan.json    # profil + sisa anggaran ("API HR")
│   ├── kebijakan.json   # aturan yang dipakai kode
│   └── kebijakan/*.md   # aturan versi teks (untuk RAG ChromaDB)
├── _kunci/langkah-NN/   # kunci jawaban per langkah (dibangkitkan dari LAB.md)
├── _arsip/              # versi lama lab (sebelum dirombak) + kode app/ lamamu
├── .env.example         # konfigurasi; default LLM_MODE=mock
└── pyproject.toml, uv.lock
```

## Untuk pengelola lab

Semua kode kunci jawaban berasal dari blok kode di LAB.md (komentar `<!-- kode: ... -->`). Setelah mengubah LAB.md:

```bash
uv run python -m lab.kunci --uji --output   # bangun ulang _kunci/, uji langkah N dengan test 1..N, isi contoh output
```

Semua data di `data/` sintetis.
