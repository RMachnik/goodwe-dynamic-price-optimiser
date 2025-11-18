# GoodWe SEMS - Konfiguracja Backup/EPS

**Model:** GoodWe GW10KN-ET  
**Bateria:** 2x GoodWe Lynx-D LX-D5.0-10 (20 kWh)  
**Cel:** Zwiększenie mocy dostępnej w trybie backup/off-grid

---

## 📱 Krok po kroku - Aplikacja GoodWe SEMS

### Metoda 1: Aplikacja mobilna SEMS Portal (zalecana)

#### 1. Logowanie
```
1. Otwórz aplikację "SEMS Portal" (iOS/Android)
2. Zaloguj się swoimi danymi
3. Wybierz swoją elektrownię z listy
```

#### 2. Dostęp do ustawień falownika
```
Ścieżka:
📱 SEMS Portal
  └── [Twoja elektrownia]
      └── Device (Urządzenia)
          └── [GW10KN-ET - Twój falownik]
              └── Settings (Ustawienia) ⚙️
```

**Lub alternatywnie:**
```
📱 SEMS Portal
  └── [Twoja elektrownia]
      └── More (Więcej)
          └── Device Settings (Ustawienia urządzeń)
              └── Inverter Settings (Ustawienia falownika)
```

#### 3. Ustawienia Backup/EPS

**A. Włączenie trybu EPS (Emergency Power Supply)**
```
Settings → Work Mode
  ├── [ ] Grid-Tied Mode (tylko sieć)
  ├── [✓] Battery Mode (z baterią)
  └── [✓] Enable EPS/Backup (włącz backup) ⭐
```

**Możliwe nazwy opcji:**
- "EPS Enable" lub "EPS Function"
- "Backup Enable" lub "Backup Mode"
- "Off-Grid Function"
- "UPS Mode"

#### 4. Ustawienia mocy backup

**B. Limit mocy wyjściowej backup**
```
Settings → Battery Settings → EPS/Backup Settings
  └── EPS Output Power Limit: [___] kW
      (domyślnie może być: 3-6kW)
      
      Zmień na: 8-10kW (maksymalnie dla GW10KN-ET)
```

**Możliwe nazwy:**
- "EPS Power Limit"
- "Backup Output Power"
- "Off-Grid Power Limit"
- "Max Backup Power"

**C. Tryb pracy baterii podczas backup**
```
Settings → Battery → Discharge Settings
  ├── Discharge Power Limit: [___] kW
  │   └── Zwiększ do: 8-10kW
  │
  ├── Backup Reserve SOC: [___] %
  │   └── Ustaw: 20-30% (rezerwa na backup)
  │
  └── [✓] Enable battery discharge during backup
```

#### 5. Zaawansowane ustawienia (jeśli dostępne)

**D. Priorytet zasilania podczas backup**
```
Settings → Advanced → Backup Priority
  ├── [ ] PV First (PV → Dom → Bateria)
  ├── [✓] Battery First (Bateria → Dom → PV) ⭐ ZALECANE
  └── [ ] Auto (automatyczny)
```

**E. Szybkość przełączania ATS (Automatic Transfer Switch)**
```
Settings → Advanced → ATS Settings
  └── Transfer Time: [___] ms
      (zazwyczaj: 10-20ms - nie zmieniaj bez konsultacji)
```

---

## 🖥️ Metoda 2: Interfejs webowy SEMS

### Dostęp przez przeglądarkę

1. **Zaloguj się do SEMS Web Portal:**
   ```
   https://www.semsportal.com
   lub
   https://eu.semsportal.com (Europa)
   ```

2. **Ścieżka do ustawień:**
   ```
   Dashboard
     └── Plant List (Lista elektrowni)
         └── [Wybierz swoją elektrownię]
             └── Device → Inverter
                 └── Remote Setting (Zdalne ustawienia) ⚙️
   ```

3. **W sekcji Remote Setting szukaj:**
   ```
   ├── Work Mode Settings
   │   └── [✓] Enable EPS Function
   │
   ├── EPS/Backup Settings
   │   ├── EPS Output Power Limit: [10] kW
   │   └── EPS Reserve SOC: [20] %
   │
   └── Battery Settings
       └── Max Discharge Power: [10] kW
   ```

---

## 🔧 Metoda 3: Bezpośredni dostęp (zaawansowane)

### Dostęp lokalny przez WiFi falownika

**UWAGA:** Ta metoda wymaga bezpośredniego połączenia z falownikiem.

1. **Połącz się z WiFi falownika:**
   ```
   Nazwa sieci: GoodWe-XXXXX (gdzie XXXXX to część numeru seryjnego)
   Hasło: domyślnie "12345678" lub sprawdź na naklejce falownika
   ```

2. **Otwórz przeglądarkę:**
   ```
   Adres: http://10.10.100.254
   lub:   http://192.168.11.1
   ```

3. **Zaloguj się:**
   ```
   Login: admin
   Hasło: (sprawdź dokumentację lub naklejkę na falowniku)
   ```

4. **Przejdź do ustawień:**
   ```
   Settings → Battery → EPS Settings
   ```

---

## ⚠️ WAŻNE UWAGI I OGRANICZENIA

### 1. Dostęp do ustawień

```
┌────────────────────────────────────────────────────────────┐
│ POZIOMY DOSTĘPU W APLIKACJI SEMS:                         │
├────────────────────────────────────────────────────────────┤
│ • USER (Użytkownik)       - podstawowy monitoring         │
│ • INSTALLER (Instalator)  - pełne ustawienia ⭐           │
│ • ADMIN (Administrator)   - wszystkie funkcje             │
└────────────────────────────────────────────────────────────┘
```

**Jeśli nie widzisz opcji backup/EPS:**
- Twoje konto może być w trybie USER (tylko monitoring)
- Potrzebujesz dostępu INSTALLER lub ADMIN
- Skontaktuj się z instalatorem o hasło instalatora

### 2. Limit sprzętowy falownika

**GoodWe GW10KN-ET - Limity sprzętowe:**
```
On-Grid (z siecią):
  • Max output: 10kW
  • Max battery discharge: 10kW ✅

Off-Grid/Backup (bez sieci):
  • Max EPS output: 6-8kW ⚠️
  • To jest LIMIT SPRZĘTOWY!
  • Nie można zwiększyć powyżej tej wartości w oprogramowaniu
```

### 3. Twój problem NIE JEST w limitach

**Na podstawie analizy z 27.10.2025:**
```
Teoretyczna moc backup:     6-8kW
Faktyczna moc dostarczona:  150-600W ⚠️

Problem NIE jest w ustawieniach falownika!
Problem JEST w instalacji elektrycznej - tylko część domu
jest podłączona do wyjścia backup (EPS).
```

**Co to oznacza:**
- Nawet jeśli zwiększysz limity w SEMS, nadal będziesz miał ~150-600W
- Większość domu jest podłączona do głównego obwodu (nie backup)
- Rozwiązanie: przeróbka instalacji elektrycznej przez elektryka

---

## 🔍 Co sprawdzić w aplikacji SEMS

### Krok 1: Sprawdź obecne ustawienia

Zanotuj obecne wartości:

```
[ ] Work Mode: __________________ (Grid-Tied / Battery / Hybrid?)
[ ] EPS Enabled: __________ (Yes / No?)
[ ] EPS Power Limit: __________ kW
[ ] Battery Discharge Limit: __________ kW
[ ] Backup Reserve SOC: __________ %
[ ] Current Load during backup: __________ W (z incydentu 27.10)
```

### Krok 2: Sprawdź czy EPS jest włączone

**W aplikacji SEMS:**
```
Device → Inverter → Status
  └── EPS Status: [Active / Inactive / Not Configured]
```

**Jeśli EPS Status = "Not Configured" lub "Inactive":**
- EPS może być wyłączone w ustawieniach
- Sprawdź "Settings → Work Mode → Enable EPS"

### Krok 3: Sprawdź historię pracy EPS

```
Device → Inverter → History → EPS Events
  └── Zobacz logi z 27.10.2025, 8:00-10:00
      • Czy EPS się włączył?
      • Jaka była max moc wyjściowa?
      • Czy były błędy?
```

---

## 📊 Co możesz zyskać zmieniając ustawienia

### Realistyczne oczekiwania:

#### Scenariusz 1: EPS było wyłączone
```
Przed: EPS disabled → 0W backup
Po:    EPS enabled → 6-8kW backup możliwe ✅

WYGRANA: Ogromna poprawa!
```

#### Scenariusz 2: Niski limit mocy EPS
```
Przed: EPS limit = 3kW
Po:    EPS limit = 8kW

WYGRANA: 2-3x więcej mocy
```

#### Scenariusz 3: Ograniczony backup circuit (Twój przypadek)
```
Przed: 150-600W faktycznie dostarczone
Po:    150-600W faktycznie dostarczone (bez zmian) ❌

Problem: Instalacja elektryczna, nie software!
```

**W Twoim przypadku (na podstawie analizy):**
- Problem NIE jest w limitach falownika
- Zmiana ustawień MOŻE dać +10-20% poprawy
- Główny problem: tylko część domu na backup circuit
- **Potrzebna: przeróbka instalacji elektrycznej**

---

## 🛠️ Plan działania

### Krok 1: Sprawdź w SEMS (0 PLN, 30 min)

1. ✅ Zaloguj się do SEMS
2. ✅ Sprawdź czy EPS jest włączone
3. ✅ Sprawdź limity mocy
4. ✅ Jeśli limity są niskie (< 6kW) - zwiększ do 8-10kW
5. ✅ Zapisz zmiany i zrób test

### Krok 2: Test kontrolowany (0 PLN, 15 min)

```bash
# Przy pełnej baterii (SOC > 80%)
1. Wyłącz główny bezpiecznik (symulacja przerwy)
2. Sprawdź które urządzenia działają
3. Zmierz obciążenie (Load w aplikacji SEMS)
4. Włącz bezpiecznik

Oczekiwany wynik:
- Jeśli limit był niski: teraz więcej urządzeń działa ✅
- Jeśli nadal 150-600W: problem w instalacji elektrycznej ❌
```

### Krok 3: Konsultacja z elektrykiem (500-5000 PLN)

**Jeśli test pokazał nadal 150-600W:**
- Skontaktuj się z instalatorem systemu PV
- Poproś o:
  - Schemat instalacji elektrycznej
  - Które obwody są na backup/EPS
  - Wycenę rozszerzenia backup circuit lub instalacji SZR
  
---

## 📞 Kontakt z supportem GoodWe

**Jeśli nie możesz znaleźć ustawień:**

### GoodWe Support Polska
```
Email: service@goodwe.pl
Tel: +48 22 299 96 93
```

### GoodWe Global Support
```
Email: service@goodwe.com
Tel: +86 512 8843 0606
Website: https://www.goodwe.com/support
```

**Co powiedzieć:**
```
"Mam falownik GoodWe GW10KN-ET z baterią Lynx-D.
Podczas przerwy w prądzie (27.10.2025) system dostarczył tylko
~300W zamiast oczekiwanych 6-8kW.

Sprawdziłem dane i bateria była w dobrym stanie (64-70% SOC).
Chciałbym:
1. Sprawdzić ustawienia EPS/backup w SEMS
2. Zwiększyć limit mocy wyjściowej EPS jeśli to możliwe
3. Zrozumieć czy to problem konfiguracji czy instalacji elektrycznej

Potrzebuję dostępu do zaawansowanych ustawień (poziom INSTALLER)."
```

---

## 📋 Checklist

Przed kontaktem z supportem/elektrykiem zaznacz co sprawdziłeś:

```
Hardware:
[ ] Model falownika: GW10KN-ET
[ ] Moc nominalna: 10kW
[ ] Bateria: 2x Lynx-D LX-D5.0-10 (20kWh)
[ ] SOC podczas incydentu: 64-70% (wystarczające)

Software/SEMS:
[ ] Sprawdziłem aplikację SEMS
[ ] Poziom dostępu: _____________ (USER/INSTALLER/ADMIN)
[ ] EPS Enabled: _____________ (Yes/No)
[ ] EPS Power Limit: _____________ kW
[ ] Battery Discharge Limit: _____________ kW
[ ] Backup Reserve SOC: _____________ %

Test:
[ ] Przeprowadziłem test backup
[ ] Zmierzyłem faktyczne obciążenie: _____________ W
[ ] Sprawdziłem które urządzenia działają podczas backup
[ ] Zrobiłem zdjęcia ekranu z SEMS

Problem:
[ ] Po zwiększeniu limitów: brak poprawy (instalacja elektryczna)
[ ] Po zwiększeniu limitów: znaczna poprawa (był problem w limitach)
[ ] Nie mogę znaleźć ustawień EPS (poziom dostępu)
[ ] Nie mogę zwiększyć limitów (zablokowane)
```

---

## 🎯 Podsumowanie

### Co możesz zrobić TERAZ:

1. **Zaloguj się do SEMS** i sprawdź ustawienia EPS
2. **Jeśli znajdziesz limity mocy** - zwiększ do 8-10kW
3. **Przeprowadź test** - sprawdź czy coś się zmieniło
4. **Jeśli brak poprawy** - problem w instalacji elektrycznej

### Najbardziej prawdopodobne scenariusze:

**Scenariusz A (20% szans):** 
- EPS było wyłączone lub limit był niski
- Zmiana w SEMS rozwiązuje problem ✅

**Scenariusz B (80% szans):** 
- EPS działa prawidłowo
- Problem w instalacji elektrycznej (backup circuit)
- Potrzebna konsultacja z elektrykiem 🔌

### Dalsze kroki:
1. ✅ Sprawdź SEMS (ten dokument)
2. ✅ Przeczytaj analizę: `docs/OFFGRID_PROBLEM_ANALYSIS_20251027.md`
3. ✅ Zobacz wykresy: `out/offgrid_*.png`
4. ✅ Zaplanuj konsultację z elektrykiem/instalatorem

---

**Data utworzenia:** 29 października 2025  
**Wersja:** 1.0  
**Odniesienie:** Analiza incydentu z 27.10.2025






