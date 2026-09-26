"""Build train/essay_rft/topics.jsonl: essay topics for Bielik essay RFT.

source='cke_old'   : single topics from OLD-formula CKE papers 2003-2022 (git-ignored inputs).
source='generated' : new topics in the CKE formula-2023 style (thesis + stance frame),
                     written by us as PROMPTS only (never training targets).
The 12 formula-2023 essay rows in devset/cke-essays.jsonl are the evaluation set: they are
only read here to drop near-duplicates, never emitted.

Output is CKE-derived -> train/essay_rft/*.jsonl is git-ignored.
"""
import json, math, os, re, sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from parse_cke_old import ROOT, EVAL_IDS, load as load_cke_old  # noqa: E402

ST, SR, NO, XIX, XX = 'starożytność', 'średniowiecze', 'nowożytność', 'XIX w.', 'XX w.'

# Era of each old CKE topic (ids only, no CKE text here).
OLD_ERA = {
    '2003-maj-z39': [ST, SR, SR], '2003-maj-z44': [NO, NO, NO], '2003-maj-z40': [XIX, XX, XX],
    '2005-maj-z51': [SR, XX], '2006-maj-z53': [SR, SR], '2007-maj-z24': [NO, XX],
    '2008-maj-z24': [NO, XX], '2009-maj-z26': [NO, XIX], '2010-maj-z24': [NO, XX],
    '2011-czerwiec-z22': [SR, NO], '2011-maj-z24': [NO, XX], '2012-czerwiec-z26': [SR, XX],
    '2012-maj-z25': [ST, XX], '2013-maj-z26': [SR, XX], '2014-maj-z23': [XIX, XX],
    **{p: [ST, SR, NO, XIX, XX] for p in
       ['2015-maj-z22', '2016-maj', '2017-maj', '2018-maj', '2019-maj', '2021-maj', '2022-maj']},
}
# Manual overlap review against the 36 formula-2023 EVAL topics.
# near_eval   = essentially the same subject as an eval topic (old topics only; kept because the task
#               says "every old topic", but a clean eval run should drop them).
# eval_related = same period/theme, different thesis (partial overlap; keep or drop as policy dictates).
# Generated topics with a real near-duplicate were rejected while writing (e.g. "najwybitniejszy
# władca elekcyjny", "unia lubelska korzystniejsza dla...", "potop jako najgroźniejszy konflikt XVII w.",
# "Jałta przesądziła...", "przydomek Wielki", "Galicja najlepsze warunki").
OLD_NEAR_EVAL = {
    'old-2018-maj-t3': '2023-przykladowy#2, 2022-grudzien-probna#2 (upadek RP XVIII w.)',
    'old-2019-maj-t2': '2024-maj#1 (Karol Wielki)',
    'old-2022-maj-t2': '2025-czerwiec#1 (krucjaty)',
    'old-2022-maj-t4': '2026-styczen-probna#2 (Napoleon a Polacy)',
    'old-2017-maj-t4': '2026-styczen-probna#2 (Ksiestwo Warszawskie / Napoleon)',
    'old-2012-maj-z25-t2': '2024-maj#3 (Pilsudski i niepodleglosc)',
    'old-2021-maj-t2': '2022-grudzien-probna#1 (problem krzyzacki)',
    'old-2013-maj-z26-t1': '2022-grudzien-probna#1 (problem krzyzacki)',
    'old-2011-czerwiec-z22-t1': '2022-grudzien-probna#1 (Pomorze / Krzyzacy)',
    'old-2019-maj-t5': '2026-maj#3 (kleska 1939)',
    'old-2021-maj-t3': '2026-czerwiec#2 (Jagiellonowie / zloty wiek)',
    'old-2021-maj-t4': '2026-maj#2 (rewolucja przemyslowa)',
    'old-2015-maj-z22-t2': '2023-czerwiec#1 (rozbicie dzielnicowe)',
    'old-2008-maj-z24-t1': '2024-maj#2 (wojny z Turcja XVII w.)',
}
EVAL_RELATED = {
    'old-2018-maj-t5': '2024-maj#3', 'old-2016-maj-t4': '2024-maj#3',
    'old-2011-maj-z24-t2': '2025-czerwiec#3', 'old-2017-maj-t5': '2025-czerwiec#3',
    'old-2010-maj-z24-t2': '2025-czerwiec#3', 'old-2019-maj-t3': '2024-grudzien-probna#2',
    'old-2011-maj-z24-t1': '2023-przykladowy#2', 'old-2022-maj-t5': '2023-czerwiec#3',
    'old-2012-czerwiec-z26-t1': '2024-grudzien-probna#1', 'old-2018-maj-t2': '2023-przykladowy#1',
    'old-2014-maj-z23-t1': '2023-czerwiec#2', 'old-2018-maj-t4': '2023-czerwiec#2',
    'old-2003-maj-z40-t1': '2023-czerwiec#2', 'old-2008-maj-z24-t2': '2025-maj#3',
    'old-2022-maj-t3': '2026-maj#1', 'old-2011-czerwiec-z22-t2': '2026-styczen-probna#1',
    'old-2022-maj-t1': '2026-czerwiec#1', 'old-2012-maj-z25-t1': '2026-czerwiec#1',
}
EVAL_RELATED_GEN = {  # thesis prefix -> eval topic
    'Najtrwalszym skutkiem podbojów Aleksandra': '2026-czerwiec#1',
    'O zwycięstwie Rzymu w wojnach punickich': '2026-czerwiec#1',
    'Kolonizacja na prawie niemieckim': '2023-czerwiec#1',
    'Panowanie Kazimierza Wielkiego': '2024-czerwiec#1',
    'Przywileje szlacheckie z XIV': '2025-maj#1',
    'Wprowadzenie wolnej elekcji': '2023-przykladowy#2',
    'Sarmatyzm był': '2024-grudzien-probna#2',
    'Stany Zjednoczone wywalczyły': '2023-maj#2',
    'Konstytucja 3 maja': '2023-przykladowy#2',
    'Polityka germanizacyjna': '2023-czerwiec#2',
    'Traktat wersalski': '2026-styczen-probna#3',
    'Bitwa Warszawska w 1920': '2024-maj#3',
    'Największym sukcesem gospodarczym II': '2025-czerwiec#3',
    'Polityka ustępstw wobec III Rzeszy': '2026-maj#3',
    'Decyzja o wybuchu powstania warszawskiego': '2023-przykladowy#3',
    'Okres stalinizmu w Polsce': '2025-maj#3',
}

Z = 'Zajmij stanowisko wobec powyższej tezy i je uzasadnij, uwzględniając w swojej argumentacji '
Z_SHORT = 'Zajmij stanowisko wobec powyższej tezy i je uzasadnij, uwzględniając w argumentacji '
Z_NOUZ = 'Zajmij stanowisko wobec powyższej tezy, uwzględniając w swojej argumentacji '
PSK = 'aspekty: polityczny, społeczno-gospodarczy i kulturowy.'

GENERATED = [
    # --- starożytność (18) ---
    (ST, 'Warunki naturalne miały decydujący wpływ na rozwój cywilizacji starożytnego Egiptu i Mezopotamii.', PSK),
    (ST, 'Demokracja ateńska w V wieku p.n.e. zapewniała rzeczywisty udział w rządach wszystkim mieszkańcom Aten.', 'aspekty: ustrojowy, społeczno-gospodarczy i kulturowy.'),
    (ST, 'Sparta zawdzięczała swoją pozycję w świecie greckim wyłącznie sile militarnej.', 'aspekty: militarny, ustrojowy i społeczno-gospodarczy.'),
    (ST, 'Wojny grecko-perskie przyniosły Grekom więcej korzyści niż strat.', 'aspekty: militarny, polityczny i kulturowy.'),
    (ST, 'Wojna peloponeska doprowadziła do trwałego osłabienia świata greckiego.', 'aspekty: polityczny, militarny i społeczno-gospodarczy.'),
    (ST, 'Najtrwalszym skutkiem podbojów Aleksandra Wielkiego było powstanie kultury hellenistycznej.', PSK),
    (ST, 'O zwycięstwie Rzymu w wojnach punickich zadecydowała przede wszystkim przewaga militarna.', 'aspekty: militarny, polityczny i społeczno-gospodarczy.'),
    (ST, 'Upadek republiki rzymskiej był nieuchronnym następstwem ekspansji terytorialnej Rzymu.', 'aspekty: ustrojowy, społeczno-gospodarczy i militarny.'),
    (ST, 'Pryncypat Oktawiana Augusta był w rzeczywistości monarchią, a nie odnowioną republiką.', 'aspekty: ustrojowy, polityczny i kulturowy.'),
    (ST, 'Okres pax Romana był czasem największej pomyślności w dziejach imperium rzymskiego.', PSK),
    (ST, 'Chrześcijaństwo zwyciężyło w imperium rzymskim przede wszystkim dzięki poparciu władzy cesarskiej.', 'trzy wybrane wydarzenia z dziejów chrześcijaństwa w okresie od I do IV wieku.'),
    (ST, 'Kryzys III wieku zapoczątkował upadek cesarstwa rzymskiego.', 'aspekty: polityczny, militarny i społeczno-gospodarczy.'),
    (ST, 'Dziedzictwo starożytnej Grecji wywarło większy wpływ na kulturę europejską niż dziedzictwo Rzymu.', 'dorobek Greków i Rzymian w trzech wybranych dziedzinach kultury.'),
    (ST, 'Cywilizacje starożytnego Bliskiego Wschodu położyły fundamenty pod rozwój kultury europejskiej.', 'dorobek trzech wybranych cywilizacji tego regionu.'),
    (ST, 'Religia odgrywała decydującą rolę w życiu starożytnych Egipcjan.', PSK),
    (ST, 'Imperium perskie Achemenidów było najlepiej zorganizowanym państwem starożytnego Bliskiego Wschodu.', 'aspekty: ustrojowy, militarny i społeczno-gospodarczy.'),
    (ST, 'Wielka kolonizacja grecka przyczyniła się do rozwoju całego basenu Morza Śródziemnego.', PSK),
    (ST, 'Trwałość imperium rzymskiego w większym stopniu zapewniały prawo i administracja niż siła legionów.', 'aspekty: ustrojowy, militarny i społeczno-gospodarczy.'),
    # --- średniowiecze (24) ---
    (SR, 'Chrzest Polski w 966 roku był najważniejszym wydarzeniem w dziejach państwa pierwszych Piastów.', PSK),
    (SR, 'Panowanie Bolesława Chrobrego było okresem największej potęgi państwa pierwszych Piastów.', 'aspekty: polityczny, militarny i kulturowy.'),
    (SR, 'Cesarstwo bizantyjskie osiągnęło szczyt swojej potęgi za panowania Justyniana Wielkiego.', 'aspekty: polityczny, militarny i kulturowy.'),
    (SR, 'Ekspansja arabska w VII–VIII wieku przyniosła podbitym ludom więcej korzyści niż strat.', PSK),
    (SR, 'Spór o inwestyturę zakończył się zwycięstwem papiestwa.', 'trzy wybrane wydarzenia z dziejów tego konfliktu.'),
    (SR, 'Kościół był najważniejszą instytucją średniowiecznej Europy.', PSK),
    (SR, 'Rozwój instytucji stanowych w średniowiecznej Anglii i Francji osłabił władzę monarszą.', 'aspekty: ustrojowy, polityczny i społeczno-gospodarczy.'),
    (SR, 'Wojna stuletnia przyczyniła się do umocnienia monarchii we Francji.', 'aspekty: militarny, polityczny i społeczno-gospodarczy.'),
    (SR, 'Czarna śmierć zapoczątkowała głębokie przemiany w Europie XIV wieku.', 'aspekty: społeczny, gospodarczy i kulturowy.'),
    (SR, 'Najazdy wikingów przyczyniły się do rozwoju wczesnośredniowiecznej Europy.', PSK),
    (SR, 'Najazdy mongolskie w XIII wieku miały katastrofalne skutki dla Europy Środkowo-Wschodniej.', 'aspekty: polityczny, militarny i społeczno-gospodarczy.'),
    (SR, 'Kolonizacja na prawie niemieckim była najważniejszym czynnikiem przemian na ziemiach polskich w XIII–XIV wieku.', 'aspekty: społeczny, gospodarczy i kulturowy.'),
    (SR, 'Zjednoczenie ziem polskich na przełomie XIII i XIV wieku było przede wszystkim zasługą Władysława Łokietka.', 'aspekty: polityczny, militarny i dyplomatyczny.'),
    (SR, 'Panowanie Kazimierza Wielkiego było przełomowym okresem w dziejach Polski średniowiecznej.', 'aspekty: ustrojowy, społeczno-gospodarczy i międzynarodowy.'),
    (SR, 'Przywileje szlacheckie z XIV–XV wieku zapoczątkowały budowę demokracji szlacheckiej w Polsce.', 'aspekty: ustrojowy, społeczny i gospodarczy.'),
    (SR, 'Przyjęcie chrześcijaństwa zadecydowało o przetrwaniu państw Europy Środkowej i Północnej powstałych w X–XI wieku.', 'dzieje trzech wybranych państw.'),
    (SR, 'Średniowieczne miasta były głównym motorem rozwoju gospodarczego Europy.', 'aspekty: społeczny, gospodarczy i kulturowy.'),
    (SR, 'Działalność zakonów była głównym czynnikiem rozwoju cywilizacyjnego ziem polskich w średniowieczu.', 'aspekty: religijny, gospodarczy i kulturowy.'),
    (SR, 'Idea uniwersalizmu cesarskiego Ottona III sprzyjała rozwojowi państwa polskiego.', 'aspekty: polityczny, religijny i kulturowy.'),
    (SR, 'Wielka schizma wschodnia trwale podzieliła Europę na dwa kręgi cywilizacyjne.', 'aspekty: polityczny, religijny i kulturowy.'),
    (SR, 'Zdobycie Konstantynopola przez Turków w 1453 roku miało przełomowe znaczenie dla dziejów Europy.', PSK),
    (SR, 'Przyjęcie chrześcijaństwa z Bizancjum w największym stopniu ukształtowało dzieje Rusi Kijowskiej.', PSK),
    (SR, 'Rekonkwista była głównym czynnikiem kształtującym dzieje Półwyspu Iberyjskiego w średniowieczu.', PSK),
    (SR, 'Wielka karta swobód z 1215 roku zapoczątkowała rozwój parlamentaryzmu w Anglii.', 'trzy wybrane wydarzenia z dziejów Anglii w XIII–XV wieku.'),
    # --- nowożytność (30) ---
    (NO, 'Wielkie odkrycia geograficzne przyniosły Europejczykom więcej korzyści niż strat.', PSK),
    (NO, 'Kolonizacja hiszpańska w XVI wieku miała katastrofalne skutki dla ludów Ameryki.', PSK),
    (NO, 'Renesans był epoką przełomu w dziejach kultury europejskiej.', 'dokonania trzech wybranych twórców tej epoki.'),
    (NO, 'Reformacja przyczyniła się do rozwoju kultury europejskiej w XVI wieku.', 'aspekty: polityczny, społeczny i kulturowy.'),
    (NO, 'Sobór trydencki skutecznie powstrzymał rozwój reformacji w Europie.', 'aspekty: religijny, polityczny i kulturowy.'),
    (NO, 'Rzeczpospolita w XVI wieku zasłużenie nazywana była „państwem bez stosów”.', 'aspekty: ustrojowy, społeczny i kulturowy.'),
    (NO, 'Ruch egzekucyjny był najskuteczniejszą próbą naprawy państwa polskiego w XVI wieku.', 'aspekty: ustrojowy, polityczny i społeczno-gospodarczy.'),
    (NO, 'Wprowadzenie wolnej elekcji osłabiło Rzeczpospolitą.', 'przebieg i skutki trzech wybranych elekcji z XVI–XVII wieku.'),
    (NO, 'Rzeczpospolita w XVI wieku prowadziła skuteczną politykę bałtycką.', 'aspekty: militarny, dyplomatyczny i gospodarczy.'),
    (NO, 'Rozwój gospodarki folwarczno-pańszczyźnianej w XVI wieku stał się źródłem późniejszego zacofania Rzeczypospolitej.', 'aspekty: społeczny, gospodarczy i polityczny.'),
    (NO, 'Gdańsk odgrywał kluczową rolę w gospodarce Rzeczypospolitej w XVI–XVII wieku.', 'aspekty: gospodarczy, polityczny i kulturowy.'),
    (NO, 'Rządy Ludwika XIV były wzorcowym przykładem monarchii absolutnej.', 'aspekty: ustrojowy, społeczno-gospodarczy i kulturowy.'),
    (NO, 'Rewolucja angielska w XVII wieku zapoczątkowała rozwój nowoczesnego parlamentaryzmu.', 'trzy wybrane wydarzenia z dziejów Anglii w XVII wieku.'),
    (NO, 'Absolutyzm oświecony służył przede wszystkim wzmocnieniu państwa, a nie dobru poddanych.', 'panowanie trzech wybranych władców.'),
    (NO, 'Reformy Piotra I uczyniły z Rosji mocarstwo europejskie.', 'aspekty: ustrojowy, militarny i społeczno-gospodarczy.'),
    (NO, 'Sarmatyzm był oryginalnym i wartościowym zjawiskiem w kulturze Rzeczypospolitej.', 'aspekty: polityczny, społeczny i kulturowy.'),
    (NO, 'Wojna trzydziestoletnia była w większym stopniu konfliktem politycznym niż religijnym.', 'aspekty: polityczny, religijny i militarny.'),
    (NO, 'Pokój westfalski ukształtował nowy ład polityczny w Europie.', 'aspekty: polityczny, religijny i terytorialny.'),
    (NO, 'Za panowania Karola V monarchia Habsburgów była najpotężniejszym państwem Europy.', 'aspekty: polityczny, militarny i gospodarczy.'),
    (NO, 'Rewolucja naukowa XVI–XVII wieku zmieniła sposób postrzegania świata przez Europejczyków.', 'dokonania trzech wybranych uczonych.'),
    (NO, 'Stany Zjednoczone wywalczyły niepodległość przede wszystkim dzięki pomocy Francji.', 'aspekty: militarny, dyplomatyczny i polityczny.'),
    (NO, 'Konstytucja Stanów Zjednoczonych z 1787 roku była urzeczywistnieniem idei oświeceniowych.', 'aspekty: ustrojowy, polityczny i społeczny.'),
    (NO, 'Okres dyktatury jakobinów był zaprzeczeniem ideałów rewolucji francuskiej.', PSK),
    (NO, 'Konstytucja 3 maja była najważniejszym osiągnięciem Sejmu Czteroletniego.', 'aspekty: ustrojowy, społeczny i międzynarodowy.'),
    (NO, 'Wojna siedmioletnia była pierwszym konfliktem o zasięgu światowym.', 'aspekty: militarny, polityczny i gospodarczy.'),
    (NO, 'Wzrost potęgi Prus w XVIII wieku był przede wszystkim efektem polityki ich władców.', 'panowanie trzech wybranych władców.'),
    (NO, 'Handel atlantycki w XVI–XVIII wieku był podstawą bogactwa państw zachodniej Europy.', 'aspekty: społeczno-gospodarczy, polityczny i kulturowy.'),
    (NO, 'XVII wiek był złotym wiekiem Republiki Zjednoczonych Prowincji Niderlandów.', PSK),
    (NO, 'Imperium osmańskie osiągnęło szczyt potęgi za panowania Sulejmana Wspaniałego.', 'aspekty: militarny, polityczny i kulturowy.'),
    (NO, 'Sztuka baroku była przede wszystkim narzędziem propagandy Kościoła katolickiego i monarchii absolutnych.', 'przykłady z trzech wybranych dziedzin sztuki.'),
    # --- XIX w. (24) ---
    (XIX, 'Klęska powstania listopadowego była wynikiem przede wszystkim błędów jego przywódców.', 'aspekty: militarny, polityczny i międzynarodowy.'),
    (XIX, 'Wielka Emigracja była najważniejszym ośrodkiem polskiego życia politycznego w latach 1831–1863.', 'aspekty: polityczny, ideowy i kulturowy.'),
    (XIX, 'Wiosna Ludów zakończyła się klęską ruchów rewolucyjnych i narodowych w Europie.', 'wydarzenia z trzech wybranych państw.'),
    (XIX, 'Powstanie styczniowe przyniosło społeczeństwu polskiemu więcej strat niż korzyści.', PSK),
    (XIX, 'Praca organiczna była skuteczniejszą formą walki o polskość niż zbrojne powstania.', PSK),
    (XIX, 'Polityka germanizacyjna w zaborze pruskim w drugiej połowie XIX wieku zakończyła się niepowodzeniem.', 'trzy wybrane przejawy tej polityki i reakcje na nie społeczeństwa polskiego.'),
    (XIX, 'Uwłaszczenie chłopów w Królestwie Polskim w 1864 roku było decyzją podyktowaną przede wszystkim interesem politycznym zaborcy.', 'aspekty: polityczny, społeczny i gospodarczy.'),
    (XIX, 'Zjednoczenie Włoch było przede wszystkim zasługą Camilla Cavoura.', 'dokonania trzech wybranych postaci.'),
    (XIX, 'Zjednoczenie Niemiec w 1871 roku zmieniło układ sił w Europie.', 'aspekty: polityczny, militarny i gospodarczy.'),
    (XIX, 'Głównym powodem wybuchu wojny secesyjnej była kwestia niewolnictwa.', PSK),
    (XIX, 'Ekspansja kolonialna mocarstw europejskich w XIX wieku przyniosła ludom Afryki i Azji wyłącznie negatywne skutki.', PSK),
    (XIX, 'Reformy okresu Meiji uczyniły z Japonii nowoczesne mocarstwo.', 'aspekty: ustrojowy, militarny i społeczno-gospodarczy.'),
    (XIX, 'Epoka wiktoriańska była okresem największej potęgi Wielkiej Brytanii.', PSK),
    (XIX, 'XIX wiek był epoką narodzin nowoczesnych ideologii politycznych.', 'założenia trzech wybranych ideologii.'),
    (XIX, 'Ruch robotniczy w XIX wieku przyczynił się do poprawy warunków życia robotników.', 'aspekty: polityczny, społeczny i gospodarczy.'),
    (XIX, 'Kultura romantyzmu odegrała decydującą rolę w podtrzymaniu polskiej świadomości narodowej pod zaborami.', 'dorobek trzech wybranych twórców.'),
    (XIX, 'Wojna krymska była przełomem w stosunkach międzynarodowych w XIX-wiecznej Europie.', 'aspekty: militarny, dyplomatyczny i polityczny.'),
    (XIX, 'Reformy Aleksandra II były nieudaną próbą modernizacji Imperium Rosyjskiego.', 'aspekty: ustrojowy, społeczno-gospodarczy i militarny.'),
    (XIX, 'Królestwo Polskie w latach 1815–1830 cieszyło się szerokim zakresem autonomii.', 'aspekty: ustrojowy, społeczno-gospodarczy i kulturowy.'),
    (XIX, 'Narodziny nowoczesnych partii politycznych pod koniec XIX wieku zmieniły oblicze polskiego życia politycznego.', 'programy trzech wybranych ugrupowań.'),
    (XIX, 'We Francji w XIX wieku żaden ustrój nie zdołał się trwale utrzymać.', 'trzy wybrane okresy dziejów Francji z lat 1815–1875.'),
    (XIX, 'Ekspansja terytorialna w XIX wieku zapewniła Stanom Zjednoczonym status mocarstwa.', 'aspekty: polityczny, militarny i gospodarczy.'),
    (XIX, 'Ruch emancypacyjny kobiet w XIX wieku odniósł znaczące sukcesy.', 'aspekty: polityczny, społeczny i kulturowy.'),
    (XIX, 'Imperium osmańskie w XIX wieku zasłużenie nazywano „chorym człowiekiem Europy”.', 'aspekty: polityczny, militarny i społeczno-gospodarczy.'),
    # --- XX w. (24) ---
    (XX, 'Rewolucja lat 1905–1907 przyniosła Polakom w zaborze rosyjskim istotne zdobycze.', 'aspekty: polityczny, społeczny i kulturowy.'),
    (XX, 'Przejęcie władzy przez bolszewików w 1917 roku było zamachem stanu, a nie rewolucją ludową.', 'aspekty: polityczny, społeczny i militarny.'),
    (XX, 'Traktat wersalski nie zapewnił Europie trwałego pokoju.', 'aspekty: polityczny, militarny i gospodarczy.'),
    (XX, 'Bitwa Warszawska w 1920 roku uratowała Europę przed rozprzestrzenieniem się komunizmu.', 'aspekty: militarny, polityczny i międzynarodowy.'),
    (XX, 'Największym sukcesem gospodarczym II Rzeczypospolitej była budowa Gdyni i Centralnego Okręgu Przemysłowego.', 'aspekty: gospodarczy, społeczny i polityczny.'),
    (XX, 'Polityka New Deal skutecznie wyprowadziła Stany Zjednoczone z wielkiego kryzysu.', 'aspekty: gospodarczy, społeczny i polityczny.'),
    (XX, 'Polityka ustępstw wobec III Rzeszy była błędem mocarstw zachodnich.', 'trzy wybrane wydarzenia z lat 1935–1939.'),
    (XX, 'O klęsce III Rzeszy w II wojnie światowej zadecydowała przede wszystkim przewaga gospodarcza aliantów.', 'aspekty: militarny, gospodarczy i polityczny.'),
    (XX, 'Zagłada Żydów była konsekwencją ideologii nazistowskiej realizowanej od 1933 roku.', 'trzy wybrane etapy polityki III Rzeszy wobec ludności żydowskiej.'),
    (XX, 'Polskie Siły Zbrojne na Zachodzie wniosły istotny wkład w zwycięstwo aliantów.', 'trzy wybrane bitwy z ich udziałem.'),
    (XX, 'Decyzja o wybuchu powstania warszawskiego była uzasadniona.', 'aspekty: polityczny, militarny i społeczny.'),
    (XX, 'Dekolonizacja po II wojnie światowej przyniosła narodom Afryki i Azji rzeczywistą niezależność.', PSK),
    (XX, 'Integracja europejska po II wojnie światowej była przede wszystkim odpowiedzią na zagrożenie ze strony ZSRR.', 'aspekty: polityczny, gospodarczy i militarny.'),
    (XX, 'Rozpad ZSRR był przede wszystkim skutkiem kryzysu gospodarczego.', 'aspekty: polityczny, gospodarczy i narodowościowy.'),
    (XX, 'Okres stalinizmu w Polsce był czasem całkowitego podporządkowania społeczeństwa władzy komunistycznej.', PSK),
    (XX, 'Dekada rządów Edwarda Gierka była okresem pozornego dobrobytu.', PSK),
    (XX, 'Ruch „Solidarności” odegrał decydującą rolę w upadku komunizmu w Polsce.', 'trzy wybrane wydarzenia z lat 1980–1989.'),
    (XX, 'Kościół katolicki był najważniejszą siłą oporu wobec władzy komunistycznej w Polsce.', 'aspekty: polityczny, społeczny i kulturowy.'),
    (XX, 'Wojna wietnamska była największą porażką polityki zagranicznej Stanów Zjednoczonych w XX wieku.', 'aspekty: militarny, polityczny i społeczny.'),
    (XX, 'Organizacja Narodów Zjednoczonych okazała się skuteczniejsza w utrzymaniu pokoju niż Liga Narodów.', 'trzy wybrane konflikty międzynarodowe.'),
    (XX, 'Rządy Mao Zedonga zahamowały rozwój Chin.', PSK),
    (XX, 'Wojny bałkańskie w latach 1912–1913 przygotowały grunt pod wybuch I wojny światowej.', 'aspekty: polityczny, militarny i narodowościowy.'),
    (XX, 'Powstanie państwa Izrael w 1948 roku zapoczątkowało trwały konflikt na Bliskim Wschodzie.', 'aspekty: polityczny, militarny i religijny.'),
    (XX, 'Hiszpańska wojna domowa była próbą generalną przed II wojną światową.', 'aspekty: militarny, polityczny i międzynarodowy.'),
]

# Generated topics dropped after the near-duplicate check against the eval set (see sim report).
DROP_GENERATED = set()


# ---------- similarity vs eval topics (char 3-5 gram tf-idf cosine on the thesis) ----------
def thesis(t):
    return re.split(r'\s*Zajmij stanowisko', t)[0].lower()


def grams(s):
    s = re.sub(r'[^0-9a-ząćęłńóśźż ]', ' ', s)
    s = ' ' + re.sub(r'\s+', ' ', s).strip() + ' '
    return Counter(s[i:i + n] for n in (3, 4, 5) for i in range(len(s) - n + 1))


def eval_topics():
    out = []
    for line in open(os.path.join(ROOT, 'devset', 'cke-essays.jsonl'), encoding='utf-8'):
        r = json.loads(line)
        if r['id'] in EVAL_IDS:
            out += [(f'{r["id"]}#{t["n"]}', t['text']) for t in r['topics']]
    return out


def sim_index(docs):
    df = Counter()
    vecs = [grams(d) for d in docs]
    for v in vecs:
        df.update(v.keys())
    n = len(vecs)

    def vec(c):
        w = {g: c[g] * math.log((n + 1) / (df.get(g, 0) + 1)) for g in c}
        norm = math.sqrt(sum(x * x for x in w.values())) or 1.0
        return {g: x / norm for g, x in w.items()}
    return vec


def main():
    old = load_cke_old()
    ev = eval_topics()
    assert len(ev) == 36, len(ev)
    gen_rows, era_ct = [], Counter()
    for i, (era, th, frame) in enumerate(GENERATED, 1):
        gid = f'gen-{i:03d}'
        if gid in DROP_GENERATED:
            continue
        lead = Z_SHORT if i % 5 == 0 else (Z_NOUZ if i % 11 == 0 else Z)
        row = {'id': gid, 'source': 'generated', 'topic': f'{th} {lead}{frame}', 'era': era}
        rel = [v for k, v in EVAL_RELATED_GEN.items() if th.startswith(k)]
        if rel:
            row['eval_related'] = rel[0]
        gen_rows.append(row)
    assert sum('eval_related' in r for r in gen_rows) == len(EVAL_RELATED_GEN)
    rows = []
    for r in old:
        paper, n = r['id'][4:].rsplit('-t', 1)
        r2 = {'id': r['id'], 'source': 'cke_old', 'topic': r['topic'], 'era': OLD_ERA[paper][int(n) - 1],
              'paper': paper, 'needs_materials': r['needs_materials']}
        if r['id'] in OLD_NEAR_EVAL:
            r2['near_eval'] = OLD_NEAR_EVAL[r['id']]
        if r['id'] in EVAL_RELATED:
            r2['eval_related'] = EVAL_RELATED[r['id']]
        rows.append(r2)
    rows += gen_rows

    # similarity report
    corpus = [thesis(t) for _, t in ev] + [thesis(r['topic']) for r in rows]
    vec = sim_index(corpus)
    evv = [(eid, vec(grams(thesis(t)))) for eid, t in ev]
    report = []
    for r in rows:
        v = vec(grams(thesis(r['topic'])))
        best = max(((sum(v.get(g, 0) * x for g, x in ev_v.items()), eid) for eid, ev_v in evv))
        r['_sim'] = round(best[0], 3)
        report.append((best[0], r['id'], best[1], thesis(r['topic'])[:110]))
    for r in rows:
        r['max_sim_eval'] = r.pop('_sim')
    # never emit an eval topic verbatim
    evset = {re.sub(r'\W', '', t.lower()) for _, t in ev}
    assert not any(re.sub(r'\W', '', r['topic'].lower()) in evset for r in rows)

    out = os.path.join(HERE, 'topics.jsonl')
    with open(out, 'w', encoding='utf-8', newline='\n') as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + '\n')
    ct = Counter((r['source'], r['era']) for r in rows)
    print('wrote', out, len(rows))
    for k in sorted(ct):
        print(k, ct[k])
    print('near_eval', sum('near_eval' in r for r in rows), 'eval_related',
          Counter(r['source'] for r in rows if 'eval_related' in r))
    if '--sim' in sys.argv:
        for s, rid, eid, th in sorted(report, reverse=True)[:30]:
            print(f'{s:.3f} {rid} ~ {eid} | {th}')


if __name__ == '__main__':
    main()
