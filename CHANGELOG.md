# Changelog

## 0.0 — Start projektu
- Inicjalizacja repozytorium

## 0.1 — Pierwsze scrapery
- Scraper centrumrowerowe.pl (Playwright + BeautifulSoup)
- Scraper bike-discount.de (Playwright + BeautifulSoup)
- Podstawowy README

## 0.2 — Wczesne eksperymenty
- Drobne poprawki kodu i notebooków
- Zmiany w przetwarzaniu DataFrame

## 0.3 — Aplikacja Streamlit + AI matcher
- Pierwszy frontend w Streamlit
- Dopasowywanie produktów CR↔BD przez Claude AI
- Poprawa jakości danych

## 0.4 — Deployment na Streamlit Cloud
- Ustalenie Python 3.12 jako wymaganej wersji
- Konfiguracja `requirements.txt` (bez `uv.lock`)
- Pierwsze działające wdrożenie na Streamlit Community Cloud

## 0.5 — Fix dopasowań zawieszenia
- Dodanie pre-filtra po grade'zie zawieszenia (FOX Factory/Performance/Rhythm, RockShox Ultimate/Select+/Select/R)
- Eliminacja fałszywych dopasowań między różnymi grade'ami

## 0.6 — Wyświetlanie wszystkich produktów
- Domyślne wyświetlanie pełnego katalogu (bez przymusu ustawiania filtra min. oszczędności)

## 0.7 — Fix linków do CR (noreferrer)
- Zamiana `st.dataframe` z `LinkColumn` na tabelę HTML
- Linki z `rel="noreferrer noopener"` — centrumrowerowe.pl blokował ruch z referrerem streamlit.app

## 0.8 — Buycoffee.to banner
- Dodanie przycisku „Postaw kawę" (buycoffee.to/icearas) w sidebarze i na stronie głównej

## 0.9 — UI: wyszukiwarka i porządki
- Przeniesienie pola wyszukiwania z sidebara na stronę główną
- Nowy tytuł aplikacji
- Usunięcie `.env` z trackowania git

## 1.0 — Poprawa matchowania zawieszenia
- Usunięcie błędnych matchów (złe grade'y, części serwisowe)
- Ulepszony pre-filter po grade'zie w `ai_matcher.py`

## 1.1 — Pełny katalog CR jako baza
- Zmiana architektury: baza to wszystkie produkty CR, BD match jako overlay (lewa strona zawsze wypełniona)
- Eksport pełnego katalogu CR do `data/cr_all.csv`

## 1.2 — Trzeci sklep: rowerowy.com
- Scraper rowerowy.com (Playwright)
- Matcher CR↔RW (`rw_matcher.py`) zapisujący wyniki do `data/rw_matched.csv`
- Integracja trzeciej kolumny w tabeli Streamlit

## 1.3 — Dev Container
- Dodanie konfiguracji Dev Container (`.devcontainer/`)

## 1.4 — Poprawki UI
- Usunięcie metryk z widoku głównego
- Fix nagłówków tabeli w dark mode
- Padding poziomy tabeli

## 1.5 — Filtr marek
- Zastąpienie filtrów cenowych z sidebara multiselectem marki (Shimano, SRAM, RockShox, FOX)

## 1.6 — Kurs EUR/PLN z API NBP
- Automatyczne pobieranie kursu EUR/PLN z api.nbp.pl (tabela A, odświeżanie co 1h)
- Możliwość ręcznego nadpisania kursu w sidebarze

## 1.7 — Link do Allegro + schemat bazy danych
- Kolumna „Link AL" — link do wyników wyszukiwania na Allegro (sortowanie: cena rosnąco, tylko nowe)
- Ekstrakcja numeru modelu z nazwy produktu (regex) do zapytania Allegro
- `DATABASE.md` — projekt schematu PostgreSQL (`canonical_products`, `shop_listings`, `price_history`)

## 1.8 — Atrybucja „made by icearas"
- Dodanie podpisu w stopce tabeli z linkiem do buycoffee.to/icearas

## 1.9 — Zastąpienie rowerowy.com przez mtbiker.pl
- Nowy scraper mtbiker.pl (Playwright, paginacja URL `/page-{n}/`, filtrowanie po marce w kodzie)
- Nowy matcher `mtb_matcher.py` (CR↔MTB, wyniki w `data/mtb_matched.csv`)
- Fix: `float("nan")` zamiast `None` w fallbacku pandas (unikanie TypeError)
- Dokumentacja: one-linery do scrapowania każdego sklepu z osobna

## 2.0 — Pierwsze dane z mtbiker.pl
- 136 produktów CR, 93 matche CR↔BD, 34 matche CR↔MTB w plikach CSV
- Kolumna MTB (PLN) i oszczędności MTB widoczne na produkcji

## 2.1 — Filtr dostępności w sklepie
- Multiselect „Dostępne w sklepie" w sidebarze (centrumrowerowe.pl, bike-discount.de, mtbiker.pl)
- Filtruje wiersze mające dopasowaną cenę w wybranym sklepie (OR między sklepami)

## 2.2 — Czwarty sklep: bikeinn.com
- Scraper bikeinn.com bez Playwright — bezpośrednie zapytania do Elasticsearch API (`sr.tradeinn.com`)
- 281 produktów: przerzutki, kasety, łańcuchy, hamulce, widelce (RockShox + FOX)
- `bi_matcher.py` — matchuje CR↔BI przez AI, 46 dopasowań, wyniki w `data/bi_matched.csv`
- Kolumna BI (PLN) i oszczędności BI w tabeli; bikeinn.com dodane do filtra sklepów
