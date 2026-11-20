# Rencana: menyesuaikan lab dengan scope GGF Agentic AI Engineering Training

Acuan: dokumen *Handover Trainer: GGF Agentic AI Engineering Training* (20 November 2026).
Keputusan yang sudah diambil:

- Domain inti tetap **klaim reimbursement**. Use case GGF per batch dipakai di **capstone Hari 3**.
- LAB.md **disusun ulang per Hari 1 / 2 / 3** mengikuti rundown GGF. Nomor langkah berubah.
- Tracing: **LangSmith** sebagai utama + **tracer lokal (JSONL)** yang tetap jalan tanpa internet.
- Dikerjakan **bertahap per hari**. Setiap tahap: kode di LAB.md, test, kunci jawaban, contoh output terverifikasi.

Status: **Tahap A dan B selesai.** Hari 1 lengkap (function calling, MCP, retrieval sebagai tool, evaluasi). Berikutnya Tahap C (tracing, FastAPI + Docker).

---

## 1. Peta scope GGF → lab

| Scope GGF | Hari | Status sekarang | Rencana |
|---|---|---|---|
| Workflow vs agent, routing, planner-executor, HITL, kapan agent tidak perlu | 1 | Routing ada (L4); planner & HITL ada tapi di belakang | Konsep di Hari 1, implementasi HITL tetap di Hari 2 (butuh checkpointer) |
| Structured output | 1 | Ada (L7) | Dipindah ke Hari 1 |
| **Function calling** | 1 | **Belum** (tool dipanggil kode, bukan LLM) | **Langkah baru** |
| **MCP** (wajib) | 1 | **Belum** | **Langkah baru** + MCP server sintetis |
| RAG, **retrieval sebagai tool** | 1 | RAG ada (L9), tapi berupa node tetap | Dipindah ke Hari 1 + dibungkus sebagai tool |
| **Evaluasi dasar dengan test case** | 1 | **Belum** (yang ada pytest kode) | **Langkah baru** |
| Supervisor, orchestrator-workers, handoff | 2 | Ada (L6 `Send`, L16 pola) | Supervisor memakai agent Hari 1 sebagai worker |
| State, checkpoint, retry, resume | 2 | Ada (L11, L13) | Tetap |
| Reflection, evaluator-optimizer | 2 | Ada (L10) | Tetap |
| **Tracing** | 2 | **Belum** (hanya disinggung lewat Studio) | **Langkah baru** |
| **Deploy FastAPI + Docker** | 2 | **Belum** | **Langkah baru** + Dockerfile template |
| Guardrail input | 3 | Ada (L8, injeksi lewat dokumen) | Dipindah ke Hari 3 |
| Guardrail **output**, **data confidential** | 3 | **Belum** | **Langkah baru** |
| Injeksi lewat **tool & MCP server**, **least privilege** | 3 | **Belum** | **Langkah baru** |
| **Secret management** | 3 | **Belum** | **Langkah baru** |
| Approval aksi berisiko | 3 | Ada (L12: `bayar` setelah persetujuan) | Diperluas: tool tulis via MCP wajib approval |
| Capstone per use case batch | 3 | **Belum** | Template capstone + panduan ganti domain |

---

## 2. Susunan langkah baru

Kolom "Asal" = nomor langkah di LAB.md sekarang. **BARU** = ditulis dari nol.

### Langkah 0 — Persiapan (sebelum Hari 1, bersama pre-reading)

| # | Langkah | Asal | Isi |
|---|---|---|---|
| 0 | Persiapan | 0 | uv, `.env`, mock vs live, **gateway rubythalib.ai (DeepSeek V4.1 Flash)**, cek Docker |

### Hari 1 — Single agent: workflow, function calling, MCP, RAG, evaluasi

| # | Langkah | Asal | Isi |
|---|---|---|---|
| 1 | Graph pertama + `app.py` | 1 | State, node, edge, `stream`, superstep |
| 2 | Node kedua: membaca data | 2 | Tool = fungsi biasa |
| 3 | Aturan bisnis dan reducer | 3 | Keputusan oleh kode |
| 4 | Routing: conditional edge | 4 | Pola **routing**; diskusi "workflow vs agent, kapan agent tidak perlu" |
| 5 | LLM: mock vs live, structured output | 7 | Router LLM dengan Pydantic |
| 6 | **Function calling: agent asisten** | **BARU** | `bind_tools`, `ToolNode`, `tools_condition`, loop ReAct. Agent `asisten` menjawab pertanyaan bebas ("status KLM-003 apa, dan sisa anggaran Sari berapa?") dengan memilih tool sendiri. Mock: model tiruan yang menghasilkan `tool_calls` deterministik. |
| 7 | **MCP: aplikasi internal lewat MCP server** | **BARU** | `mcp_server/hr_finance.py` (FastMCP, stdio): tool `profil_karyawan`, `sisa_anggaran`, `riwayat_klaim`. Client: `langchain-mcp-adapters`. Agent `asisten` memakai tool dari MCP server, bukan import langsung. Inspeksi dengan MCP Inspector. |
| 8 | RAG ChromaDB + **retrieval sebagai tool** | 9 | Chunking, embedding, Chroma; `cari_kebijakan` jadi tool untuk `asisten` |
| 9 | **Evaluasi dasar dengan test case** | **BARU** | `eval/kasus.jsonl` (input → rute / keputusan / tool yang harus dipanggil), `eval.py` menghitung skor per kategori. Dijalankan di mock dan live; dibahas kenapa skor live berubah-ubah. |

Hasil akhir Hari 1: satu graph dengan router → (jalur klaim workflow) atau (agent `asisten` dengan tool lokal + MCP + RAG), plus skor evaluasi.

### Hari 2 — Multi-agent, state, reflection, tracing, deployment

| # | Langkah | Asal | Isi |
|---|---|---|---|
| 10 | Paralel: fan-out dan join | 5 | |
| 11 | Orchestrator-workers dengan `Send` | 6 | |
| 12 | Memo oleh LLM + evaluator-optimizer | 8 (tanpa guardrail) + 10 | Reflection, batas iterasi |
| 13 | Checkpointer, thread, time travel | 11 | |
| 14 | Human-in-the-loop | 12 | |
| 15 | Retry, idempotensi, crash lalu resume | 13 | |
| 16 | Multi-agent: supervisor, handoff, planner-executor | 16 | Supervisor (LLM) membagi kerja ke agent `asisten` dan graph klaim |
| 17 | Streaming | 14 | Dipakai lagi di endpoint SSE |
| 18 | **Tracing** | **BARU** | LangSmith (`LANGSMITH_TRACING`, project per peserta) + tracer lokal JSONL (callback handler) yang jalan offline. Membaca trace: latensi, token, tool call. |
| 19 | **Deploy: FastAPI + Docker** | **BARU** | `api.py`: `POST /klaim`, `POST /klaim/{thread}/lanjut`, `GET /klaim/{thread}`, `GET /klaim/{thread}/stream` (SSE). `Dockerfile` + `docker-compose.yml` (volume untuk SQLite & Chroma, `.env` lewat env_file). Cadangan: Google Cloud Shell. |
| 20 | Debugging di LangGraph Studio | 15 | Dipadatkan; Studio sebagai alat debug, bukan deploy |

### Hari 3 — Hardening, security, capstone

| # | Langkah | Asal | Isi |
|---|---|---|---|
| 21 | Guardrail input dan output | 8 (guardrail) + **BARU** | Input: injeksi lewat dokumen (KLM-004). Output: memo tidak boleh mengubah keputusan, tidak boleh membocorkan data. |
| 22 | **Data confidential** | **BARU** | Field sensitif sintetis (no. rekening, NIK) di data karyawan; redaksi sebelum masuk prompt / trace / log; uji kebocoran di eval. |
| 23 | **Injeksi lewat tool & MCP server, least privilege** | **BARU** | MCP server "nakal" (deskripsi tool dan hasil tool berisi instruksi). Allowlist tool per agent, MCP server read-only vs write, validasi hasil tool. |
| 24 | **Approval aksi berisiko + secret management** | 12 (diperluas) + **BARU** | Tool tulis (`ajukan_pembayaran` via MCP) wajib `interrupt`. Secret: `.env` / env var, `SecretStr`, tidak bocor ke log/trace/image Docker, `.dockerignore`. |
| 25 | **Capstone** | **BARU** | Template: ganti `data/`, dokumen RAG, dan MCP server dengan use case batch (perkebunan / pabrik / distribusi); checklist presentasi (demo + rencana implementasi). |

Langkah 17 lama (LLM sungguhan) dilebur ke Langkah 0 dan 5, karena pelatihan memakai gateway live sejak Hari 1. Mode mock tetap ada untuk test, untuk peserta yang saldo tokennya habis, dan untuk berjaga kalau internet di Lampung tidak stabil.

---

## 3. Perubahan teknis

- **Dependency baru:** `mcp==2.3.0` (dikunci eksplisit), `fastapi` (Tahap C). **`langchain-mcp-adapters` tidak dipakai:** versi terbarunya mensyaratkan `mcp<2`, sedangkan `langgraph-api` (server Studio) mensyaratkan `mcp>=2.3`. Sebagai gantinya ada adapter kecil `app/mcp_klien.py` (SDK `mcp` resmi).
- **Konfigurasi LLM:** default `.env.example` diganti ke gateway rubythalib.ai + DeepSeek V4.1 Flash (**butuh base URL dan nama model persis dari Anda**).
- **File baru di root:** `mcp_server/`, `eval/`, `api.py`, `Dockerfile`, `docker-compose.yml`, `.dockerignore`.
- **Test:** `test_langkah01.py` … `test_langkah25.py` dinomori ulang mengikuti susunan baru. Pembangun kunci tetap dipakai, jadi kunci langkah N diuji dengan test 1..N.
- **Data sintetis:** tambah field confidential di `karyawan.json` (Hari 3), dataset eval, dan data riwayat klaim untuk MCP server.

---

## 4. Urutan pengerjaan

1. **Tahap A: susun ulang tanpa materi baru.** Pindahkan langkah lama ke urutan baru, nomori ulang test dan kunci, pastikan semuanya lolos. Ini fondasi yang aman sebelum menambah materi.
2. **Tahap B: Hari 1 baru.** Function calling, MCP, retrieval sebagai tool, evaluasi.
3. **Tahap C: Hari 2 baru.** Tracing, FastAPI + Docker.
4. **Tahap D: Hari 3 baru.** Guardrail output, data confidential, injeksi lewat tool/MCP + least privilege, secret management, capstone.

Setiap tahap selesai dengan `scripts/bangun_kunci.py --uji --output` lolos dan satu commit.

---

## 5. Yang perlu Anda putuskan atau kirim

1. **Base URL dan nama model** gateway rubythalib.ai untuk DeepSeek V4.1 Flash.
2. **Realistiskah rundown Hari 1?** (Ini juga pertanyaan Amar no. 4.) Dengan susunan di atas, Hari 1 berisi 9 langkah. Langkah 1–4 bisa dipercepat jika peserta sudah mengerjakan sebagian saat pre-reading.
3. **Pre-reading material** (H-7) belum termasuk rencana ini. Mau saya buatkan juga setelah lab selesai?
4. **Use case batch dari GGF** baru masuk H-14. Template capstone (Langkah 25) dibuat generik dulu, lalu disesuaikan saat dokumentasi masuk.
