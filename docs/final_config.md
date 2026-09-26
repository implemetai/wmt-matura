# Konfiguracja finału (decyzja zespołu, 26.09.2026 ~20:40)

**System „progress”: Bielik-4.5B-v3 Q8_0 (zarejestrowana baza, bez LoRA) w trybie hybrydowym + Qwen3.5-9B jako opisywacz obrazów.**

| Element | Ustawienie |
|---|---|
| Model odpowiadający | Bielik-4.5B-v3.0-Instruct Q8_0, sha256 `562f2291…1b7f`, bez adaptera |
| Zadania krótkie (zamknięte, otwarte, rozstrzygnięcia) | surowy Bielik (`exam_runner --mode hybrid` → tryb raw), temperatura 0 |
| Wypracowanie (zadanie 26) | harness v3 (`CKE_MODE=1 QTYPE_V2=1 RERANK=1 ESSAY_SAFE=1`): plan, retrieval z Wikipedii na każdy element, akapity, zakończenie; tryb bezpieczny: tylko lata (najwyżej 2 na akapit), ostrzejsza weryfikacja dat (miesiąc/dzień i rok muszą stać przy tym samym wydarzeniu w znalezionym fragmencie), lepsze z dwóch wypracowań (mniej niepotwierdzonych faktów) |
| Obrazy | Qwen3.5-9B Q5_K_M + mmproj F16 (≤ 8 GB), prompt „literal” (tylko to, co widać; litery/strzałki/legenda; napisy dosłownie; „nieczytelne” zamiast zgadywania), max 800 tokenów; opis trafia do promptu z dopiskiem „automatyczny, może zawierać błędy”, nie trafia do zapytań wyszukiwarki |
| OCR | brak (decyzja zespołu) |
| Serwer | llama.cpp b11185, `-np 1`, `--cache-ram 0`; model wizyjny uruchamiany przed Bielikiem i wyłączany po opisaniu obrazów |
| Uruchomienie | `scripts/run_final.sh PKG_DIR [OUT_DIR]` (całość offline, na jednej maszynie) |

## Dlaczego hybryda

Na arkuszach, których nie używaliśmy do strojenia (CKE 2024 i 2026, 88 pkt; ocena rubryką CKE, `devset/cke_full/grades.jsonl`):

| System | zamknięte /11 | otwarte /47 | wypracowanie /30 | razem |
|---|---|---|---|---|
| surowy Bielik (baza) | 5 | **25** | 4 | 34 |
| harness v3 | 5 | 20 | **9** | 34 |
| harness v3 + LoRA v3 | 4 | 21 | 7 | 32 |
| **hybryda (szacunek z tych samych ocen)** | 5 | 25 | 9 | **39** |

- Harness pomaga tylko przy wypracowaniu. Na czterech arkuszach (2023–2026) wypracowania harnessu mają 22 pkt, surowego Bielika 6.
- Na zadaniach krótkich harness na nowych arkuszach nie pomaga (zamknięte) albo szkodzi (otwarte); zysk na arkuszach 2023 i 2025 wynikał ze strojenia na nich.
- LoRA v3 (RFT na własnych poprawnych rozumowaniach, `docs/cke_v3_lora_eval.md`) nie poprawia wyniku: 32 wobec 34 na odłożonych arkuszach. Zostaje poza finałem.
- Harness v4 (`harness/README.md`, flagi `V4_*`) poprawia ABCD, psuje P/F; na pełnych arkuszach nieoceniony. Poza finałem.
- Model wizyjny: wybór na ślepo spośród 5 kandydatów (`docs/vision_describer_eval.md`). Na próbnym egzaminie z harnessem v3 domyślne opisy wypadły gorzej niż OCR na zadaniach z obrazami (8 wobec 13 pkt z 31). Poprawki (prompt „literal”, dopisek o błędach, opis poza wyszukiwarką) nie zostały ocenione rubryką, bo zespół zdecydował o oszczędzaniu tokenów. Nawet oficjalne opisy CKE (arkusz 660) dawały surowemu Bielikowi tylko +1–2 pkt.

## Ryzyka

- Pojedynczy przebieg na zajętym serwerze waha się o ±4 pkt; finał idzie na wolnym GPU z `-np 1`.
- Oczekiwany przyrost nad bazą na nowym arkuszu: ok. +5 pkt (wypracowanie), niepewność kilka punktów.

## Benchmark konfiguracji finałowej (26.09 wieczór, ślepa ocena rubryką CKE, egzaminatorzy Claude Opus)

| Benchmark | Baza (surowy Bielik) | System finałowy |
|---|---|---|
| 12 wypracowań formuły 2023 (grudzień 2022 – styczeń 2026), 3 egzaminatorów, mediana | 1,7 / 15 | poprzedni pipeline 4,75–4,9 / 15; **ESSAY_SAFE=1: 6,17 / 15** (lepszy od poprzedniego w 7 z 12, gorszy w 2; wpadki ≤ 3 pkt: 2 wobec 3) |
| Zadania krótkie 4 arkuszy CKE (126 pkt) | 70 / 126 | te same odpowiedzi (surowy Bielik) |
| Próbny egzamin organizatorów (60 pkt, same PNG) | 24–25 / 60 | 25–27 / 60 z poprzednim wypracowaniem (dwa przebiegi) |

Oczekiwany przyrost nad bazą na nowym arkuszu: ok. +4,5 pkt (wypracowanie), pojedynczy przebieg ±3.

### Iteracja 2 wypracowania (26.09 ~22:30) — odrzucona

`ESSAY_SAFE=2` (tylko lata, bez miesięcy i dni; akapity w stałym porządku: teza → kontekst → fakty → skutek → werdykt) wobec `ESSAY_SAFE=1` na tych samych 12 tematach, 3 egzaminatorów na ślepo: **5,17 wobec 6,08 / 15**, wygrane 3, porażki 7, 2 remisy. Mniej błędów rzeczowych (2,25 wobec 2,6), ale słabsze omówienie elementów. W finale zostaje `ESSAY_SAFE=1` (druga niezależna ocena: 6,08, pierwsza 6,17).

### Odporność na awarie L40S (26.09 ~23:50)

- Dysk sieciowy `/workspace` (NFS) znikał 3 razy (17:17, 22:07, 23:12, po ~10–40 min). llama-server przeżywał każdą awarię; harness raz padł z „Bus error” (23:12). Wszystkie pliki finału (modele, indeks, venv, kod) są na lokalnym `/scratch`.
- `run_final.sh` ustawia `HOME`, `HF_HOME`, `XDG_CACHE_HOME` na `/scratch/final_home` i `PYTHONNOUSERSITE=1`, żeby żaden proces nie dotykał `/workspace`.
- `exam_runner --mode hybrid`: jeśli harness nie odpowiada przy wypracowaniu, pisze je surowy Bielik (`route: raw-fallback`), zamiast zostawić puste pole. Sprawdzone na próbnym egzaminie z harnessem wyłączonym.
- Gdy SSH nie działa, dostęp awaryjny przez terminal JupyterLab (`fh session jupyter`).

### Fine-tuning wypracowania (RFT, noc 26/27.09) — nie wchodzi do finału

LoRA `bielik45-essay-rft-r16-e2` (sha256 `ff3b24abfdb0ad5556bd2b96bcb2605a9cf11926d77186a95c299197364ef950`): 660 wypracowań Bielika (165 tematów: 120 nowych w stylu formuły 2023 i 45 starych tematów CKE; bez tematów testowych), selekcja regułami (zero niepotwierdzonych faktów, teza, elementy w osobnych akapitach, zakończenie, długość), 164 najlepsze, 762 akapity treningowe; cele to wyłącznie teksty samego Bielika. Na 12 tematach testowych, 3 egzaminatorów na ślepo: **6,42 wobec 6,50 / 15** dla `ESSAY_SAFE=1` (4 wygrane, 5 porażek, 3 remisy); najgorsze wypracowanie 4 wobec 2, wpadek ≤ 3 pkt: 0 wobec 2. Brak zysku w średniej, a obsługa adaptera tylko dla wypracowania wymaga jawnej skali LoRA w każdym zapytaniu (w llama.cpp b11185 `--lora-init-without-apply` nie wyłącza adaptera) — ryzyko dla zadań krótkich bez zysku, więc finał zostaje bez LoRA. Adapter i dane: `train/loras/` (poza gitem), skrypty `train/essay_rft/`.

`ESSAY_SAFE=1` oceniony trzeci raz niezależnie: 6,50 (wcześniej 6,17 i 6,08).
