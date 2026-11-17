# LAB: Bangun Agent Klaim Reimbursement dengan LangGraph, dari Nol

Satu lab, satu proyek utuh. Kamu menulis sendiri seluruh folder `app/` dari file kosong sampai menjadi sistem multi-node yang:

- mengarahkan permintaan (router + LLM + structured output),
- memeriksa item klaim **secara paralel** (fan-out, `Send`, reducer, join),
- memutuskan dengan **aturan kode**, bukan LLM,
- menulis memo dan **menilai dirinya sendiri** (loop evaluator-optimizer dengan batas),
- **berhenti menunggu atasan** (`interrupt` + `Command(resume=...)`),
- **tahan crash** (checkpoint SQLite, resume dari proses lain, `RetryPolicy`, pembayaran idempoten),
- bisa di-**stream** dan di-**debug di LangGraph Studio**,
- plus tiga pola orkestrasi lain (supervisor, handoff, planner-executor).

Cakupan konsepnya sama dengan `ggf-qc-agent`, tapi domainnya jauh lebih sederhana: **klaim reimbursement karyawan**. Semua orang kantoran paham domainnya, jadi perhatianmu bisa penuh ke LangGraph.

> **Cara kerja lab ini:** setiap tahap punya test di `tests/test_tahapXX_*.py`. Test itu adalah **spesifikasi**: tulis kode sampai test tahap itu hijau, baru lanjut. Kunci jawaban ada di `_kunci/app/`. Jangan dibuka sebelum benar-benar buntu (lihat bagian [Kalau buntu](#kalau-buntu)).

---

## Daftar isi

| Tahap | Topik | File yang kamu tulis | Konsep LangGraph | Estimasi |
|---|---|---|---|---|
| 0 | Setup | `app/__init__.py`, `.env` | uv, struktur proyek | 15' |
| 1 | Tool Python biasa | `config.py`, `tools.py` | (belum LangGraph) aturan bisnis yang bisa dites | 45' |
| 2 | State & skema | `state.py` | `TypedDict`, `Annotated` + reducer, Pydantic | 30' |
| 3 | Graph pertama | `nodes.py` (router), graph mini | node, edge, conditional edge, compile, invoke | 45' |
| 4 | LLM & RAG mini | `llm.py`, `jawab_kebijakan` | structured output, mode mock/live, validasi output LLM | 45' |
| 5 | Paralel & map-reduce | `guardrails.py`, 5 node baru | fan-out, `Send`, `input_schema`, join/barrier, superstep | 60' |
| 6 | Evaluator-optimizer | `tulis_memo`, `nilai_memo` | loop dengan batas iterasi | 45' |
| 7 | Human-in-the-loop | `persetujuan`, `bayar`, `selesai`, `graph.py` | `interrupt`, `Command(resume=...)`, efek samping setelah persetujuan | 60' |
| 8 | Checkpoint & CLI | `cli.py`, `buka_sqlite` | `SqliteSaver`, `thread_id`, `get_state`, `get_state_history`, resume lintas proses | 45' |
| 9 | Keandalan | `HR_RETRY`, crash & idempotensi | `RetryPolicy`, node diulang dari awal, kunci idempotensi | 30' |
| 10 | Streaming | (di `cli.py`) | `stream_mode` updates/values/custom, `get_stream_writer` | 20' |
| 11 | LangGraph Studio | `langgraph.json` | `langgraph dev`, breakpoint, edit state, fork, time travel, SDK | 60' |
| 12 | Pola orkestrasi | `pola.py` | supervisor, handoff (`Command(goto=...)`), planner-executor | 45' |
| 13 | (opsional) LLM sungguhan | `.env` | mode live: Sumopod / vLLM / Ollama | 30' |

Total sekitar **9 sampai 11 jam**. Enak dibagi 3 sampai 4 sesi: (0–4), (5–7), (8–11), (12–13).

### Peta konsep ke `ggf-qc-agent`

| Konsep | Di lab ini | Padanan di ggf-qc-agent |
|---|---|---|
| Router + structured output + validasi kode | `router` | `app/agents/router.py` |
| RAG sebagai satu rute | `jawab_kebijakan` (pencarian kata) | `knowledge_agent` (ChromaDB) |
| Fan-out paralel + join | `cek_karyawan` ∥ `periksa_item`×N → `putuskan` | `qc_analyst` ∥ `traceability` → `risk_assessor` |
| Map-reduce dinamis `Send` | `fan_out_item` → `periksa_item` | `fan_out_blocks` → `block_inspector` |
| Keputusan deterministik | `putuskan` | `risk_assessor` |
| Evaluator-optimizer | `tulis_memo` ⇄ `nilai_memo` | `report_writer` ⇄ `evaluator` |
| Human-in-the-loop | `persetujuan` | `human_approval` |
| RetryPolicy | `cek_karyawan` (API HR) | `traceability` (ERP) |
| Idempotensi efek samping | `bayar` | `apply_lot_action` |
| Guardrail prompt injection | `KLM-004` | `LOT-2026-1108-B` |
| Checkpoint SQLite + resume lintas proses | `cli.py` | `app/cli.py` |
| Streaming | `cli.py` | `app/streaming.py` |
| 5 pola orkestrasi | `graph.py` + `pola.py` | `labs/day3_lab5b_orchestration_patterns.py` |
| **Studio** | Tahap 11 | (tidak ada) |

Yang sengaja **tidak** dimasukkan supaya tetap sederhana: FastAPI + Docker (Studio sudah memberimu server API), ChromaDB, observability biaya token.

---

## Studi kasus: klaim reimbursement

Karyawan mengajukan klaim (misalnya biaya perjalanan). Setiap klaim berisi beberapa item. Setiap item punya kategori, jumlah, ada/tidaknya struk, dan keterangan bebas.

**Aturan** (`data/kebijakan.json`, versi teks di `data/kebijakan/*.md`):

| Kategori | Batas per item | Wajib struk |
|---|---|---|
| transport | Rp300.000 | tidak |
| makan | Rp150.000 | tidak |
| hotel | Rp750.000 | ya |
| peralatan | Rp2.500.000 | ya |
| hiburan | tidak bisa diklaim | – |

- Item di atas batas: dibayar **sampai batas** (status `dipotong`).
- Item wajib struk tanpa struk, atau kategori hiburan: **ditolak** (dibayar 0).
- Total disetujui > sisa anggaran tahunan karyawan: klaim **ditolak**.
- Auto-approve hanya bila semua item `ok`, total ≤ **Rp500.000**, dan tidak ada peringatan. Selain itu wajib persetujuan atasan.
- Klaim yang ditolak tidak perlu atasan (tidak ada uang bergerak).

**Lima klaim latihan** (`data/klaim.json`). Hafalkan hasil yang diharapkan, karena test memakainya:

| Klaim | Isi singkat | Hasil yang diharapkan |
|---|---|---|
| KLM-001 | hotel 650rb, makan 180rb, transport 220rb | `setujui_sebagian`, disetujui **Rp1.020.000**, perlu atasan |
| KLM-002 | taksi 85rb, makan 95rb | `setujui_penuh` Rp180.000, **auto-approve** → langsung dibayar |
| KLM-003 | monitor, keyboard tanpa struk, langganan streaming | `setujui_sebagian` Rp2.100.000, perlu atasan |
| KLM-004 | hotel 900rb dengan keterangan **berisi prompt injection** | `setujui_sebagian` Rp1.030.000, peringatan, memo tidak boleh "APPROVED" |
| KLM-005 | total 520rb, sisa anggaran karyawan hanya 400rb | `tolak` otomatis, tanpa atasan |

### Topologi akhir yang akan kamu bangun

```
START → router
router ──klaim───────► muat_klaim
router ──kebijakan───► jawab_kebijakan → END
router ──klarifikasi─► klarifikasi → END

muat_klaim ──────────────► cek_karyawan ─────────┐   (paralel, RetryPolicy)
muat_klaim ──Send×N──────► periksa_item ×N ──────┤   (map)
                                                 ▼
                                              putuskan   (join + reduce, aturan kode)
                                                 ▼
                                   ┌────────► tulis_memo
                                   │             ▼
                     belum lolos ──┴──────── nilai_memo
                                                 │
                    ┌──────── tolak ─────────────┼──────── auto-approve ────────┐
                    ▼                            ▼ perlu atasan                 ▼
                 selesai                    persetujuan (interrupt)  ──setujui──► bayar → selesai → END
                                              │  └──revisi──► tulis_memo
                                              └──tolak──► selesai
```

---

## Aturan main untuk diri sendiri

1. **Ketik sendiri.** Jangan menyalin dari `_kunci/`. Membaca LAB ini dan test boleh, dan memang itu tujuannya.
2. Jalankan **hanya test tahap yang sedang dikerjakan**: `uv run pytest tests/test_tahap03_graph_pertama.py -q`. Test tahap berikutnya pasti merah karena kodenya belum ada.
3. Setelah tahap hijau, jalankan juga semua tahap sebelumnya: `uv run pytest -q tests/test_tahap0[1-3]*`. Pastikan tidak ada yang rusak.
4. Di setiap tahap, kerjakan juga bagian **🔬 Eksperimen**. Bagian itu yang membuat paham, bukan sekadar hijau.
5. Commit tiap tahap selesai (`git init` dulu). Riwayat commit menjadi catatan belajarmu.

---

## Tahap 0 — Setup

**Tujuan:** proyek bisa dijalankan dan test bisa dikoleksi.

```bash
cd ~/Learning/langgraph-klaim-lab
uv sync                       # buat .venv dan pasang versi persis dari uv.lock
cp .env.example .env          # (sudah ada) default LLM_MODE=mock, tanpa API key
mkdir app && touch app/__init__.py
git init && git add -A && git commit -m "tahap 0: kerangka"
KUNCI=1 uv run pytest -q      # kunci jawaban: harus 55 passed (bukti environment sehat)
```

`KUNCI=1` membuat test memakai `_kunci/app` alih-alih `app/` milikmu. Pakai ini untuk mengecek bahwa kegagalan test berasal dari kodemu, bukan dari environment.

**Mode mock:** sepanjang Tahap 1–12 kamu tidak butuh API key. Setiap pemanggilan LLM punya `fallback` deterministik. Ini juga cara yang benar membangun agent: struktur graph dulu, LLM belakangan. Tahap 13 menyalakan LLM sungguhan.

---

## Tahap 1 — Tool Python biasa

**Tujuan:** semua aturan bisnis yang bisa dihitung ada di fungsi Python biasa yang mudah dites. **Belum ada LangGraph.**

> Prinsip: LLM tidak pernah menghitung uang. Kalau suatu keputusan bisa ditulis sebagai `if`, tulis sebagai `if`.

### File `app/config.py`

- `ROOT`: folder yang berisi `pyproject.toml`. Cari dengan menelusuri `Path(__file__).resolve().parents`. Ini supaya path data benar dari mana pun kode dijalankan (termasuk dari `_kunci/` dan dari server Studio).
- Panggil `load_dotenv(ROOT / ".env")` sekali di level modul.
- `@dataclass(frozen=True) class Settings` dengan field: `llm_mode, llm_base_url, llm_api_key, llm_model, llm_temperature, max_revisi, runtime_dir, data_dir, hr_gagal_n_kali, crash_setelah_bayar, mock_draf_pertama_kurang`.
- `get_settings() -> Settings`: **baca `os.getenv` setiap kali dipanggil** (jangan di-cache), supaya test bisa mengubah env. `runtime_dir` relatif → jadikan absolut terhadap `ROOT`, lalu `mkdir(parents=True, exist_ok=True)`. `data_dir = ROOT / "data"`.

### File `app/tools.py`

| Fungsi | Perilaku |
|---|---|
| `ambil_klaim(claim_id) -> dict \| None` | Dari `data/klaim.json`. Kembalikan `{"claim_id": claim_id, **klaim}`, atau `None` bila tidak ada. |
| `ambil_kebijakan() -> dict` | Isi `data/kebijakan.json`. |
| `periksa_item(item, kebijakan) -> dict` | Kembalikan `{item_id, kategori, diajukan, disetujui, status, alasan}`. `status` ∈ `ok` / `dipotong` / `ditolak` sesuai tabel aturan. Urutan cek: kategori tidak dikenal atau batas 0 → ditolak; wajib struk tapi tidak ada → ditolak; melebihi batas → dipotong; selain itu ok. |
| `format_rupiah(n) -> str` | `1050000` → `"Rp1.050.000"`. |
| `class HRTimeoutError(RuntimeError)` | Error API HR. |
| `ambil_profil_karyawan(karyawan_id) -> dict` | Dari `data/karyawan.json`, kembalikan `{"karyawan_id": ..., **profil}`. **Simulasi API tidak stabil:** simpan penghitung panggilan di level modul; bila `penghitung <= HR_GAGAL_N_KALI`, raise `HRTimeoutError`. |
| `reset_hr()` | Nolkan penghitung (dipakai test). |
| `bayar(claim_id, jumlah) -> dict` | Transfer tiruan ke `runtime_dir/pembayaran.json`. Kunci idempotensi `f"{claim_id}:{jumlah}"`. Bila kunci sudah ada, kembalikan transaksi lama + `duplikat=True` **tanpa menulis apa pun**. Bila belum, buat `{"kunci", "claim_id", "jumlah", "ref": "TRF-0001"}`, simpan, kembalikan + `duplikat=False`. |
| `baca_ledger() -> dict` | Isi `pembayaran.json` (atau `{}`). |
| `cari_kebijakan(pertanyaan, k=2) -> list[dict]` | RAG mini tanpa embedding: pecah setiap file `data/kebijakan/*.md` per paragraf (`"\n\n"`), lewati judul `#`. Skor = jumlah kata (huruf kecil, panjang > 2) yang sama dengan pertanyaan. Kembalikan `k` teratas: `{"sumber": nama_file_tanpa_ekstensi, "teks", "skor"}`. Abaikan skor 0. |

**Cek:** `uv run pytest tests/test_tahap01_tools.py -q` → 10 passed.

**🔬 Eksperimen**
- `uv run python -c "from app import tools; print(tools.cari_kebijakan('berapa batas hotel'))"`. Lihat bahwa pencarian kata itu rapuh: coba "penginapan" alih-alih "hotel". Inilah alasan RAG sungguhan memakai embedding.
- Panggil `bayar` dua kali dengan jumlah sama, lalu dengan jumlah berbeda. Kenapa kunci idempotensi menyertakan jumlah?

<details><summary>💡 Petunjuk bila buntu</summary>

- `json.loads((get_settings().data_dir / "klaim.json").read_text(encoding="utf-8"))`
- Penghitung modul: `_hr_panggilan = {"n": 0}` (dict supaya bisa diubah dari dalam fungsi tanpa `global`).
- Kata: `set(re.findall(r"[a-z0-9]+", teks.lower()))` lalu filter `len(k) > 2`; skor = `len(q & kata_paragraf)`.
</details>

---

## Tahap 2 — State dan skema

**Tujuan:** mendefinisikan "papan tulis" bersama yang dibaca dan ditulis semua node, plus skema output LLM.

### Konsep kunci: reducer

Node **tidak** mengembalikan state utuh, tapi **pembaruan parsial** (`{"log": ["..."]}`). LangGraph menggabungkannya ke state memakai **reducer** per field:

| Deklarasi field | Bila dua update datang | Dipakai untuk |
|---|---|---|
| `keputusan: dict` (tanpa reducer) | nilai baru **menimpa** | data milik satu node |
| `log: Annotated[list[str], operator.add]` | list **disambung** | jejak, hasil paralel |

Aturan penting: kalau **beberapa node menulis field yang sama di superstep yang sama** (paralel), field itu **wajib** punya reducer. Tanpa reducer, LangGraph melempar `InvalidUpdateError` (kamu akan melihatnya sendiri di Tahap 11).

### File `app/state.py`

- `Rute = Literal["klaim", "kebijakan", "klarifikasi"]`
- `class KlaimState(TypedDict, total=False)` dengan field:
  `permintaan, rute, claim_id, klaim, profil, hasil_item, keputusan, draf_memo, jumlah_draf, penilaian, persetujuan, pembayaran, status_akhir, jawaban, sumber, log, peringatan`.
  - `hasil_item`, `log`, `peringatan` → `Annotated[list[...], operator.add]`
  - sisanya tanpa reducer
- `class ItemTask(TypedDict)`: `claim_id: str`, `item: dict`. Ini input untuk node paralel di Tahap 5.
- Pydantic (`BaseModel` + `Field(description=...)`, karena deskripsi ikut dikirim ke LLM):
  - `RuteDecision`: `rute: Rute`, `claim_id: str | None = None`, `alasan: str`
  - `PenilaianMemo`: `skor: int` (1–10, `ge=1, le=10`), `masalah: list[str] = []`
  - `JawabanKebijakan`: `jawaban: str`, `sumber: list[str] = []`

**Cek:** `uv run pytest tests/test_tahap02_state.py -q` → 5 passed.

**🔬 Eksperimen:** kenapa `total=False`? Coba hapus, lalu panggil `KlaimState(permintaan="x")` di editor yang mengecek tipe. Di runtime TypedDict tidak memvalidasi apa pun. Validasi hanya terjadi di Pydantic. Coba `RuteDecision(rute="lain", alasan="x")`.

---

## Tahap 3 — Graph pertama

**Tujuan:** graph terkecil yang berguna: router memilih jalur, satu jalur selesai.

### Konsep

- **Node** = fungsi `state -> dict` (pembaruan parsial).
- **Edge** `add_edge(a, b)` = selalu dari a ke b.
- **Conditional edge** `add_conditional_edges(a, fungsi_rute, [tujuan...])` = `fungsi_rute(state)` mengembalikan **nama node** tujuan. Daftar tujuan dipakai LangGraph untuk validasi dan menggambar diagram.
- `compile()` → graph yang bisa `invoke` / `stream`.

### File `app/nodes.py` (mulai)

| Fungsi | Spesifikasi |
|---|---|
| `rute_aturan(permintaan) -> RuteDecision` | Router tanpa LLM: ada `KLM-\d{3}` (tidak peka huruf besar/kecil) → `klaim` + claim_id huruf besar; mengandung kata seperti `kebijakan, aturan, batas, boleh, bisa, apakah, berapa, bagaimana, struk, maksimal` → `kebijakan`; selain itu `klarifikasi`. |
| `router(state) -> dict` | Untuk sekarang: `keputusan = rute_aturan(state["permintaan"])` (Tahap 4 menggantinya dengan LLM). **Validasi kode:** bila rute `klaim` tapi `ambil_klaim(claim_id)` `None` → ubah ke `klarifikasi`. Kembalikan **hanya** `{"rute", "claim_id", "log": [f"router: {rute} ({alasan})"]}`. |
| `rute_setelah_router(state) -> str` | `klaim→"muat_klaim"`, `kebijakan→"jawab_kebijakan"`, `klarifikasi→"klarifikasi"`. |
| `klarifikasi(state) -> dict` | `jawaban`: bila ada `claim_id`, awali dengan `"Klaim {cid} tidak ditemukan. "`, lalu `"Sebutkan nomor klaim (misalnya KLM-001) atau tanyakan aturan klaim."`. `status_akhir="butuh_klarifikasi"`, `log=["klarifikasi"]`. |

Test merakit graph mini sendiri (node `muat_klaim` dan `jawab_kebijakan` diganti placeholder). Bacalah `_graph_mini()` di test: itulah pola merakit graph.

**Cek:** `uv run pytest tests/test_tahap03_graph_pertama.py -q` → 4 passed.

**🔬 Eksperimen** (buat `scratch.py` sendiri, jangan di-commit):
```python
g = ...  # rakit seperti _graph_mini() di test
print(g.get_graph().draw_mermaid())   # tempel ke https://mermaid.live
for chunk in g.stream({"permintaan": "halo"}, stream_mode="updates"):
    print(chunk)                       # satu chunk per node yang selesai
```
Lalu coba kembalikan state utuh dari `router` (`return {**state, ...}`). Apa yang terjadi pada `log`? (Petunjuk: reducer `operator.add` menyambung list lama dengan list lama + baru.)

---

## Tahap 4 — LLM, structured output, dan RAG mini

**Tujuan:** memasang LLM tanpa membuat graph bergantung padanya.

### Konsep

- `chat_model.with_structured_output(SkemaPydantic)` → LLM mengembalikan **objek Pydantic**, bukan teks. Masalah format hilang.
- **Output LLM tetap divalidasi kode.** Structured output menjamin *bentuk*, bukan *kebenaran*. LLM bisa mengarang `claim_id` yang formatnya valid tapi tidak ada di data.
- Mode **mock** memakai `fallback()`, jadi seluruh graph bisa dites gratis dan deterministik.

### File `app/llm.py`

| Fungsi | Spesifikasi |
|---|---|
| `is_live() -> bool` | `get_settings().llm_mode == "live"` |
| `chat_model()` | `ChatOpenAI(model, base_url, api_key, temperature, timeout=60, max_retries=2)`. Bila API key kosong → `RuntimeError` yang pesannya menyebut `LLM_API_KEY`. |
| `structured(schema, system, user, fallback)` | Mock → `fallback()`. Live → `chat_model().with_structured_output(schema).invoke([SystemMessage, HumanMessage])`. |
| `teks(system, user, fallback) -> str` | Sama, tapi `.invoke(...).content`. |

### Ubah dan tambah di `app/nodes.py`

- `router`: ganti dengan `llm.structured(RuteDecision, SYSTEM_ROUTER, permintaan, fallback=lambda: rute_aturan(permintaan))`. Tulis `SYSTEM_ROUTER` yang **mendefinisikan tiap rute** (pelajaran Pertemuan 5: definisi yang jelas membantu penalaran model). Validasi `claim_id` tetap di kode.
- `jawab_kebijakan(state)`: `cari_kebijakan(permintaan, k=2)` → susun konteks `"[sumber] teks"` → `llm.structured(JawabanKebijakan, system_dengan_konteks, permintaan, fallback=...)`. Fallback: teks dokumen teratas + semua sumber, atau "Tidak ditemukan..." bila kosong. Kembalikan `jawaban, sumber, status_akhir="dijawab", log`.

**Cek:** `uv run pytest tests/test_tahap04_llm_rag.py -q` → 4 passed.

**🔬 Eksperimen:** baca `test_router_lewat_lapisan_llm`. Test itu mengganti LLM dengan fungsi palsu yang "mengarang" nomor klaim. Teknik `monkeypatch` seperti ini adalah cara mengetes perilaku agent saat LLM salah, tanpa memanggil LLM.

---

## Tahap 5 — Paralel, map-reduce dengan `Send`, join

**Tujuan:** memeriksa semua item klaim **bersamaan**, sambil memanggil API HR di cabang lain, lalu menunggu keduanya sebelum memutuskan.

### Konsep

- **Superstep:** LangGraph menjalankan graph per "langkah". Semua node yang terpicu di langkah yang sama berjalan **paralel**. Langkah berikutnya baru mulai setelah semuanya selesai.
- **Fan-out statis:** dua edge keluar dari satu node → dua cabang paralel.
- **Fan-out dinamis (`Send`):** jumlah cabang baru diketahui saat runtime (jumlah item). Fungsi rute mengembalikan `[Send("periksa_item", payload), ...]`. Setiap `Send` membawa **input sendiri**, bukan state utuh. Karena itu `periksa_item` didaftarkan dengan `input_schema=ItemTask`.
- **Reduce:** setiap `periksa_item` mengembalikan `{"hasil_item": [satu_hasil]}`. Reducer `operator.add` menyambung semuanya.
- **Join / barrier:** `add_edge(["cek_karyawan", "periksa_item"], "putuskan")` artinya `putuskan` menunggu **semua** sumber selesai.

### File `app/guardrails.py`

- `deteksi_injeksi(teks) -> list[str]`: daftar pola regex (tidak peka huruf besar/kecil) yang cocok. Minimal kenali: `abaikan (semua) aturan/instruksi/perintah`, `ignore (all) (previous) instructions`, kata `approved`, `setujui klaim/penuh/semua`.
- `bungkus_tidak_tepercaya(teks)` → `"<data_tidak_tepercaya>{teks}</data_tidak_tepercaya>"`.

### Tambah di `app/nodes.py`

| Node / fungsi | Spesifikasi |
|---|---|
| `muat_klaim(state)` | `klaim = ambil_klaim(claim_id)`. Untuk tiap item yang keterangannya cocok `deteksi_injeksi`: `peringatan` += `f"{item_id}: keterangan berisi pola prompt injection"`. Kembalikan `klaim, peringatan, log`. |
| `fan_out_item(state) -> list[Send]` | Satu `Send("periksa_item", {"claim_id": ..., "item": it})` per item, urutan sesuai data. |
| `periksa_item(task: ItemTask)` | `{"hasil_item": [tools.periksa_item(task["item"], ambil_kebijakan())], "log": [...]}`. **Panggil lewat `tools.periksa_item`**, bukan `from app.tools import periksa_item`, karena test me-monkeypatch `tools.periksa_item`. |
| `cek_karyawan(state)` | `profil = ambil_profil_karyawan(klaim["karyawan_id"])`. Kembalikan `profil, log`. **Jangan pakai try/except.** Retry diurus graph di Tahap 9. |
| `putuskan(state)` | Urutkan `hasil_item` berdasarkan `item_id` (urutan hasil paralel tidak dijamin!). Hitung `total_diajukan`, `total_disetujui`. Aturan: disetujui 0 → `tolak`; disetujui > `sisa_anggaran` → `tolak`; semua ok → `setujui_penuh`; selain itu `setujui_sebagian`. `perlu_persetujuan = aksi != "tolak" and (disetujui > batas_auto_approve or aksi == "setujui_sebagian" or ada peringatan)`. Untuk `tolak`, `total_disetujui` = 0. Kembalikan `{"keputusan": {aksi, alasan, total_diajukan, total_disetujui, perlu_persetujuan, rincian}, "log"}`. |

**Cek:** `uv run pytest tests/test_tahap05_paralel_send.py -q` → 7 passed. Test terakhir **mengukur waktu**: 3 item × 0,3 detik harus selesai sekitar 0,3 detik.

**🔬 Eksperimen**
- Di `scratch.py`, stream graph Tahap 5 dengan `stream_mode="updates"` untuk KLM-003. Perhatikan `periksa_item` muncul 3×, dan `cek_karyawan` muncul di superstep yang sama.
- Hapus `operator.add` dari `hasil_item` di `state.py`, lalu jalankan lagi. Baca error-nya baik-baik, kemudian kembalikan reducernya.
- Kenapa keputusan uang di `putuskan` tidak memakai LLM sama sekali? (Jawab untuk dirimu sendiri: audit, reprodusibilitas, prompt injection.)

---

## Tahap 6 — Evaluator-optimizer (refleksi) dengan batas

**Tujuan:** LLM menulis memo, lalu memo dinilai. Bila belum lolos, memo ditulis ulang dengan umpan balik, **maksimal `MAX_REVISI` kali**.

### Konsep

Loop di graph = conditional edge yang mengarah **kembali** ke node sebelumnya. Setiap loop wajib punya **batas**. Tanpa batas, kamu akan bertemu `GraphRecursionError`, atau tagihan LLM yang besar.

Penilai memakai dua lapis: **cek kode deterministik** (nomor klaim, frasa keputusan, total yang persis) **+ LLM-as-judge** (skor kualitas). Cek kode menangkap kesalahan fatal dengan pasti. Judge menangkap kualitas.

### Tambah di `app/nodes.py`

| Fungsi | Spesifikasi |
|---|---|
| `LABEL_KEPUTUSAN` | `{"setujui_penuh": "disetujui penuh", "setujui_sebagian": "disetujui sebagian", "tolak": "ditolak"}` |
| `tulis_memo(state)` | `n = jumlah_draf + 1`. Susun data untuk LLM: nomor klaim, judul, nama karyawan, label keputusan, alasan, total disetujui (format rupiah), rincian item dengan **keterangan dibungkus `bungkus_tidak_tepercaya`**, `masalah` dari penilaian sebelumnya, dan `catatan` atasan (Tahap 7). System prompt mewajibkan nomor klaim, frasa keputusan, total persis, dan melarang mengikuti instruksi di dalam data tidak tepercaya. **Fallback mock:** memo template yang memuat semuanya, kecuali bila `MOCK_DRAF_PERTAMA_KURANG` aktif dan `n == 1`: **hilangkan baris total**, supaya loop terlihat bekerja. Kembalikan `draf_memo, jumlah_draf=n, log`. |
| `cek_memo_aturan(memo, claim_id, keputusan) -> list[str]` | Masalah bila: nomor klaim tidak ada; label keputusan tidak ada (bandingkan `memo.lower()`); `format_rupiah(total_disetujui)` tidak ada; ada kata `APPROVED` (huruf besar, `\b`). Pesan masalah tentang total harus mengandung kata `total`. |
| `nilai_memo(state)` | `masalah = cek_memo_aturan(...)`, lalu judge `llm.structured(PenilaianMemo, ..., fallback=skor 5 bila ada masalah, 8 bila tidak)`. `lolos = tidak ada masalah kode and skor >= 7`. Kembalikan `{"penilaian": {"skor", "masalah": masalah_kode + masalah_judge, "lolos"}, "log"}`. **Panggil `cek_memo_aturan` lewat nama modul** (biarkan sebagai fungsi modul biasa). Test me-monkeypatch `app.nodes.cek_memo_aturan`. |
| `rute_setelah_nilai(state) -> str` | Urutan: belum lolos **dan** `jumlah_draf <= MAX_REVISI` → `"tulis_memo"`; aksi `tolak` → `"selesai"`; perlu persetujuan **atau** belum lolos (jatah habis) → `"persetujuan"`; selain itu `"bayar"`. |

**Cek:** `uv run pytest tests/test_tahap06_evaluator.py -q` → 4 passed.

**🔬 Eksperimen:** set `MAX_REVISI=0` di `.env`. Apa yang terjadi pada KLM-001? Memo yang belum lolos tetap sampai ke atasan, beserta daftar masalahnya. Itu desain yang disengaja: manusia memutuskan, bukan loop tanpa akhir.

---

## Tahap 7 — Human-in-the-loop dan graph lengkap

**Tujuan:** graph berhenti dan menunggu atasan, lalu dilanjutkan, mungkin keesokan harinya, dari proses lain.

### Konsep `interrupt`

```python
jawaban = interrupt(payload)   # 1) graph BERHENTI di sini; payload dikirim ke pemanggil sebagai "__interrupt__"
...                            # 2) saat di-resume: node ini DIJALANKAN ULANG DARI BARIS PERTAMA,
                               #    dan kali ini interrupt() mengembalikan nilai dari Command(resume=nilai)
```

Konsekuensinya:
- `interrupt` **wajib** checkpointer (untuk menyimpan posisi berhenti). Tanpa checkpointer, interrupt pertama tampak berhasil, tetapi resume gagal dengan `RuntimeError: Cannot use Command(resume=...) without checkpointer`.
- Kode **sebelum** `interrupt()` berjalan dua kali, jadi jangan taruh efek samping di sana.
- **Jangan** bungkus `interrupt()` dengan `try/except Exception` (ia bekerja dengan melempar exception khusus).
- Efek samping (uang keluar) ada di node **terpisah sesudah** persetujuan: `bayar`.

### Tambah di `app/nodes.py`

| Fungsi | Spesifikasi |
|---|---|
| `persetujuan(state)` | `jawaban = interrupt({claim_id, karyawan, atasan, keputusan (label), total_disetujui (rupiah), peringatan, masalah_memo, memo, petunjuk})`. Terima `str` (`"setujui"`) maupun `dict` (`{"aksi": ..., "catatan": ...}`). Normalisasi aksi: `setujui/setuju/ya/yes/ok/approve` → `setujui`; `tolak/tidak/no/reject` → `tolak`; selain itu → `revisi` (teksnya dijadikan catatan bila catatan kosong). Kembalikan `persetujuan={"aksi", "catatan", "oleh": atasan}`, `log`; bila revisi juga `jumlah_draf=0`. |
| `rute_setelah_persetujuan(state)` | `setujui→"bayar"`, `revisi→"tulis_memo"`, `tolak→"selesai"` |
| `bayar(state)` | `tools.bayar(claim_id, total_disetujui)`. Kembalikan `pembayaran=trx, status_akhir="dibayar", log=[f"bayar: {ref} duplikat={duplikat}"]`. (Tahap 9 menambah crash, Tahap 10 menambah progres stream.) |
| `selesai(state)` | `status_akhir`: tetap `dibayar` bila sudah dibayar; `ditolak_atasan` bila persetujuan `tolak`; selain itu `ditolak_otomatis`. `jawaban = f"Klaim {cid}: {status}, dibayar {rupiah}."` |

### File `app/graph.py`

- `build_builder() -> StateGraph` merakit **semua** node dan edge sesuai topologi di atas (lihat juga docstring yang kamu tulis sendiri di atas file, karena menulis topologi sebagai komentar dulu sangat membantu).
- `build_graph(checkpointer=None)` → `compile(checkpointer=checkpointer or InMemorySaver())`.

**Cek:** `uv run pytest tests/test_tahap07_hitl.py -q` → 7 passed.

**🔬 Eksperimen** (`scratch.py`):
```python
from langgraph.types import Command
from app.graph import build_graph
g = build_graph(); cfg = {"configurable": {"thread_id": "coba-1"}}
s = g.invoke({"permintaan": "Proses KLM-004"}, cfg)
print(s["__interrupt__"][0].value)          # apa yang dilihat atasan
print(g.get_state(cfg).next)                 # ('persetujuan',)
s = g.invoke(Command(resume={"aksi": "revisi", "catatan": "sebut alasan pemotongan hotel"}), cfg)
print(s["log"][-4:])                         # kembali ke tulis_memo, lalu berhenti lagi
```
Tambahkan `print("persetujuan dipanggil")` di baris pertama `persetujuan`. Hitung berapa kali tercetak untuk satu kali persetujuan.

---

## Tahap 8 — Checkpoint SQLite, `thread_id`, dan CLI

**Tujuan:** state bertahan walau proses mati. Atasan bisa menyetujui besok dari terminal lain.

### Konsep

- Checkpointer menyimpan **snapshot state setelah setiap superstep**, dikelompokkan per `thread_id` (satu klaim = satu thread).
- `get_state(cfg)`: state terakhir + `next` (node berikutnya) + `interrupts`.
- `get_state_history(cfg)`: semua checkpoint, terbaru dulu. Ini dasar *time travel* di Studio.
- `invoke(None, cfg)`: lanjutkan dari checkpoint terakhir tanpa input baru.
- ⚠️ **Jebakan reducer:** memakai **thread yang sama** untuk klaim baru akan menyambung `hasil_item` dan `log` lama. Satu klaim, satu thread.

### Tambah di `app/graph.py`

`buka_sqlite(path=None) -> SqliteSaver`: `sqlite3.connect(path or runtime_dir/"checkpoints.db", check_same_thread=False)`, `SqliteSaver(conn)`, `saver.setup()`.

### File `app/cli.py` (dijalankan `uv run python -m app.cli ...`)

| Perintah | Perilaku |
|---|---|
| `jalankan "<permintaan>" [--thread T]` | Thread default acak (`t-xxxxxx`). Jalankan graph (pakai `stream`, lihat Tahap 10; untuk sekarang `invoke` juga boleh), lalu cetak status. Bila berhenti di interrupt, output harus memuat kata `INTERRUPT`. |
| `lanjut --thread T [--aksi A] [--catatan C]` | Dengan `--aksi`: `Command(resume={"aksi": A, "catatan": C})`. Tanpa `--aksi`: input `None` (lanjut setelah crash). Lalu cetak status. |
| `status --thread T` | Cetak `next`, `status_akhir`, keputusan, peringatan, jawaban, dan payload interrupt bila ada. Output memuat `next` dalam bentuk tuple, misalnya `('persetujuan',)`. |
| `riwayat --thread T` | Satu baris per checkpoint, memuat `step=` dan `next=`. |
| `diagram` | `print(graph.get_graph().draw_mermaid())` |
| `pembayaran` | Cetak ledger. |

Semua perintah (kecuali `pembayaran`) memakai `build_graph(buka_sqlite())`. Config: `{"configurable": {"thread_id": T}, "recursion_limit": 40}`.

**Cek:** `uv run pytest tests/test_tahap08_checkpoint.py -q` → 2 passed. Test kedua benar-benar menjalankan CLI di **proses terpisah**.

**🔬 Eksperimen** (di dua jendela terminal):
```bash
uv run python -m app.cli jalankan "Proses klaim KLM-003" --thread demo-3
# tutup terminal ini. Buka terminal baru:
uv run python -m app.cli status  --thread demo-3
uv run python -m app.cli lanjut  --thread demo-3 --aksi revisi --catatan "jelaskan kenapa keyboard ditolak"
uv run python -m app.cli lanjut  --thread demo-3 --aksi setujui
uv run python -m app.cli riwayat --thread demo-3
uv run python -m app.cli diagram          # tempel ke mermaid.live
```

---

## Tahap 9 — Keandalan: retry, crash, idempotensi

**Tujuan:** sistem tetap benar saat dunia luar bermasalah.

### 9a. `RetryPolicy`

Di `graph.py`:
```python
HR_RETRY = RetryPolicy(max_attempts=4, initial_interval=0.1, backoff_factor=2.0, jitter=False,
                       retry_on=HRTimeoutError)
g.add_node("cek_karyawan", cek_karyawan, retry_policy=HR_RETRY)
```
`retry_on` membatasi retry hanya untuk error sementara. Bug (`KeyError`) tidak boleh di-retry.

### 9b. Crash di tengah efek samping

Di `bayar`, setelah `tools.bayar(...)`: bila `CRASH_SETELAH_BAYAR=1` **dan** transaksi bukan duplikat, cetak pesan lalu `os._exit(1)` (mati mendadak, persis seperti proses yang di-kill).

Yang terjadi: uang **sudah** keluar, tapi node `bayar` tidak pernah selesai, jadi **tidak ada checkpoint untuk node itu**. Saat `lanjut`, LangGraph menjalankan `bayar` **lagi dari awal**. Tanpa kunci idempotensi, karyawan dibayar dua kali. Checkpointer **tidak** melindungi efek samping. Itu tugasmu.

**Cek:** `uv run pytest tests/test_tahap09_keandalan.py -q` → 4 passed.

**🔬 Eksperimen:**
```bash
CRASH_SETELAH_BAYAR=1 uv run python -m app.cli jalankan "Proses KLM-002" --thread crash-1; echo "exit=$?"
uv run python -m app.cli pembayaran                     # 1 transaksi
uv run python -m app.cli lanjut --thread crash-1        # bayar diulang -> duplikat=True
uv run python -m app.cli pembayaran                     # tetap 1 transaksi
HR_GAGAL_N_KALI=3 uv run python -m app.cli jalankan "Proses KLM-002"   # berhasil setelah retry
HR_GAGAL_N_KALI=9 uv run python -m app.cli jalankan "Proses KLM-002"   # menyerah: lihat traceback
```
Lalu ubah sementara kunci idempotensi di `tools.bayar` menjadi acak (`uuid4()`), ulangi skenario crash, dan lihat transfer ganda. Kembalikan setelahnya.

---

## Tahap 10 — Streaming

**Tujuan:** pengguna melihat progres saat agent bekerja, bukan layar kosong.

| `stream_mode` | Isi tiap chunk |
|---|---|
| `"updates"` | `{nama_node: pembaruan}` per node selesai; interrupt muncul sebagai `{"__interrupt__": ...}` |
| `"values"` | state **penuh** setelah tiap superstep |
| `"custom"` | data bebas yang dikirim node lewat `get_stream_writer()` |
| `"messages"` | token LLM satu per satu (hanya terasa di mode live) |
| `[..., ...]` | gabungan; tiap chunk menjadi `(mode, data)` |

- Di `bayar`: `tulis = get_stream_writer()`, lalu `tulis({"progres": f"mentransfer {rupiah} untuk {cid}"})` sebelum transfer dan `tulis({"progres": f"transfer {ref} selesai (duplikat={dup})"})` sesudahnya. Jadi tepat **2** progres per pembayaran.
- Di `cli.py`, jalankan dengan `stream_mode=["updates", "custom"]`: cetak setiap baris `log` dari update (`➡️ ...`), progres custom (`⏳ ...`), dan `INTERRUPT` saat bertemu `__interrupt__`.

**Cek:** `uv run pytest tests/test_tahap10_streaming.py -q` → 3 passed.

---

## Tahap 11 — LangGraph Studio: debugging visual

**Tujuan:** melihat, menghentikan, mengubah, dan memutar ulang graph secara visual. Ini alat debugging terpenting saat graph mulai besar.

### 11a. Daftarkan graph

Tambahkan di **akhir** `app/graph.py`:
```python
# Untuk LangGraph Studio: TANPA checkpointer, karena server menyediakan persistence sendiri.
graph = build_builder().compile()
```
Buat `langgraph.json` di root proyek:
```json
{
  "dependencies": ["."],
  "graphs": {
    "klaim": "./app/graph.py:graph"
  },
  "env": ".env"
}
```
(Di Tahap 12 kamu menambahkan tiga graph pola ke sini.)

**Cek:** `uv run pytest tests/test_tahap11_studio.py -q` → 2 passed.

### 11b. Jalankan server + Studio

```bash
uv run langgraph dev
```
Output yang diharapkan:
```
- 🚀 API: http://127.0.0.1:2024
- 🎨 Studio UI: https://smith.langchain.com/studio/?baseUrl=http://127.0.0.1:2024
- 📚 API Docs: http://127.0.0.1:2024/docs
```
- Studio UI berjalan di browser dan terhubung ke server lokalmu. Kamu perlu **login akun LangSmith** (gratis). Kode dan data tetap di laptopmu.
- Pakai **Chrome**. Safari memblokir koneksi https→localhost; kalau terpaksa Safari, jalankan `uv run langgraph dev --tunnel`.
- Server **hot reload**: simpan file `.py` → graph dimuat ulang otomatis.
- Server ini memakai `.env` (mode mock secara default), jadi semua latihan Studio gratis.

### 11c. Latihan debugging di Studio (kerjakan berurutan)

1. **Baca topologi.** Pilih graph `klaim`. Cocokkan diagram dengan topologi di LAB ini. Garis putus-putus = conditional edge.
2. **Jalankan dan amati per langkah.** Input: `{"permintaan": "Proses klaim KLM-003"}`. Klik setiap node di panel kanan untuk melihat **pembaruan** yang dikembalikannya dan **state** sesudahnya. Temukan superstep tempat `periksa_item` (3×) dan `cek_karyawan` berjalan bersamaan.
3. **Human-in-the-loop dari UI.** Run berhenti di `persetujuan` dengan payload interrupt. Resume dengan `{"aksi": "revisi", "catatan": "sebutkan item mana yang ditolak"}`, lalu setujui. Ikuti jalur loop-nya di diagram.
4. **Breakpoint.** Pasang interrupt **sebelum** `putuskan` (lewat menu node atau pengaturan interrupt di Studio). Jalankan KLM-001. Saat berhenti, periksa `hasil_item`: urutannya mungkin tidak sama dengan urutan data. Itulah alasan `putuskan` mengurutkannya.
5. **Edit state lalu lanjutkan.** Masih di breakpoint `putuskan`: edit state, ubah `profil.sisa_anggaran` menjadi `500000`, lalu lanjutkan. Keputusan seharusnya berubah menjadi `tolak`. Kamu baru menguji cabang lain **tanpa mengubah data**.
6. **Time travel / fork.** Buka riwayat checkpoint thread KLM-001. Pilih checkpoint setelah `nilai_memo` pertama, edit `draf_memo` menjadi memo yang kamu tulis sendiri, lalu jalankan dari situ (fork). Bandingkan dua cabang riwayat.
7. **Debug bug sungguhan.** Di `state.py`, hapus `operator.add` dari `hasil_item` (biarkan `list[dict]`), lalu simpan (hot reload). Jalankan KLM-001. Baca error `InvalidUpdateError` di Studio dan temukan node mana yang menulis bersamaan. Kembalikan reducernya.
8. **Retry terlihat.** Set `HR_GAGAL_N_KALI=2` di `.env`, restart `langgraph dev`, jalankan klaim apa saja, lalu amati log server: `cek_karyawan` gagal dua kali sebelum berhasil. Kembalikan ke `0`.
9. **Panggil lewat SDK** (graph yang sama, sebagai layanan). Buat `sdk_demo.py`:
   ```python
   import asyncio
   from langgraph_sdk import get_client

   async def main():
       c = get_client(url="http://127.0.0.1:2024")
       t = await c.threads.create()
       async for ch in c.runs.stream(t["thread_id"], "klaim", input={"permintaan": "Proses KLM-001"}, stream_mode="updates"):
           print(ch.event, ch.data)
       print((await c.threads.get_state(t["thread_id"]))["next"])          # ['persetujuan']
       async for ch in c.runs.stream(t["thread_id"], "klaim", command={"resume": "setujui"}, stream_mode=["updates", "custom"]):
           print(ch.event, ch.data)

   asyncio.run(main())
   ```
   `uv run python sdk_demo.py` sambil `langgraph dev` jalan. Thread ini juga muncul di Studio. Inilah "LangGraph stack": graph → server (Agent Server) → SDK/Studio. Dokumentasi API lengkap ada di http://127.0.0.1:2024/docs.

> **Kenapa `graph` untuk Studio tanpa checkpointer, sedangkan CLI memakai SQLite?** Server `langgraph dev` mengelola thread dan checkpoint sendiri (in-memory, disimpan di folder `.langgraph_api/`). CLI kita berjalan sendirian, jadi kitalah yang memasang `SqliteSaver`. Graph builder-nya sama; hanya cara compile yang berbeda.

> **Opsional, tracing LangSmith:** tambahkan `LANGSMITH_TRACING=true` dan `LANGSMITH_API_KEY=...` di `.env`. Setiap run (termasuk dari CLI) akan tercatat lengkap di LangSmith: input/output tiap node, prompt LLM, latensi, token.

---

## Tahap 12 — Pola orkestrasi lain

Graph utamamu sudah memakai empat pola: **routing** (router), **parallelization** (cek_karyawan ∥ periksa_item), **orchestrator-workers** (`Send`), dan **evaluator-optimizer**. Tahap ini menambah tiga lagi di `app/pola.py`, dengan domain klaim yang sama, **tanpa LLM**, supaya strukturnya yang terlihat. Di sistem nyata, keputusan "siapa berikutnya" biasanya dibuat LLM.

### 12a. Supervisor — `supervisor_graph`

State: `claim_id`, `temuan: Annotated[dict, gabung_dict]` (reducer buatanmu sendiri: `lambda a, b: {**a, **b}`), `log: Annotated[list[str], operator.add]`.

- `supervisor(state) -> Command[Literal["cek_struk", "cek_anggaran", "tulis_ringkasan", "__end__"]]`: pilih worker pertama (urutan `cek_struk, cek_anggaran, tulis_ringkasan`) yang belum ada di `temuan`, atau `END` bila semua sudah. Kembalikan `Command(goto=tujuan, update={"log": [f"supervisor -> {tujuan}"]})`. (`END` bernilai string `"__end__"`.)
- Worker `cek_struk` (temuan berisi teks `"{n} item tanpa struk {daftar}"`), `cek_anggaran`, `tulis_ringkasan`. Masing-masing menulis `{"temuan": {nama_worker: teks}}`.
- Edge: `START → supervisor`, dan setiap worker → `supervisor` (worker **selalu** kembali). Supervisor **tidak** butuh `add_conditional_edges`: tujuannya diumumkan lewat anotasi `Command[Literal[...]]`.

### 12b. Handoff — `handoff_graph`

Tidak ada pengendali pusat. Setiap agent memutuskan penerusnya sendiri dengan `Command(goto=...)`.
- `resepsionis`: pesan mengandung `cuti/gaji/anggaran` → `agen_hr`, selain itu → `agen_keuangan`. Log `"resepsionis -> {tujuan}"`.
- `agen_keuangan`: pesan mengandung `anggaran` → serahkan ke `agen_hr` (log `"agen_keuangan -> agen_hr"`); selain itu jawab `"Keuangan: ..."` dan `goto=END` (log `"agen_keuangan selesai"`).
- `agen_hr`: jawab `"HR: ..."`, log `"agen_hr selesai"`, edge biasa ke `END`.

### 12c. Planner-executor — `planner_graph`

- `planner`: `rencana = ["ambil_klaim", "periksa_semua_item", "hitung_total"]`, log `f"planner: {rencana}"`.
- `executor`: ambil langkah pertama, jalankan, simpan hasil ke `data` (reducer gabung dict: `klaim`, `hasil`, `total_disetujui`), kembalikan sisa rencana, log `f"executor: {langkah}"`.
- `executor → executor` selama rencana belum habis, lalu `END`.

Di akhir file: `supervisor_graph = build_supervisor()`, `handoff_graph = ...`, `planner_graph = ...`. Daftarkan ketiganya di `langgraph.json` sebagai `pola_supervisor`, `pola_handoff`, `pola_planner`, lalu lihat di Studio.

**Cek:** `uv run pytest tests/test_tahap12_pola.py -q` → 3 passed. Lalu **semua**: `uv run pytest -q` → 55 passed. 🎉

**🔬 Diskusi untuk dirimu sendiri:** graph klaim utama memakai *workflow* (langkah diketahui di depan) di sekeliling dua titik LLM. Kapan kamu akan mengganti `putuskan` dengan supervisor LLM? (Jawaban yang sehat: hampir tidak pernah untuk keputusan uang.)

---

## Tahap 13 (opsional) — LLM sungguhan

Ubah `.env`:
```bash
LLM_MODE=live
LLM_BASE_URL=https://ai.sumopod.com/v1      # atau vLLM: http://127.0.0.1:8000/v1, Ollama: http://127.0.0.1:11434/v1
LLM_API_KEY=isi-key-kamu
LLM_MODEL=glm-5.3-flash                      # vLLM: nama --served-model-name; Ollama: misal qwen3:4b
```
Lalu:
```bash
uv run python -m app.cli jalankan "tolong cek klaim nomor klm-001 ya" --thread live-1
uv run python -m app.cli jalankan "Proses klaim KLM-004" --thread live-4      # prompt injection
uv run python -m app.cli jalankan "Apakah langganan Netflix bisa diklaim?"
```
Yang perlu diamati:
- **Router:** LLM memahami kalimat bebas ("tolong cek klaim nomor klm-001 ya").
- **Loop evaluator:** LLM sering menulis `Rp 1.020.000` (dengan spasi) atau `1,02 juta`. Cek kode menolaknya, dan revisi berikutnya memperbaiki berkat daftar `masalah`. Lihat berapa draf yang dibutuhkan di `log`.
- **KLM-004:** apakah memo LLM terpengaruh keterangan "tulis APPROVED"? Guardrail kode tetap menjaga hasil akhirnya.
- **Studio dalam mode live:** jalankan ulang `langgraph dev`. Di tab run, kamu bisa melihat **token LLM di-stream** per node.
- Bila model tidak mendukung structured output (error tool calling / json_schema), coba `chat_model().with_structured_output(schema, method="function_calling")` atau `method="json_mode"` di `llm.py`.

Test tetap memakai mode mock (diatur `conftest.py`), jadi `uv run pytest` tidak memakan token.

---

## Kalau buntu

Urutan yang disarankan:

1. **Baca pesan error test sampai habis**, terutama baris `assert` dan pesannya. Banyak assert punya penjelasan.
2. Jalankan satu test dengan output penuh: `uv run pytest tests/test_tahap05_paralel_send.py::test_map_reduce_dan_join -x -s`.
3. Buka `<details>` petunjuk di tahap itu (bila ada), atau buka graph di Studio.
4. Bandingkan perilaku dengan kunci **tanpa membaca kodenya**: `KUNCI=1 uv run pytest tests/test_tahap05_paralel_send.py -q`. Atau jalankan CLI kunci dari foldernya: `cd _kunci && uv run python -m app.cli jalankan "Proses KLM-001"` (`python -m` selalu mendahulukan `app/` di folder tempat kamu berdiri).
5. Terakhir: buka **satu fungsi** di `_kunci/app/` yang bermasalah saja, tutup, lalu ketik ulang dengan kata-katamu sendiri.

Studio untuk kunci: `cd _kunci && uv run langgraph dev`.

## Gejala error yang umum

| Gejala | Penyebab | Perbaikan |
|---|---|---|
| `InvalidUpdateError: At key 'hasil_item': Can receive only one value per step` | Field ditulis banyak node paralel tanpa reducer | `Annotated[list[dict], operator.add]` |
| `log` berisi duplikat berlipat | Node mengembalikan state utuh (`{**state, ...}`) | Kembalikan hanya field yang berubah |
| `putuskan` jalan dua kali, atau tidak pernah jalan | Join ditulis sebagai dua `add_edge` terpisah, atau nama node salah | `add_edge(["cek_karyawan", "periksa_item"], "putuskan")` |
| `KeyError: 'klaim'` di `periksa_item` | Node `Send` menerima `ItemTask`, bukan state | Baca `task["item"]`; daftarkan dengan `input_schema=ItemTask` |
| `RuntimeError: Cannot use Command(resume=...) without checkpointer` | Graph di-compile tanpa checkpointer. Interrupt pertama tetap "berhasil", tapi resume gagal | `build_graph()` memasang `InMemorySaver` default |
| Resume tidak melakukan apa-apa | `thread_id` berbeda, atau thread itu tidak sedang di interrupt | Cek `get_state(cfg).next` |
| `GraphRecursionError` | Loop tanpa batas (evaluator / revisi) | Periksa `rute_setelah_nilai` dan `MAX_REVISI` |
| Data klaim lama ikut terbawa | Thread yang sama dipakai untuk klaim lain | Satu klaim, satu thread |
| Studio: graph tidak muncul / gagal load | Error import di `app/graph.py`, atau path di `langgraph.json` salah | Baca log terminal `langgraph dev`; cek `uv run python -c "import app.graph"` |
| Studio tidak bisa terhubung di Safari | Safari memblokir https→localhost | Pakai Chrome atau `langgraph dev --tunnel` |
| Transfer ganda setelah crash | Kunci idempotensi tidak deterministik | Kunci dari isi aksi (`claim_id:jumlah`) |
