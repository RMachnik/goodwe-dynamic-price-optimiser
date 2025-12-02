# Plan Optymalizacji: Migracja z Plików na Bazę Danych
## Enhanced Database Migration Plan - Complete System Analysis

**Document Version**: 2.2  
**Updated**: 2025-12-02  
**Status**: Phase 2 Complete - Component Integration Done  

---

## Implementation Progress

### ✅ Phase 1: Core Infrastructure (COMPLETE)

| Task | Status | Notes |
|------|--------|-------|
| Database schema (`src/database/schema.py`) | ✅ Complete | 8 tables: energy_data, system_state, coordinator_decisions, charging_sessions, battery_selling_sessions, weather_data, price_forecasts, pv_forecasts |
| Storage interface (`src/database/storage_interface.py`) | ✅ Complete | Abstract base class with async methods |
| SQLite storage (`src/database/sqlite_storage.py`) | ✅ Complete | Full implementation with all save/get methods |
| File storage (`src/database/file_storage.py`) | ✅ Complete | Legacy file-based storage wrapper |
| Composite storage (`src/database/composite_storage.py`) | ✅ Complete | Writes to both SQLite and files for safety |
| Storage factory (`src/database/storage_factory.py`) | ✅ Complete | Creates storage based on config (file_only/db_only/composite) |
| Dict config support in core classes | ✅ Complete | AutomatedPriceCharger, GoodWeFastCharger, EnhancedDataCollector |
| LogWebServer StorageFactory integration | ✅ Complete | Uses StorageFactory for data access |
| Test suite passing | ✅ Complete | 627 passed, 10 skipped (expected async DB tests) |

### ✅ Phase 2: Component Migration (COMPLETE)

| Task | Status | Notes |
|------|--------|-------|
| EnhancedDataCollector DB writes | ✅ Complete | Added `_flatten_data_for_storage()` to convert nested data to DB schema |
| MasterCoordinator DB writes | ✅ Complete | Already had storage integration, now passes storage to MultiSessionManager |
| BatterySellingEngine | ✅ Complete | Uses file-based daily tracking (isolated data, low-priority) |
| MultiSessionManager migration | ✅ Complete | Storage parameter in constructor, `_save_daily_plan()` and `_load_daily_plan()` use storage with file fallback |

### ⬜ Phase 3: API & Optimization (PENDING)

| Task | Status | Notes |
|------|--------|-------|
| LogWebServer SQL queries | ⬜ Pending | Replace JSON reads with SQL |
| Connection pooling | ⬜ Pending | Performance optimization |
| Batch operations | ⬜ Pending | Grouped inserts |
| Query optimization | ⬜ Pending | Indexes and EXPLAIN analysis |

---

## 1. Przygotowanie infrastruktury bazy danych

**Cel**: Utworzenie struktury bazy danych i warstwy abstrakcji

### 1.1 Rozszerzony schemat bazy danych SQLite

- Utworzenie pliku `src/database/schema.py` z definicjami tabel:

**Tabele podstawowe:**
- `energy_data` - dane energetyczne (timestamp, battery_soc, pv_power, grid_power, consumption, price)
- `charging_sessions` - sesje ładowania (session_id, start_time, end_time, energy_kwh, cost_pln, status)
- `daily_stats` - statystyki dzienne (date, total_consumption, total_pv, total_grid_import, avg_price)
- `system_state` - stan systemu (timestamp, state, uptime, metrics)
- `battery_selling_sessions` - sesje sprzedaży energii
- `coordinator_decisions` - historia decyzji

**Tabele dla prognoz i danych zewnętrznych:**
- `weather_data` - dane pogodowe (timestamp, source, temperature, humidity, pressure, wind_speed, wind_direction, precipitation, cloud_cover, solar_irradiance)
- `price_forecasts` - prognozy cen energii (timestamp, forecast_date, hour, price_pln, confidence, source)
- `pv_forecasts` - prognozy produkcji PV (timestamp, forecast_date, hour, predicted_power_w, confidence, weather_conditions)
- `peak_hours_data` - dane o godzinach szczytowych (timestamp, date, peak_hours, recommended_usage, savings_potential)
- `price_window_analysis` - analiza okien cenowych (timestamp, window_start, window_end, price_category, savings_pln)

### 1.2 Warstwa abstrakcji danych

- Utworzenie `src/database/storage_interface.py` - abstrakcyjny interfejs dla różnych typów storage
- Utworzenie `src/database/sqlite_storage.py` - implementacja SQLite
- Utworzenie `src/database/connection_manager.py` - zarządzanie połączeniami z poolingiem
- Indeksy na kolumnach timestamp dla szybkich zapytań czasowych

### 1.3 Aktualizacja requirements.txt

- Dodanie `aiosqlite>=0.19.0` - async SQLite
- Dodanie `sqlalchemy>=2.0.0` - ORM (opcjonalnie dla przyszłej migracji do PostgreSQL)
- Dodanie `alembic>=1.12.0` - migracje bazy danych
- Dodanie `pydantic>=2.0.0` - walidacja danych
- Dodanie `backoff>=2.2.0` - retry logic dla operacji bazodanowych

## 1.4 Composite Storage Architecture (New)

**Cel**: Zapewnienie bezpieczeństwa danych i kompatybilności wstecznej

- **Composite Pattern**: Implementacja `CompositeStorage`, która zapisuje dane jednocześnie do wielu backendów (SQLite + Pliki).
- **Read Fallback Strategy**:
  1. Próba odczytu z SQLite (Primary).
  2. W przypadku błędu lub braku danych -> odczyt z plików JSON (Fallback).
  3. Logowanie ostrzeżenia przy użyciu fallbacku.
- **Korzyści**:
  - Bezpieczeństwo: Awaria bazy nie zatrzymuje systemu.
  - Migracja: Możliwość stopniowego przenoszenia danych.
  - Debugging: Pliki JSON pozostają dostępne do łatwego podglądu.

## 1.5 Storage Factory

- Utworzenie `src/database/storage_factory.py`
- Odpowiedzialność: Tworzenie odpowiedniej instancji storage na podstawie konfiguracji.
- Obsługa trybów:
  - `file_only`: Tylko pliki (Legacy)
  - `db_only`: Tylko baza (Target)
  - `composite`: Baza + Pliki (Transition/Safe Mode)

## 2. Implementacja narzędzia migracji danych

**Cel**: Przeniesienie istniejących danych z JSON do bazy

### 2.1 Rozszerzony skrypt migracji

- Utworzenie `scripts/migrate_json_to_db.py`:
- Skanowanie katalogów `out/`, `out/energy_data/`, `out/battery_selling_analytics/`, `out/multi_session_data/`
- Parsowanie plików JSON:
  - `coordinator_state_*.json` → tabela `system_state`
  - `charging_decision_*.json` → tabela `coordinator_decisions`
  - `charging_schedule_*.json` → tabela `charging_sessions`
  - `battery_selling_decision_*.json` → tabela `battery_selling_sessions`
  - `session_records.json`, `daily_summaries.json`, `monthly_reports.json` → tabele analytics
  - Pliki pogodowe i prognoz → tabele `weather_data`, `price_forecasts`, `pv_forecasts`
- Import danych do odpowiednich tabel z walidacją Pydantic
- Raportowanie postępu i błędów z szczegółowymi logami
- Opcja dry-run do testowania
- **Backup automatyczny** przed migracją
- **Rollback mechanism** w przypadku błędów

### 2.2 Walidacja migracji

- Porównanie liczby rekordów przed i po migracji
- Weryfikacja integralności danych
- Generowanie raportu migracji

## 3. Refaktoryzacja komponentów na bazę danych

**Cel**: Zamiana operacji na plikach na operacje bazodanowe

### 3.1 EnhancedDataCollector (`src/enhanced_data_collector.py`)

- Zamiana `save_data_to_file()` (linie 383-406) na `save_data_to_db()`
- Usunięcie zapisu do JSON
- Dodanie async zapisów do tabeli `energy_data`
- Batch insert co 10 pomiarów dla wydajności
- Zachowanie metody `get_current_data()` z cache w pamięci
- **Error handling** z retry logic dla operacji bazodanowych

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
- **Error handling** dla operacji bazodanowych

### 3.7 WeatherDataCollector (`src/weather_data_collector.py`)

- Zamiana zapisów danych pogodowych na tabelę `weather_data`
- Async zapisy dla IMGW i Open-Meteo danych
- Cache w pamięci dla najnowszych danych

### 3.8 PSEPriceForecastCollector (`src/pse_price_forecast_collector.py`)

- Zamiana zapisów prognoz cen na tabelę `price_forecasts`
- Batch insert dla prognoz 24h
- Walidacja danych przed zapisem

### 3.9 PSEPeakHoursCollector (`src/pse_peak_hours_collector.py`)

- Zamiana zapisów godzin szczytowych na tabelę `peak_hours_data`
- Async zapisy z retry logic
- Cache dla najnowszych danych

### 3.10 LogWebServer (`src/log_web_server.py`)

- **KRYTYCZNE**: Zamiana odczytu z plików JSON na zapytania SQL
- Linie 756-787: `_get_battery_selling_data()` - zamiana na SQL
- Linie 686-750: `_get_system_status()` - zamiana na SQL
- Dodanie endpoint'ów API dla danych z bazy
- **Backward compatibility** - zachowanie istniejących endpoint'ów

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
- **Connection pooling** z retry logic
- **Circuit breaker** dla operacji bazodanowych

## 5. Aktualizacja konfiguracji

**Cel**: Przełączenie na bazę danych w konfiguracji

### 5.1 master_coordinator_config.yaml

- **Fazowe przełączanie**:
  - Faza 1: `data_storage.file_storage.enabled: true`, `data_storage.database_storage.enabled: false`
  - Faza 2: `data_storage.file_storage.enabled: true`, `data_storage.database_storage.enabled: true` (dual mode)
  - Faza 3: `data_storage.file_storage.enabled: false`, `data_storage.database_storage.enabled: true`
- Dodanie ścieżki do bazy SQLite: `/opt/goodwe-dynamic-price-optimiser/data/goodwe_energy.db`
- Konfiguracja retention (auto-delete danych starszych niż 30 dni)
- **Error handling configuration**:
  - `database.retry_attempts: 3`
  - `database.retry_delay_seconds: 5`
  - `database.connection_pool_size: 10`
  - `database.fallback_to_file: true` (during migration)

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
- `test/test_error_handling.py` - testy error handling i rollback
- `test/test_web_server_migration.py` - testy LogWebServer z bazą danych
- Testy wydajnościowe (insert 1000 rekordów < 1s)
- **Testy integracyjne** dla wszystkich komponentów

### 7.2 Testy integracyjne

- Test pełnego cyklu: collect → store → retrieve → analyze
- Test równoległego dostępu (multi-threading)
- Test recovery po błędzie połączenia
- **Test migracji** - pełny cykl migracji z rollback
- **Test backward compatibility** - LogWebServer z nowymi endpoint'ami
- **Test error scenarios** - błędy bazy, network issues, disk full

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

## Szacowany czas implementacji (ZAKTUALIZOWANY)

- **Faza 1-3**: ~12-18 godzin (infrastruktura + migracja + refaktoryzacja + **nowe komponenty**)
- **Faza 4-6**: ~6-8 godzin (optymalizacja + konfiguracja + deployment + **error handling**)
- **Faza 7-8**: ~6-8 godzin (testy + dokumentacja + **testy integracyjne**)
- **Faza 9**: ~4-6 godzin (**LogWebServer migration** + backward compatibility)
- **Łącznie**: ~28-40 godzin pracy (vs. oryginalne 15-22h)

**Dodatkowe komponenty wymagające migracji:**
- WeatherDataCollector: +2-3h
- PSEPriceForecastCollector: +2-3h  
- PSEPeakHoursCollector: +2-3h
- LogWebServer: +4-6h (krytyczne!)
- Error handling & rollback: +3-4h
- Extended testing: +3-4h

## Ryzyko i mitygacja (ZAKTUALIZOWANE)

⚠️ **Ryzyko**: Utrata danych podczas migracji  
✅ **Mitygacja**: **Automatyczny backup** przed migracją, dry-run, walidacja, **rollback mechanism**

⚠️ **Ryzyko**: Problemy z wydajnością SQLite przy dużym obciążeniu  
✅ **Mitygacja**: Connection pooling, batch operations, indeksy, **circuit breaker**, przygotowanie do migracji na PostgreSQL

⚠️ **Ryzyko**: Kompatybilność wstecz  
✅ **Mitygacja**: Zachowanie możliwości eksportu do JSON, narzędzie migracji w obie strony, **fazowe przełączanie**

⚠️ **Ryzyko**: LogWebServer przestanie działać  
✅ **Mitygacja**: **Backward compatibility**, dual mode, **extensive testing**

⚠️ **Ryzyko**: Błędy operacji bazodanowych  
✅ **Mitygacja**: **Retry logic**, **fallback to files**, **error monitoring**

⚠️ **Ryzyko**: Problemy z migracją nowych komponentów  
✅ **Mitygacja**: **Fazowe podejście**, testy każdego komponentu osobno, **rollback per component**

## Lista zadań (ZAKTUALIZOWANA)

### **Faza 1: Infrastruktura (8-12h)**
1. Utworzenie struktury bazy danych (schema.py, storage_interface.py, sqlite_storage.py, connection_manager.py) i aktualizacja requirements.txt
2. **Implementacja error handling i retry logic** w warstwie abstrakcji
3. **Implementacja rollback mechanism** dla migracji
4. Implementacja narzędzia migracji (migrate_json_to_db.py) do przeniesienia istniejących danych JSON do bazy SQLite
5. **Dodanie backup automatycznego** przed migracją

### **Faza 2: Komponenty podstawowe (6-8h)**
6. Refaktoryzacja EnhancedDataCollector - zamiana save_data_to_file() na async operacje bazodanowe z batch insert
7. Refaktoryzacja MasterCoordinator - zamiana _save_system_state() i _save_decision_to_file() na zapisy do bazy
8. Refaktoryzacja BatterySellingAnalytics i MultiSessionManager - zamiana operacji na plikach JSON na zapytania SQL
9. Refaktoryzacja HybridChargingLogic i PVForecaster - migracja zapisów na operacje bazodanowe

### **Faza 3: Komponenty dodatkowe (6-8h)**
10. **Refaktoryzacja WeatherDataCollector** - migracja danych pogodowych na tabelę weather_data
11. **Refaktoryzacja PSEPriceForecastCollector** - migracja prognoz cen na tabelę price_forecasts  
12. **Refaktoryzacja PSEPeakHoursCollector** - migracja danych o godzinach szczytowych
13. **Refaktoryzacja LogWebServer** - zamiana odczytu z JSON na SQL (KRYTYCZNE!)

### **Faza 4: Optymalizacja i konfiguracja (4-6h)**
14. Implementacja connection pooling, batch operations, indeksów i cache w pamięci dla maksymalnej wydajności
15. **Implementacja circuit breaker** dla operacji bazodanowych
16. Aktualizacja master_coordinator_config.yaml - **fazowe przełączanie** na database_storage
17. Aktualizacja Dockerfile i docker-compose.yml - dodanie volume dla bazy, health checks i inicjalizacji

### **Faza 5: Testy i dokumentacja (4-6h)**
18. Utworzenie testów jednostkowych i integracyjnych (test_database_storage.py, test_migration.py, **test_error_handling.py**, **test_web_server_migration.py**)
19. **Testy backward compatibility** dla LogWebServer
20. **Testy rollback mechanism** i error scenarios
21. Aktualizacja README.md i utworzenie nowej dokumentacji (DATABASE_ARCHITECTURE.md, MIGRATION_GUIDE.md)

### **Faza 6: Deployment i monitoring (2-4h)**
22. **Implementacja monitoring** dla operacji bazodanowych
23. **Deployment fazowy** z możliwością rollback
24. **Walidacja produkcyjna** i optymalizacja wydajności

---

## 🎯 **Podsumowanie kluczowych ulepszeń planu**

### **✅ Dodane komponenty:**
- **WeatherDataCollector** - migracja danych pogodowych
- **PSEPriceForecastCollector** - migracja prognoz cen  
- **PSEPeakHoursCollector** - migracja godzin szczytowych
- **LogWebServer** - krytyczna migracja odczytu z JSON na SQL

### **✅ Rozszerzona architektura bazy:**
- **5 nowych tabel** dla prognoz i danych zewnętrznych
- **Error handling** i retry logic w całej warstwie
- **Rollback mechanism** dla bezpiecznej migracji
- **Circuit breaker** dla odporności na błędy

### **✅ Fazowe podejście:**
- **6 faz** zamiast 3 oryginalnych
- **Dual mode** podczas przejścia (JSON + SQL)
- **Backward compatibility** dla LogWebServer
- **Rollback per component** dla bezpieczeństwa

### **✅ Zaktualizowane szacunki:**
- **28-40 godzin** zamiast 15-22h
- **24 zadania** zamiast 11 oryginalnych  
- **6 faz** zamiast 3 oryginalnych
- **Rozszerzone testy** i walidacja

### **🚨 Krytyczne elementy do priorytetyzacji:**
1. **LogWebServer migration** - bez tego dashboard nie będzie działać
2. **Error handling** - bez tego system będzie niestabilny  
3. **Rollback mechanism** - bez tego ryzyko utraty danych
4. **Backward compatibility** - bez tego przerwa w działaniu systemu

**Plan jest teraz kompletny i gotowy do implementacji!** 🚀

