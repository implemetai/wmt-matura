# Prezentacja (2–3 min + 1–2 min pytań) — ściąga

## Pitch (ok. 2,5 min)

1. **Co zbudowaliśmy.** Jeden otwarty model, **Bielik-4.5B (5 GB)**, rozwiązuje maturę z historii offline na jednej
   karcie. Wokół niego: baza wiedzy z **całej polskiej Wikipedii** (1,5 mln artykułów, 3,4 mln fragmentów) i mały model
   wizyjny, który tylko zamienia obrazy z arkusza na polski opis. Żadnych zamkniętych API w trakcie egzaminu.
2. **Najważniejsza lekcja: mierz na prawdziwych arkuszach.** Na własnych pytaniach nasz LoRA dawał +70 pp. Na pełnych
   arkuszach CKE, ocenianych rubryką CKE przez **trzech niezależnych egzaminatorów na ślepo**, dawał zero. Od tej chwili
   każda decyzja szła przez ten pomiar.
3. **Co zadziałało: wypracowanie.** Pipeline: plan → wyszukiwanie w Wikipedii dla każdego elementu tematu → akapity →
   ścisła weryfikacja dat w znalezionych fragmentach → lepsze z dwóch wypracowań. Na 12 arkuszach (2022–2026):
   **1,7 → 6,2 pkt na 15**, bez wypracowań poniżej progu 300 słów.
4. **Co nie zadziałało (i dlaczego to też wynik).** LoRA na 4 tys. pytań od Claude'a, RFT na własnych poprawnych
   rozumowaniach Bielika, fine-tuning wypracowań na jego najlepszych tekstach, rozbudowany harness do zadań krótkich —
   na odłożonych arkuszach nie pobiły czystego Bielika. Zostawiliśmy tylko to, co wygrało pomiar.
5. **Wynik.** Zadania krótkie rozwiązuje czysty Bielik (~56% na 4 arkuszach), wypracowanie nasz pipeline.
   Oczekiwany przyrost nad bazą na nowym arkuszu: **ok. +4,5 pkt**, cały z wypracowania. Wszystko odtwarzalne:
   repozytorium + wagi i indeks na Hugging Face + jedna komenda `run_final.sh`.

## Liczby pod ręką

| | Baza (czysty Bielik) | Nasz system |
|---|---|---|
| 12 wypracowań formuły 2023, 3 egzaminatorów | 1,7 / 15 | **6,2 / 15** (3 niezależne oceny: 6,17 / 6,08 / 6,50) |
| Zadania krótkie, 4 arkusze CKE (126 pkt) | 70 / 126 | te same odpowiedzi |
| Próbny egzamin organizatorów (60 pkt, same PNG) | 24–25 / 60 | 25–27 / 60 (przed wprowadzeniem trybu bezpiecznego wypracowania) |

## Pytania, które mogą paść

- **Czemu nie fine-tuning?** Zrobiliśmy trzy (LoRA na krótkich odpowiedziach, RFT na rozumowaniach, RFT na wypracowaniach) —
  żaden nie wygrał ślepej oceny na odłożonych arkuszach. Adaptery i raporty są w repo (`docs/`).
- **Po co model wizyjny?** Egzamin daje same obrazy (mapy, karykatury, drzewa genealogiczne); Bielik jest tekstowy.
  Qwen3.5-9B wybraliśmy na ślepo spośród 5 kandydatów; opis trafia do Bielika z dopiskiem „automatyczny, może zawierać błędy”.
- **Skąd dane?** Pytania treningowe/testowe generował i weryfikował Claude z artykułów Wikipedii i otwarcie licencjonowanych
  materiałów ZPE. Arkusze CKE tylko do oceny — nie ma ich w repo (prawa autorskie), są skrypty do pobrania.
- **Jak liczyliście wynik?** Rubryka CKE, egzaminatorzy Claude Opus na ślepo (losowe etykiety), 3 niezależnych przy wypracowaniach;
  zgodność egzaminatorów poza wypracowaniami ~100%.
- **Największy problem?** Szum: ten sam arkusz na zajętym serwerze dawał ±4 pkt. Finał idzie deterministycznie (`-np 1`).
- **Co dalej?** Wypracowanie to wciąż największa rezerwa (6 z 15) — błędy w datach i powierzchowne argumenty.
