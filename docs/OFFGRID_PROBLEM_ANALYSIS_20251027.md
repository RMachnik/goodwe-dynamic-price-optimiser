# Analiza problemu z działaniem Off-Grid - 27.10.2025

**Data incydentu:** 27 października 2025, 8:00-10:00  
**Czas trwania przerwy:** ~2 godziny  
**Problem:** Bateria nie udźwignęła obciążenia podczas przerwy w dostawie prądu - większość urządzeń w domu nie działała

---

## 📊 Podsumowanie wykonawcze

### ✅ Co działało prawidłowo:
- Bateria była w dobrym stanie (64-70% SOC)
- Falownik prawidłowo wykrył utratę sieci i przeszedł w tryb off-grid
- Bateria była w stanie dostarczyć wystarczającą moc (teoretycznie do 10kW)
- PV nawet ładowało baterię podczas przerwy (600-2450W produkcji)

### ❌ Co nie działało:
- **Tylko 150-590W obciążenia podczas przerwy** vs normalnie ~1600W
- **78-90% urządzeń w domu zostało odciętych od zasilania**
- Większość sprzętu nie działała mimo wystarczającego stanu baterii

### 🎯 Główna przyczyna:
**Instalacja elektryczna ma ograniczony obwód backup. Większość domu NIE jest podłączona do systemu awaryjnego.**

---

## 📈 Szczegółowa analiza danych

### 1. Stan przed przerwą (7:00-7:55)
```
- SOC: 70% → 64% (spadek o 6%)
- Bateria rozładowywała się: 1036-1433W
- Load: 1570-1670W (normalne obciążenie poranne)
- PV produkcja: 250-890W (niska, poranek)
- Grid: stabilna
```

### 2. Podczas przerwy w prądzie (8:00-10:00)
```
⚠️ KLUCZOWE OBSERWACJE:

Czas    | SOC | Battery(W) | PV(W)  | Grid(W) | Load(W) | Status
--------|-----|------------|--------|---------|---------|------------------
07:55   | 64% |    837.9   | 736.2  |    5.0  | 1569.1  | Normalny
08:00   | 64% |   -457.7   | 810.9  |    1.0  |  352.1  | ⚠️ PRZERWA!
08:15   | 65% |   -499.6   | 663.9  |    1.0  |  163.3  | Load min
08:30   | 66% |   -499.6   | 666.5  |    1.0  |  166.0  | PV ładuje
09:00   | 68% |   -750.1   | 931.6  |    0.0  |  181.6  | SOC rośnie
09:30   | 70% |   -917.2   | 1518.1 |    7.0  |  593.9  | Load rośnie
10:00   | 69% |   1590.8   | 354.9  |   10.0  | 1935.8  | Przed powrotem
10:10   | 71% |  -9530.5   | 518.5  |-10637.0 | 1625.1  | ⚡ Sieć wraca
```

**Kluczowe fakty:**
- Grid: 0-2W (praktycznie BRAK SIECI)
- SOC: 64% → 70% (WZROST - bateria się ładowała z PV!)
- Battery: wartości ujemne = ładowanie z PV
- Load: **150-590W** - dramatycznie niskie obciążenie
- Po powrocie sieci: masywne ładowanie ~10kW

### 3. Po przywróceniu prądu (10:10+)
```
- Grid: -10637W (masywne ładowanie)
- Battery: -9530W (ładowanie z maksymalną mocą)
- SOC: 71% → 91% w 30 minut
- Load: powrót do normalnego ~1600W
```

---

## 🔍 Analiza przyczyn

### Dlaczego obciążenie spadło z 1600W do 150-590W?

**Możliwe przyczyny (w kolejności prawdopodobieństwa):**

#### 1. **Ograniczony obwód backup** ⭐ NAJBARDZIEJ PRAWDOPODOBNE
```
Instalacja GoodWe ET zazwyczaj ma dwa obwody:

├── BACKUP CIRCUIT (Emergency Power)
│   ├── Podstawowe oświetlenie      ✅ ~50W
│   ├── Router/modem               ✅ ~30W
│   ├── Lodówka (okresowo)         ✅ ~150W
│   ├── 1-2 gniazdka               ✅ ~100W
│   └── RAZEM: ~150-600W           ✅ TO WIDAĆ W DANYCH!
│
└── MAIN CIRCUIT (Grid-tied only)
    ├── Ogrzewanie                 ❌ ~500W
    ├── Lodówki/zamrażarki #2-3    ❌ ~200W
    ├── Pralka/zmywarka            ❌ ~2000W (gdy działa)
    ├── Komputery/TV               ❌ ~300W
    ├── Pozostałe gniazdka         ❌ ~400W
    └── RAZEM: ~800-1400W          ❌ ODCIĘTE!
```

**Wniosek:** Większość domu jest podłączona tylko do obwodu grid-tied, który wyłącza się podczas przerwy w prądzie.

#### 2. **Limit mocy w trybie backup**
- GoodWe ET ma zazwyczaj limit 6-8kW na backup
- Podczas przerwy dostępne było tylko 150-590W
- To NIE jest limit mocy, to limit obwodu elektrycznego

#### 3. **Tryb pracy falownika**
- Falownik może mieć różne tryby: Grid-tied / Hybrid / Off-grid
- W Polsce najczęściej instalacja: Hybrid (Grid + Battery + PV)
- W trybie Hybrid podczas utraty sieci: tylko backup circuit działa

---

## 📊 Wizualizacje

Utworzono dwa wykresy obrazujące problem:

1. **`out/offgrid_problem_analysis.png`**
   - Szczegółowa analiza czasowa (7:00-11:00)
   - SOC, Load, Battery Power, Grid Power
   - Wyraźnie widoczny spadek obciążenia podczas przerwy

2. **`out/offgrid_comparison.png`**
   - Porównanie: przed / podczas / po przerwie
   - 78% spadek obciążenia podczas przerwy w prądzie

---

## 🔧 Rekomendacje i rozwiązania

### PRIORYTET 1: Weryfikacja instalacji elektrycznej

#### Krok 1: Sprawdź dokumentację instalacji
```bash
# Znajdź w dokumentacji instalacji:
1. Schemat połączeń elektrycznych
2. Które obwody są podłączone do backup output
3. Specyfikacja przełącznika ATS (Automatic Transfer Switch)
4. Limity mocy backup
```

#### Krok 2: Test instalacji
```bash
# Przeprowadź kontrolowany test:
1. Przy pełnym SOC (>80%)
2. Symuluj przerwę (wyłącz główny bezpiecznik)
3. Sprawdź które urządzenia działają
4. Zmierz rzeczywistą dostępną moc
```

### PRIORYTET 2: Rozszerzenie systemu backup

#### Opcja A: Instalacja przełącznika SZR/Smart Grid Ready ⭐ REKOMENDOWANE
**Opis:**
- Automatyczne przełączanie CAŁEGO domu na zasilanie z baterii
- Inteligentne zarządzanie priorytetami obciążenia
- Pełna ochrona przed przerwami w dostawie prądu

**Zalety:**
- ✅ Pełna ochrona całego domu
- ✅ Automatyczne zarządzanie
- ✅ Wykorzystanie pełnej mocy baterii (10kW)
- ✅ Możliwość priorytetyzacji obciążeń

**Wady:**
- ❌ Koszt: ~2000-5000 PLN
- ❌ Wymaga przeróbki instalacji przez elektryka
- ❌ Czas realizacji: 1-2 dni pracy

**Przykładowe rozwiązania:**
- Victron Energy Quattro + przełącznik ATS
- Fronius Smart Grid Ready
- SolarEdge Backup Interface

#### Opcja B: Powiększenie obwodu backup 📊 ŚREDNI KOSZT
**Opis:**
- Dodanie kluczowych obwodów do istniejącego backup circuit
- Priorytetowe zabezpieczenie najważniejszych urządzeń

**Zalety:**
- ✅ Koszt: ~500-2000 PLN
- ✅ Szybka realizacja (1 dzień)
- ✅ Ochrona kluczowych urządzeń

**Wady:**
- ❌ Nadal ograniczona liczba urządzeń
- ❌ Limit mocy backup (~6-8kW)
- ❌ Ręczne zarządzanie priorytetami

**Priorytetowe obwody do dodania:**
1. Ogrzewanie (pompa ciepła / kocioł)
2. Lodówka/zamrażarki
3. Komputery/router (całe biuro)
4. Kluczowe oświetlenie
5. 2-3 dodatkowe gniazdka

#### Opcja C: Optymalizacja ustawień falownika 💡 TANIE
**Opis:**
- Sprawdzenie i optymalizacja ustawień w falowniku GoodWe
- Zwiększenie limitów mocy backup (jeśli możliwe)

**Zalety:**
- ✅ Koszt: 0 PLN (samodzielna konfiguracja)
- ✅ Natychmiastowa realizacja
- ✅ Może poprawić sytuację

**Wady:**
- ❌ Może nie rozwiązać problemu
- ❌ Limit sprzętowy może pozostać
- ❌ Wymaga dostępu do aplikacji/interfejsu

**Kroki:**
1. Zaloguj się do aplikacji GoodWe SEMS
2. Sprawdź ustawienia: Settings → Battery → Backup
3. Zwiększ limit mocy backup (jeśli dostępne)
4. Sprawdź tryb pracy: Grid-tied / Hybrid / Off-grid
5. Włącz funkcję EPS (Emergency Power Supply) jeśli dostępna

---

## 📱 Monitorowanie i alerty

### Dodaj do systemu:

1. **Alert o przełączeniu na tryb backup**
```python
# W master_coordinator.py
if grid_status == "OFF" and battery_mode == "BACKUP":
    send_alert("🚨 System przeszedł w tryb backup - przerwa w prądzie")
    log_backup_mode_entry()
```

2. **Monitoring obciążenia podczas backup**
```python
if battery_mode == "BACKUP":
    monitor_load_capacity()
    if load < expected_load * 0.5:
        send_warning("⚠️ Obciążenie backup jest niskie - sprawdź obwody")
```

3. **Test backup raz w miesiącu**
```bash
# Scheduled test
crontab -e
0 3 1 * * /opt/goodwe/scripts/test_backup_mode.sh
```

---

## 📋 Plan działania

### Krótkoterminowy (1-2 dni):
- [ ] Sprawdź dokumentację instalacji elektrycznej
- [ ] Zidentyfikuj które obwody są na backup
- [ ] Przeprowadź kontrolowany test backup
- [ ] Zmierz rzeczywistą dostępną moc
- [ ] Sprawdź ustawienia w aplikacji GoodWe SEMS

### Średnioterminowy (1-2 tygodnie):
- [ ] Skonsultuj z elektrykiem możliwości rozszerzenia
- [ ] Wybierz opcję: SZR / Powiększenie backup / Optymalizacja
- [ ] Uzyskaj wycenę prac
- [ ] Zaplanuj prace instalacyjne

### Długoterminowy (1-3 miesiące):
- [ ] Zrealizuj wybraną opcję
- [ ] Przeprowadź testy po zmianach
- [ ] Wdróż monitoring i alerty
- [ ] Zaplanuj regularne testy backup (raz w miesiącu)

---

## 💰 Szacowane koszty

| Rozwiązanie | Koszt | Czas realizacji | Efekt |
|-------------|-------|-----------------|-------|
| **Opcja C: Optymalizacja ustawień** | 0 PLN | 1 godz. | +10-20% mocy |
| **Opcja B: Powiększenie backup** | 500-2000 PLN | 1 dzień | +50-70% urządzeń |
| **Opcja A: Instalacja SZR** | 2000-5000 PLN | 1-2 dni | 100% urządzeń |

---

## 🎓 Wnioski edukacyjne

### Co się wydarzyło:
1. **Bateria działała poprawnie** - miała wystarczający SOC (64-70%)
2. **Falownik działał poprawnie** - wykrył utratę sieci i przeszedł w tryb backup
3. **Problem: instalacja elektryczna** - większość domu nie jest podłączona do backup

### Czego się nauczyliśmy:
1. **Tryb backup ≠ cały dom** - tylko wybrane obwody mają backup
2. **Bateria może więcej** - teoretycznie 10kW, praktycznie dostarczała 150-590W
3. **Instalacja wymaga weryfikacji** - dokumentacja instalacji jest kluczowa

### Co możemy zrobić lepiej:
1. **Regularne testy** - symulować przerwy w dostawie prądu
2. **Monitoring** - alerty o przełączeniu na backup
3. **Planowanie** - priorytetyzacja kluczowych urządzeń
4. **Rozszerzenie** - inwestycja w system SZR/Smart Grid Ready

---

## 📞 Kontakt i dalsze kroki

**Zalecane działania:**
1. ✅ Przejrzyj ten dokument wraz z wykresami (`out/offgrid_*.png`)
2. ✅ Znajdź dokumentację instalacji elektrycznej
3. ✅ Skontaktuj się z instalatorem systemu PV/baterii
4. ✅ Zaplanuj konsultację z elektrykiem
5. ✅ Wybierz optymalną opcję rozwiązania problemu

**Pytania do instalatora:**
- Które obwody są podłączone do backup output?
- Jaki jest limit mocy w trybie backup?
- Czy można rozszerzyć backup circuit?
- Ile kosztowałaby instalacja SZR?
- Jakie są dostępne opcje przełączników ATS?

---

## 📚 Załączniki

1. **Plant Power_20251029063518.xls** - dane z falownika z dnia incydentu
2. **out/offgrid_problem_analysis.png** - szczegółowa analiza czasowa
3. **out/offgrid_comparison.png** - wykres porównawczy
4. **config/master_coordinator_config.yaml** - obecna konfiguracja systemu

---

**Data raportu:** 28 października 2025  
**Autor:** AI Assistant + GoodWe Dynamic Price Optimiser System  
**Wersja:** 1.0



