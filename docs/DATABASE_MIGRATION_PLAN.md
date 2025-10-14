# Plan Optymalizacji: Migracja z Plików na Bazę Danych

## 1. Przygotowanie infrastruktury bazy danych

**Cel**: Utworzenie struktury bazy danych i warstwy abstrakcji

### 1.1 Schemat bazy danych SQLite

- Utworzenie pliku `src/database/schema.py` z definicjami tabel:
- `energy_data` - dane energetyczne (timestamp, battery_soc, pv_power, grid_power, consumption, price)
- `charging_sessions` - sesje ładowania (session_id, start_time, end_time, energy_kwh, cost_pln, status)
- `daily_stats` - statystyki dzienne (date, total_consumption, total_pv, total_grid_import, avg_price)
- `system_state` - stan systemu (timestamp, state, uptime, metrics)
- `battery_selling_sessions` - sesje sprzedaży energii
- `price_forecasts` - prognozy cen
- `coordinator_decisions` - historia decyzji

### 1.2 Warstwa abstrakcji danych

- Utworzenie `src/database/storage_interface.py` - abstrakcyjny interfejs dla różnych typów storage
- Utworzenie `src/database/sqlite_storage.py` - implementacja SQLite
- Utworzenie `src/database/connection_manager.py` - zarządzanie połączeniami z poolingiem
- Indeksy na kolumnach timestamp dla szybkich zapytań czasowych

### 1.3 Aktualizacja requirements.txt

- Dodanie `aiosqlite>=0.19.0` - async SQLite
- Dodanie `sqlalchemy>=2.0.0` - ORM (opcjonalnie dla przyszłej migracji do PostgreSQL)
- Dodanie `alembic>=1.12.0` - migracje bazy danych

## 2. Implementacja narzędzia migracji danych

**Cel**: Przeniesienie istniejących danych z JSON do bazy

### 2.1 Skrypt migracji

- Utworzenie `scripts/migrate_json_to_db.py`:
- Skanowanie katalogów `out/`, `out/energy_data/`, `out/battery_selling_analytics/`
- Parsowanie plików JSON (coordinator_state_*.json, charging_schedule_*.json, session_records.json, daily_summaries.json)
- Import danych do odpowiednich tabel z walidacją
- Raportowanie postępu i błędów
- Opcja dry-run do testowania

### 2.2 Walidacja migracji

- Porównanie liczby rekordów przed i po migracji
- Weryfikacja integralności danych
- Generowanie raportu migracji

## 3. Refaktoryzacja komponentów na bazę danych

**Cel**: Zamiana operacji na plikach na operacje bazodanowe

### 3.1 EnhancedDataCollector (`src/enhanced_data_collector.py`)

- Zamiana `save_data_to_file()` na `save_data_to_db()`
- Usunięcie zapisu do JSON (linie ~383-406)
- Dodanie async zapisów do tabeli `energy_data`
- Batch insert co 10 pomiarów dla wydajności
- Zachowanie metody `get_current_data()` z cache w pamięci

### 3.2 MasterCoordinator (`src/master_coordinator.py`)

- Zamiana `_save_system_state()` (linie ~1004-1025) na zapis do tabeli `system_state`
- Zamiana `_save_decision_to_file()` (linie ~572-640) na zapis do tabeli `coordinator_decisions`
- Usunięcie tworzenia plików coordinator_state_*.json
- Dodanie metody `get_state_history()` z zapytaniami SQL

### 3.3 BatterySellingAnalytics (`src/battery_selling_analytics.py`)

- Zamiana `_save_data()` (linie ~150-169) na zapisy do tabel
- Zamiana `_load_historical_data()` (linie ~100-148) na zapytania SQL
- Usunięcie operacji na plikach session_records.json, daily_summaries.json, monthly_reports.json
- Agregacje miesięczne przez SQL GROUP BY

### 3.4 MultiSessionManager (`src/multi_session_manager.py`)

- Zamiana `_save_daily_plan()` (linie ~312-335) na zapis do tabeli `charging_sessions`
- Zamiana `_load_daily_plan()` (linie ~337-371) na zapytanie SQL
- Usunięcie plików daily_plan_*.json

### 3.5 HybridChargingLogic (`src/hybrid_charging_logic.py`)

- Zamiana zapisów decyzji na operacje bazodanowe
- Optymalizacja zapytań o historię decyzji

### 3.6 PVForecaster (`src/pv_forecasting.py`)

- Zamiana zapisów prognoz na tabelę `pv_forecasts`
- Szybkie zapytania o prognozy z indeksami

## 4. Optymalizacja wydajności

**Cel**: Maksymalizacja szybkości i stabilności

### 4.1 Connection pooling

- Implementacja puli połączeń (min 2, max 10 połączeń)
- Automatyczne zamykanie nieużywanych połączeń
- Retry logic przy błędach połączenia

### 4.2 Batch operations

- Grupowanie zapisów (batch insert co 10-50 rekordów)
- Async/await dla nieblokujących operacji I/O
- Transakcje dla spójności danych

### 4.3 Indeksy i optymalizacja zapytań

- Indeksy na timestamp, session_id, date
- EXPLAIN QUERY PLAN dla krytycznych zapytań
- Vacuum i ANALYZE dla utrzymania wydajności

### 4.4 Cache w pamięci

- Redis-like cache dla najczęściej używanych danych (current_data, latest_price)
- TTL 60s dla danych real-time
- Invalidacja cache przy zapisie

## 5. Aktualizacja konfiguracji

**Cel**: Przełączenie na bazę danych w konfiguracji

### 5.1 master_coordinator_config.yaml

- Zmiana `data_storage.file_storage.enabled: false`
- Zmiana `data_storage.database_storage.enabled: true`
- Dodanie ścieżki do bazy SQLite: `/opt/goodwe-dynamic-price-optimiser/data/goodwe_energy.db`
- Konfiguracja retention (auto-delete danych starszych niż 30 dni)

### 5.2 Zmienne środowiskowe

- Opcjonalne `DATABASE_PATH` dla łatwej zmiany lokalizacji
- `DATABASE_POOL_SIZE` dla tuningu wydajności

## 6. Docker i deployment

**Cel**: Wsparcie dla obu środowisk (Docker + bare metal)

### 6.1 Dockerfile

- Utworzenie katalogu `/data` w kontenerze dla bazy
- Volume mount dla persistencji: `-v ./data:/opt/goodwe-dynamic-price-optimiser/data`
- Inicjalizacja bazy przy pierwszym uruchomieniu

### 6.2 docker-compose.yml

- Dodanie volume dla bazy danych
- Health check sprawdzający dostępność bazy
- Backup volume dla automatycznych kopii

### 6.3 Bare metal (Ubuntu Server)

- Utworzenie katalogu `/opt/goodwe-dynamic-price-optimiser/data`
- Uprawnienia dla użytkownika systemd
- Automatyczna inicjalizacja przy instalacji

## 7. Testy i walidacja

**Cel**: Zapewnienie poprawności i wydajności

### 7.1 Testy jednostkowe

- `test/test_database_storage.py` - testy warstwy storage
- `test/test_migration.py` - testy migracji danych
- Testy wydajnościowe (insert 1000 rekordów < 1s)

### 7.2 Testy integracyjne

- Test pełnego cyklu: collect → store → retrieve → analyze
- Test równoległego dostępu (multi-threading)
- Test recovery po błędzie połączenia

### 7.3 Benchmarki

- Porównanie czasu zapisu: JSON vs SQLite
- Porównanie czasu odczytu: skanowanie plików vs SELECT
- Pomiar zużycia pamięci

## 8. Dokumentacja i cleanup

**Cel**: Aktualizacja dokumentacji i usunięcie starych plików

### 8.1 Aktualizacja README.md

- Sekcja o bazie danych
- Instrukcje migracji z plików
- Troubleshooting dla problemów z bazą

### 8.2 Nowa dokumentacja

- `docs/DATABASE_ARCHITECTURE.md` - architektura bazy
- `docs/MIGRATION_GUIDE.md` - przewodnik migracji
- Diagramy schematu bazy

### 8.3 Cleanup

- Usunięcie starych plików JSON z `out/` po udanej migracji (opcjonalne, przez skrypt)
- Archiwizacja jako backup w `out/archive/`

## 9. Opcjonalna rozbudowa (Faza 2)

**Przygotowanie do przyszłej migracji na TimescaleDB/PostgreSQL**

### 9.1 Abstrakcja umożliwiająca łatwą zmianę

- Interfejs `StorageInterface` już wspiera różne backendy
- Utworzenie `src/database/timescaledb_storage.py` (szkielet)
- Konfiguracja hybrydowa: SQLite dla sesji, TimescaleDB dla time-series

### 9.2 Monitoring i metryki

- Grafana dashboard dla metryk bazy (opcjonalnie)
- Alerty przy problemach z wydajnością

---

## Korzyści z migracji

✅ **Wydajność**: 10-100x szybsze zapytania dzięki indeksom  
✅ **Stabilność**: Transakcje ACID, brak race conditions  
✅ **Skalowalność**: Łatwa migracja do PostgreSQL/TimescaleDB  
✅ **Mniej I/O**: Batch operations zamiast tysięcy małych plików  
✅ **Łatwiejsze zapytania**: SQL zamiast parsowania JSON  
✅ **Atomowość**: Brak częściowych zapisów przy crashu  
✅ **Backup**: Pojedynczy plik bazy zamiast tysięcy JSON-ów

## Szacowany czas implementacji

- Faza 1-3: ~8-12 godzin (infrastruktura + migracja + refaktoryzacja)
- Faza 4-6: ~4-6 godzin (optymalizacja + konfiguracja + deployment)
- Faza 7-8: ~3-4 godziny (testy + dokumentacja)
- **Łącznie**: ~15-22 godziny pracy

## Ryzyko i mitygacja

⚠️ **Ryzyko**: Utrata danych podczas migracji  
✅ **Mitygacja**: Backup plików JSON przed migracją, dry-run, walidacja

⚠️ **Ryzyko**: Problemy z wydajnością SQLite przy dużym obciążeniu  
✅ **Mitygacja**: Connection pooling, batch operations, indeksy, przygotowanie do migracji na PostgreSQL

⚠️ **Ryzyko**: Kompatybilność wstecz  
✅ **Mitygacja**: Zachowanie możliwości eksportu do JSON, narzędzie migracji w obie strony

## Lista zadań

1. Utworzenie struktury bazy danych (schema.py, storage_interface.py, sqlite_storage.py, connection_manager.py) i aktualizacja requirements.txt
2. Implementacja narzędzia migracji (migrate_json_to_db.py) do przeniesienia istniejących danych JSON do bazy SQLite
3. Refaktoryzacja EnhancedDataCollector - zamiana save_data_to_file() na async operacje bazodanowe z batch insert
4. Refaktoryzacja MasterCoordinator - zamiana _save_system_state() i _save_decision_to_file() na zapisy do bazy
5. Refaktoryzacja BatterySellingAnalytics i MultiSessionManager - zamiana operacji na plikach JSON na zapytania SQL
6. Refaktoryzacja HybridChargingLogic i PVForecaster - migracja zapisów na operacje bazodanowe
7. Implementacja connection pooling, batch operations, indeksów i cache w pamięci dla maksymalnej wydajności
8. Aktualizacja master_coordinator_config.yaml - przełączenie na database_storage i konfiguracja ścieżek
9. Aktualizacja Dockerfile i docker-compose.yml - dodanie volume dla bazy, health checks i inicjalizacji
10. Utworzenie testów jednostkowych i integracyjnych (test_database_storage.py, test_migration.py) oraz benchmarków wydajności
11. Aktualizacja README.md i utworzenie nowej dokumentacji (DATABASE_ARCHITECTURE.md, MIGRATION_GUIDE.md)

