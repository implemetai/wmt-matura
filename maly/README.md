# „Mały, ale wariat”: kwantyzacje Bielika-4.5B wobec progu 35% (27.09.2026, noc)

**Decyzja: Bielik-4.5B-v3.0-Instruct i1-IQ4_XS (2,56 GB) + wypracowanie przez harness v3 (tryb hybrid).**
Próbny 25/60 (41,7%) w obu panelach wypracowań; arkusze CKE 2024–2026 47–50/131 (35,9–38,2%), średnio 48,5 (37,0%);
razem 73,5/191 (38,5%) — najlepszy wynik łączny wśród zmierzonych wariantów i najmniejszy plik, który trzyma próg na
obu zestawach. Kryterium „≥ 38% na obu” spełnił w panelu 3, w panelu 4 na arkuszach wyszło 35,9% (szum wypracowań).
Zapasowo, jeśli liczy się suma modeli: ten sam IQ4_XS z harnessem bez rerankera (`RERANK=0`) — 24/60 (40,0%), 48/131 (36,6%).

Cel kategorii: najmniejszy model z ≥ 35% na finałowej maturze z historii (60 pkt → 21 pkt). Wszystkie liczby to oceny
rubryką CKE od niezależnych egzaminatorów Claude Opus 5.5, na ślepo (etykiety losowane osobno w każdej pozycji,
mapowanie poza pakietem). Dokument nie cytuje treści arkuszy.

## Model

| | |
|---|---|
| Plik | `Bielik-4.5B-v3-Istruct-ungated.i1-IQ4_XS.gguf`, 2 558 825 920 B (2,56 GB) |
| Link do wag | https://huggingface.co/mradermacher/Bielik-4.5B-v3-Istruct-ungated-i1-GGUF (plik `…i1-IQ4_XS.gguf`) |
| sha256 | `5ebc90f844185b585839bb3167a000ec32bd5c7118054bc688d8f53a2be55b71` (= LFS oid na HF) |
| Kwantyzacja | IQ4_XS z imatrix (llama.cpp), ~4,25 bit/wagę |
| Wagi źródłowe | `adamo1139/Bielik-4.5B-v3-Instruct-ungated` = bajt w bajt `speakleash/Bielik-4.5B-v3.0-Instruct` (sha256 obu safetensors `bae33275…`, `e66d692a…` zgodne z blobami oficjalnego repo; config/tokenizer identyczne). Licencja Apache-2.0 |
| Parametry | 4,5 mld (ten sam model bazowy co w zgłoszeniu „progress”, inna precyzja) |
| Model pomocniczy (tylko wypracowanie) | `bge-reranker-v2-m3-Q8_0.gguf`, 0,64 GB, + indeks BM25 polskiej Wikipedii (baza wiedzy, nie model) |

## Warunki pomiaru

- Krótkie pozycje: **raw** — samo polecenie, bez promptu systemowego, temperatura 0, llama.cpp b11185, `-np 1`,
  `-c 16384`, `--cache-ram 0`. Próbny = paczka organizatorów (CKE maj 2023, 37 pozycji, 60 pkt) w warunkach finału:
  same znaczniki `[Obraz: …]`, bez opisów obrazów. Arkusze = części tekstowe CKE 2024/2025/2026 (79 pozycji, 131 pkt;
  `devset/cke_full/run_paper.py --mode raw`, jak bazowy pomiar Q8 zespołu).
- Wypracowanie w trybie hybrid: harness v3 (`CKE_MODE=1 QTYPE_V2=1 RERANK=1`, BM25 + reranker, plan → retrieval na
  element tematu → akapity → zakończenie → weryfikacja faktów). Krótkie odpowiedzi w hybrid są identyczne z raw
  (sprawdzone na próbnym: różni się tylko pozycja 26).
- Ocena: pozycje krótkie — jeden egzaminator na pakiet; wypracowania — mediana z trzech egzaminatorów z osobnymi
  permutacjami. Panel 1: 6 wariantów; panel 2: kwanty pośrednie + Q4_K_M jako kotwica; panel 3: tylko wypracowania
  (raw i hybrid IQ4_XS i Q4_K_M + Q8 jako kotwica).

## Wyniki

### Pozycje krótkie (bez wypracowania; próbny /45, arkusze /86)

| Wariant | GGUF | Próbny | Arkusze | Ucięte / pętle (79 pozycji arkuszy) |
|---|---|---|---|---|
| Q8_0 (kontrola) | 5,06 GB | 22 | 43 | 0 / 0 |
| i1-Q4_K_M | 2,88 GB | 18 | 37 | 0 / 0 |
| i1-Q4_K_S | 2,72 GB | 17 | 40 | — |
| **i1-IQ4_XS** | **2,56 GB** | **20** | **39** | — |
| i1-Q3_K_L | 2,50 GB | 8 | 35 | — |
| i1-Q3_K_M | 2,30 GB | 13 | 32 | 3 / 3 |
| i1-IQ3_XXS | 1,85 GB | 8 | 25 | 5 / 5 |
| i1-IQ2_M | 1,62 GB | 11 | 14 | 27 / 22 |
| Qwen3-4B-Instruct-2507 Q4_K_M | 2,50 GB | 14 | 30 | 9 / 4 |

Oceny krótkich pozycji są stabilne: te same odpowiedzi Q4_K_M ocenione w dwóch panelach różniły się w 2 ze 112 pozycji
(saldo 0). Między Q4 a Q3 wynik spada skokowo; wszystko poniżej IQ4_XS odpada.

### Całość (krótkie + wypracowanie, mediana z 3 egzaminatorów, panel 3)

| System | GGUF | Wypracowania (próbny; 2024; 2025; 2026) /15 | Próbny /60 | Arkusze /131 |
|---|---|---|---|---|
| Q8_0 raw (kontrola) | 5,06 GB | 2; 2; 0; 2 | 24 (40,0%) | 47 (35,9%) |
| i1-Q4_K_M raw | 2,88 GB | 2; 4; 2; 2 | 20 (33,3%) | 45 (34,4%) |
| i1-Q4_K_M hybrid | 2,88 GB | 4; 3; 6; 5 | 22 (36,7%) | 51 (38,9%) |
| i1-IQ4_XS raw | 2,56 GB | 2; 2; 2; 2 | 22 (36,7%) | 45 (34,4%) |
| **i1-IQ4_XS hybrid** | **2,56 GB** | **5; 5; 2; 4** | **25 (41,7%)** | **50 (38,2%)** |

Panel 4 (te same prace + IQ4_XS hybrid bez rerankera, nowi egzaminatorzy i permutacje):

| System | Wypracowania (próbny; 2024; 2025; 2026) /15 | Próbny /60 | Arkusze /131 |
|---|---|---|---|
| Q8_0 raw | 2; 2; 0; 2 | 24 (40,0%) | 47 (35,9%) |
| i1-Q4_K_M raw | 2; 3; 1; 2 | 20 (33,3%) | 43 (32,8%) |
| i1-Q4_K_M hybrid | 4; 2; 6; 5 | 22 (36,7%) | 50 (38,2%) |
| i1-IQ4_XS raw | 2; 2; 2; 3 | 22 (36,7%) | 46 (35,1%) |
| **i1-IQ4_XS hybrid** | **5; 1; 4; 3** | **25 (41,7%)** | **47 (35,9%)** |
| i1-IQ4_XS hybrid, `RERANK=0` | 4; 4; 2; 3 | 24 (40,0%) | 48 (36,6%) |

Średnio z paneli 3 i 4 (razem próbny + arkusze, 191 pkt): IQ4_XS hybrid 73,5 (38,5%), Q4_K_M hybrid 72,5 (38,0%),
IQ4_XS hybrid bez rerankera 72 (37,7%), Q8 raw 71 (37,2%), IQ4_XS raw 67,5 (35,3%).

Panel 1 (wypracowania raw oceniane obok innych kandydatów): Q8 24/60 i 49/131, Q4_K_M 21/60 i 48/131. Panel 2:
Q4_K_M raw 19/60 i 44/131, Q4_K_M hybrid 21/60 i 50/131. Rozrzut między panelami bierze się niemal wyłącznie
z wypracowań: ta sama praca potrafi dostać 1 albo 5 pkt u różnych zestawów egzaminatorów (IQ4_XS hybrid, 2024).

- Wypracowanie przez harness daje średnio **+2 pkt na pracę** zarówno dla IQ4_XS, jak i Q4_K_M (8 pkt na 4 pracach
  u obu). Prace hybrid mają 530–730 słów, prozą, jeden temat; tracą głównie na błędach dat (np. przesunięte daty
  kryzysów berlińskich w próbnym), których weryfikacja faktów nie łapie.
- Surowe wypracowania małych modeli często mają nagłówki „Stanowisko/Uzasadnienie” i wypunktowania, co kosztuje B.
- Qwen3-4B-Instruct-2507 Q4_K_M: 25% / 26%, daleko od 40% z benchmarku organizatorów (inny format wejścia, precyzja).

## Ryzyka

- Zapas nad progiem: +4 pkt na próbnym (25 wobec 21), +1–4 pkt na arkuszach (47–50 wobec 45,85). Ocena LLM waha się
  o ±2–4 pkt na arkusz, prawie wyłącznie przez wypracowanie. Oceniający organizatorów może być surowszy lub łagodniejszy.
- Jeśli „najmniejszy” sumuje wszystkie modele rozwiązania, reranker dokłada 0,64 GB (razem 3,20 GB). Wtedy uruchomić
  `RERANK=0 bash /scratch/maly/final_maly.sh PKG` — samo BM25, jeden model 2,56 GB, zmierzone 24/60 i 48/131
  (panel 4). Tryb raw (bez harnessu) ma ok. 36,7% / 35% — za mały zapas.
- Na L40S dysk sieciowy `/workspace` miał w nocy dwie kilkunastominutowe awarie (odmowa zapisu i odczytu). Finał
  uruchamiać z kopii na lokalnym `/scratch` (`final_maly.sh` robi to sam i w razie braku przełącza się na `/workspace`).

## Uruchomienie finału

```bash
# na L40S (ssh root@<IP z `fh session ls`>), paczka = exam.json + answers-template.json + images/
bash /scratch/maly/final_maly.sh /ścieżka/do/paczki_final            # MODE=hybrid, QUANT=IQ4_XS domyślnie
# -> wypisuje "ANSWERS: <ścieżka>/answers.json" (walidacja wobec szablonu w środku)
```

Próba generalna na paczce próbnej: 37/37, VALID, 60 s łącznie (odpowiadanie 48 s), odpowiedzi bajt w bajt identyczne
z ocenionym przebiegiem. VRAM: model 3,95 GB + reranker 0,9 GB; RAM < 2,5 GB.

Skrypty: `maly/scripts/` (`final_maly.sh`, `run_final_maly.sh`, `eval3.sh`, `essays3.sh`, `fetch*.sh`).
Kod harnessu i bazy wiedzy użyty w przebiegach = `maly/code/` (harness + kb; kopia na L40S: `/workspace/maly/code`, `/scratch/maly/code`, md5 `exam_runner.py` 245a62ea…). Indeks BM25 polskiej Wikipedii: `scripts/download_models.sh` (HF `zeemowo/vibers-wmt-matura`) albo `maly/code/kb/run_all.sh`. Materiały CKE (arkusze, klucze, paczka próbna) nie są w repo; pobiera się je skryptami `scripts/fetch_cke.py` / ze strony organizatorów.
