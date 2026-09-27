# Finał — instrukcja krok po kroku (dla osoby, która uruchamia i prezentuje)

Niedziela 27.09: **trening zamrożony o 11:00**, potem egzamin i prezentacje. Nasz system jest gotowy i przetestowany;
uruchomienie to jedna komenda (~4 min) plus przebieg bazowy (~2 min). Czytaj od góry do dołu.

## Co musisz mieć

- **Dostęp do maszyny L40S w Forgehand** (sesja `01a0dd35`, zespół na https://app.forgehand.app/): konto w zespole.
  Najprościej przez przeglądarkę: `fh session jupyter 01a0dd35` wypisuje jednorazowy link do JupyterLab (terminal +
  przeglądarka plików). Albo SSH: `fh session ssh 01a0dd35`. (CLI: `fh login`, potem `fh session ls`.)
- **TEAM_KEY** drużyny — od kapitana (Patryk). Nie wpisuj go do żadnego pliku ani na Slacka.
- Strona do wysyłki odpowiedzi: https://warsawmodeltrainers.dev/submissions.html
- Paczka egzaminu pojawi się o 11:00 u organizatorów (jak próbna: przewodnik https://matura-json-guide.ania-olchowik.chatgpt.site/
  i/lub aplikacja https://warsawmodeltrainers.dev/matura.html).

## 10:30 — przygotowanie (5 min)

1. `fh session ls` → sesja `01a0dd35` ma stan `running`. Otwórz JupyterLab (link z `fh session jupyter 01a0dd35`) i terminal.
2. W terminalu:
   ```bash
   nvidia-smi --query-gpu=memory.used,memory.total --format=csv   # potrzeba ~10 GB wolnego
   pgrep -fa llama-server | grep -oE 'port [0-9]+'                 # 18092/18093/18094 to stare wspólne serwery — mogą zostać
   ```
   Jeśli ktoś (np. druga osoba z zespołu) ma uruchomione swoje modele i VRAM jest ciasny — poproś o zatrzymanie.
3. (Opcjonalnie, próba generalna ~4 min):
   ```bash
   cd /scratch/mock/wmt-matura && scripts/run_final.sh data_cke/mock2023 /scratch/final_rehearsal_$(date +%H%M)
   ```
   Na końcu ma być `VALID` i `ANSWERS: ...`.

## 11:00 — egzamin

1. **Pobierz paczkę** finałową od organizatorów (zip z `exam.json`, `answers-template.json`, `images/`).
   Jeśli przyjdzie w częściach (`exam-pack-1.bin`, `exam-pack-2.bin`, …), połącz je: `cat exam-pack-*.bin > final.zip`.
2. **Wgraj ją na L40S:** w JupyterLab przeciągnij plik zip do przeglądarki plików (trafia do `/workspace/`).
3. **Uruchom** (terminal JupyterLab albo SSH):
   ```bash
   mkdir -p /scratch/final_pack && cd /scratch/final_pack && unzip -o /workspace/*.zip
   PKG=$(dirname "$(find /scratch/final_pack -name exam.json | head -1)"); echo "$PKG"
   cd /scratch/mock/wmt-matura
   scripts/run_final.sh "$PKG" /scratch/final_out            # NASZ SYSTEM, ~4 min, na końcu: VALID + ANSWERS: ...
   scripts/run_final_base.sh "$PKG" /scratch/final_out_base  # BAZA (nietknięty Bielik), ~2 min, na końcu: VALID
   cp /scratch/final_out/answers.json /workspace/answers_final_vibers.json
   cp /scratch/final_out_base/answers.json /workspace/answers_final_base.json
   ```
4. **Pobierz oba pliki** z przeglądarki plików JupyterLab (prawy klik → Download).
5. **Wyślij** na https://warsawmodeltrainers.dev/submissions.html: TEAM_KEY, nazwa rozwiązania, wybierz egzamin
   finałowy, wgraj plik. Nasz system: `answers_final_vibers.json` (nazwa np. `vibers-bielik45-hybrid-essay`).
   Baza (nietknięty model, do liczenia postępu): `answers_final_base.json` (nazwa np. `vibers-bielik45-base`) — jeśli
   strona pyta osobno o model bazowy, to jest ten plik. Zachowaj potwierdzenia wysyłki.

## Gdy coś pójdzie źle

| Objaw | Co zrobić |
|---|---|
| SSH: `Connection reset` | Dysk sieciowy `/workspace` na tej maszynie znika czasem na ~10–40 min (26.09: 3 razy). Użyj terminala JupyterLab — działa dalej. Nasz przebieg korzysta tylko z lokalnego `/scratch`, więc się nie zatrzyma. |
| Nie da się wgrać/pobrać pliku w JupyterLab (błąd 500 / Permission denied) | To ta sama awaria `/workspace`. Poczekaj kilka minut albo użyj `scp` przez SSH do/z `/scratch`. |
| `FINAL: port 182xx already in use` | Poprzedni przebieg nie skończył się. Sprawdź `pgrep -fa llama-server`; możesz podać inne porty: `VLM_PORT=18410 LLM_PORT=18400 RER_PORT=18402 H_PORT=18403 scripts/run_final.sh ...` |
| `FINAL: free VRAM ... < needed` | Ktoś zajmuje GPU — poproś o zatrzymanie jego serwerów (nasze wspólne 18092/18093/18094 zajmują tylko ~13 GB z 46). |
| W logu `[hybrid] harness failed ... raw fallback` | Harness padł — wypracowanie napisał sam Bielik (gorzej, ale nie puste). Plik i tak jest ważny. |
| Walidacja pokazuje `blank` dla jakiegoś zadania | Uruchom tę samą komendę z tym samym katalogiem wyjściowym jeszcze raz — dogoni tylko brakujące zadania. |
| Sesja `01a0dd35` nie istnieje / jest zatrzymana | Plan awaryjny (~45 min): nowa sesja L40S, `git clone https://github.com/pw-off/wmt-matura`, `scripts/forgehand_setup.sh` (llama.cpp + venv), `scripts/download_models.sh /scratch/models_final` (wagi + indeks z Hugging Face, sprawdzane sha256), potem `run_final.sh` ze ścieżkami podanymi w nagłówku `download_models.sh`. |

## Co zgłaszamy (rejestracja w aplikacji)

- Model bazowy: **Bielik-4.5B-v3.0-Instruct, GGUF Q8_0**, https://huggingface.co/speakleash/Bielik-4.5B-v3.0-Instruct-GGUF ,
  5,06 GB, sha256 `562f2291de257890adf2b4a914da8b194affe6a7a838a6b7ef3d342f306c1b7f` (kopia: https://huggingface.co/zeemowo/vibers-wmt-matura).
- Wersja „wytrenowana”: te same, niezmienione wagi + nasz harness (wypracowanie z bazą wiedzy z Wikipedii) + model
  wizyjny Qwen3.5-9B (7,5 GB) tylko do opisów obrazów. Każdy model ≤ 8 GB osobno (potwierdzone z organizatorami).
- Repozytorium: https://github.com/pw-off/wmt-matura (publiczne; `SOURCE.md` jest).
