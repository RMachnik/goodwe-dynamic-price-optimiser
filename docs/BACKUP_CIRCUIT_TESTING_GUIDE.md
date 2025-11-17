# Jak sprawdzić obwód backup w instalacji PV

**Cel:** Zidentyfikować które urządzenia/obwody są podłączone do systemu backup (EPS)  
**System:** GoodWe GW10KN-ET + Lynx-D 20kWh  
**Kontekst:** Diagnoza problemu z 27.10.2025 (tylko 150-600W podczas backup)

---

## 🔍 Metody sprawdzenia obwodu backup

### Metoda 1: Fizyczne sprawdzenie instalacji (BEZPIECZNE)
### Metoda 2: Kontrolowany test backup (WYMAGA OSTROŻNOŚCI)
### Metoda 3: Analiza dokumentacji instalacji (NAJPROSTSZE)

---

## 📋 Metoda 1: Fizyczne sprawdzenie instalacji

### Krok 1: Znajdź rozdzielnię główną

**Co szukasz:**
```
Rozdzielnia główna (skrzynka z bezpiecznikami)
├── Główny wyłącznik
├── Szereg bezpieczników/wyłączników (MCB)
├── Oznaczenia obwodów ("kuchnia", "salon", itp.)
└── Dodatkowe elementy dla PV (od instalatora)
```

**Zrób zdjęcia:**
- ✅ Całej rozdzielni (z bliska)
- ✅ Oznaczeń na bezpiecznikach
- ✅ Dodatkowych urządzeń (przekaźniki, przełączniki)

---

### Krok 2: Szukaj oznaczenia "BACKUP" lub "EPS"

**Instalacja z GoodWe ET może mieć:**

#### Wariant A: Dodatkowa mini-rozdzielnia backup
```
┌─────────────────────────────────────────┐
│ ROZDZIELNIA GŁÓWNA                      │
├─────────────────────────────────────────┤
│ [Main] ← Zasilanie z sieci             │
│   ├── [1] Salon                         │
│   ├── [2] Kuchnia                       │
│   ├── [3] Sypialnia                     │
│   ├── [4] Łazienka                      │
│   └── ... pozostałe obwody              │
└─────────────────────────────────────────┘
                ↓
┌─────────────────────────────────────────┐
│ MINI-ROZDZIELNIA BACKUP (osobna)       │
├─────────────────────────────────────────┤
│ [Backup/EPS] ← Zasilanie z falownika   │
│   ├── [B1] Router/Modem                 │
│   ├── [B2] Lodówka                      │
│   ├── [B3] Światło - korytarz          │
│   └── [B4] 1-2 gniazdka                 │
└─────────────────────────────────────────┘
```

**Szukaj:**
- 📦 Dodatkowej małej skrzynki oznaczonej "BACKUP" lub "EPS"
- 🔌 Kabla idącego od falownika do tej skrzynki
- 📝 Naklejek "ZASILANIE AWARYJNE" lub "CRITICAL LOADS"

---

#### Wariant B: Przełącznik w głównej rozdzielni
```
┌─────────────────────────────────────────────────────┐
│ ROZDZIELNIA GŁÓWNA                                  │
├─────────────────────────────────────────────────────┤
│                                                      │
│ [Main Grid]──┬──[ATS]──┬── Obwody główne           │
│              │         │                            │
│              │         └── [1] Salon               │
│              │             [2] Kuchnia             │
│              │             [3] Sypialnia           │
│              │                                      │
│ [Inverter]───┘         └── Obwody backup           │
│   (EPS out)                [B1] Router             │
│                            [B2] Lodówka            │
└─────────────────────────────────────────────────────┘

ATS = Automatic Transfer Switch (przełącznik automatyczny)
```

**Szukaj:**
- 🔄 Urządzenia z napisem "ATS", "Transfer Switch", "Przełącznik"
- 📊 Przekaźnika z dwoma wejściami (Grid + Inverter)
- 🔌 Części obwodów podłączonych "za" przełącznikiem

---

#### Wariant C: GoodWe Smart Meter + wybrane obwody
```
┌─────────────────────────────────────────────────────┐
│ ROZDZIELNIA GŁÓWNA                                  │
├─────────────────────────────────────────────────────┤
│ [Main] ← Grid                                       │
│   │                                                  │
│   ├──[Smart Meter]──┬── Wszystkie obwody główne    │
│   │                 │                               │
│   │    [Inverter]───┴── Wybrane obwody backup      │
│   │    (CT monitoring)  (tylko część!)             │
│   │                                                  │
│   └── Reszta bez backup                            │
└─────────────────────────────────────────────────────┘
```

**Szukaj:**
- 📟 GoodWe Smart Meter (liczy energię)
- 🔌 CT clamps (cęgi pomiarowe na kablach)
- 📝 Dokumentacji które obwody są monitorowane

---

### Krok 3: Zidentyfikuj fizyczne połączenia

**Co sprawdzić:**

1. **Wyjście EPS z falownika:**
   ```
   Na falowniku GoodWe GW10KN-ET szukaj:
   ├── Oznaczenia "BACKUP" lub "EPS"
   ├── Osobnego wyjścia AC (oprócz głównego)
   └── Zazwyczaj w dolnej części falownika
   ```

2. **Kabel z falownika do rozdzielni:**
   ```
   ├── Powinien być osobny kabel od głównego AC output
   ├── Może być oznaczony "BACKUP" lub "EPS"
   └── Zobacz dokąd prowadzi w rozdzielni
   ```

3. **Dokumentuj co widzisz:**
   ```
   Zrób notatki:
   [ ] Czy jest osobne wyjście EPS na falowniku?
   [ ] Czy jest dodatkowa mini-rozdzielnia backup?
   [ ] Czy jest przełącznik ATS?
   [ ] Które obwody są podłączone do backup?
   [ ] Czy są jakieś oznaczenia/naklejki?
   ```

---

## ⚡ Metoda 2: Kontrolowany test backup

### ⚠️ OSTRZEŻENIA BEZPIECZEŃSTWA:

```
❌ NIE wykonuj tego testu jeśli:
   • Pracujesz zdalnie / nie masz nadzoru
   • Ktoś używa ważnego sprzętu medycznego
   • Jest praca zdalna / ważne spotkania online
   • Nie masz czasu (test zajmie 20-30 min)

✅ Wykonuj test TYLKO gdy:
   • Bateria jest naładowana (SOC > 80%)
   • Jest dzień (działają panele PV)
   • Możesz szybko przywrócić prąd
   • Wszyscy w domu są poinformowani
   • Masz latarkę pod ręką
```

---

### Przygotowanie do testu:

#### 1. Przygotuj narzędzia i materiały
```
Potrzebujesz:
├── 📱 Aplikacja SEMS (do monitorowania)
├── 📝 Notatnik i długopis
├── 📸 Telefon z aparatem
├── 🔦 Latarka
├── ⏱️ Timer/stoper
└── 👨‍👩‍👧 Osoba pomocnicza (opcjonalnie)
```

#### 2. Sprawdź stan systemu
```
W aplikacji SEMS sprawdź:
├── SOC: ____% (minimum 80%!)
├── PV Power: ____W (dobrze jeśli > 1kW)
├── Battery Health: OK
├── Grid Voltage: ~230V (normalna)
└── Current Load: ____W (zanotuj!)
```

#### 3. Przygotuj listę urządzeń do sprawdzenia
```
Lista urządzeń w domu:
[ ] Lodówka/zamrażarki
[ ] Oświetlenie - pokój 1
[ ] Oświetlenie - pokój 2
[ ] Oświetlenie - korytarz
[ ] Router WiFi
[ ] Modem internetowy
[ ] Komputer(y)
[ ] Telewizor(y)
[ ] Gniazdka - salon
[ ] Gniazdka - kuchnia
[ ] Gniazdka - sypialnia
[ ] Gniazdka - biuro
[ ] Ogrzewanie / klimatyzacja
[ ] Pompa wody
[ ] Alarm / monitoring
[ ] Inne: _______________
```

---

### Przeprowadzenie testu:

#### Krok 1: Wyłącz główny bezpiecznik (symulacja przerwy)

```
🔧 Procedura:
1. Upewnij się że wszyscy są gotowi
2. Powiedz głośno: "WYŁĄCZAM PRĄD ZA 10 SEKUND"
3. Odlicz: 10... 5... 3... 2... 1...
4. Wyłącz główny wyłącznik w rozdzielni
5. Uruchom timer (mierz czas przełączenia)

⏱️ Obserwuj:
• Czy światła "mrugają" czy gasną całkowicie?
• Ile trwa przerwa? (powinno być < 1 sekundę)
• Czy słyszysz kliknięcie z falownika/przełącznika?
```

#### Krok 2: Sprawdź co działa (5-10 minut)

**Metodycznie sprawdź każde pomieszczenie:**

```
SALON:
├── [ ] Oświetlenie górne
├── [ ] Lampki boczne  
├── [ ] Gniazdko #1 (przy kanapie)
├── [ ] Gniazdko #2 (przy TV)
├── [ ] Gniazdko #3 (przy oknie)
└── [ ] Telewizor

KUCHNIA:
├── [ ] Oświetlenie główne
├── [ ] Lampka nad blatem
├── [ ] Gniazdko blat #1
├── [ ] Gniazdko blat #2
├── [ ] Lodówka
└── [ ] Mikrofala / czajnik (NIE WŁĄCZAJ!)

... i tak dalej dla każdego pomieszczenia
```

**Testowanie gniazdek:**
```
Użyj małego urządzenia (np. ładowarka od telefonu z LED):
├── Podłącz do gniazdka
├── Sprawdź czy świeci LED
└── Zaznacz w liście: ✅ działa / ❌ nie działa
```

#### Krok 3: Zmierz obciążenie podczas backup

```
W aplikacji SEMS sprawdź:
├── Grid: ____ W (powinno być ~0W)
├── Battery: ____ W (wartość dodatnia = rozładowanie)
├── Load: ____ W ⚠️ TO JEST KLUCZOWE!
├── SOC: ____% (sprawdź czy spada)
└── PV: ____W (jeśli słonecznie)

Zanotuj Load podczas backup: _____ W

Porównaj z normalnym Load przed testem: _____ W
```

#### Krok 4: Zrób zdjęcia (opcjonalnie)

```
Sfotografuj:
├── 📱 SEMS app - ekran z Load podczas backup
├── 💡 Które światła świecą
├── 🔌 Które gniazdka działają (z podłączonym testerem)
└── 📊 Licznik w rozdzielni (jeśli jest)
```

#### Krok 5: Przywróć zasilanie z sieci

```
🔧 Procedura:
1. Poczekaj co najmniej 5 minut w trybie backup
2. Powiedz: "WŁĄCZAM PRĄD ZA 5 SEKUND"
3. Odlicz: 5... 3... 2... 1...
4. Włącz główny wyłącznik
5. Obserwuj czy wszystko wraca do normy

✅ Sprawdź:
• Czy wszystkie urządzenia wróciły do pracy?
• Czy SEMS pokazuje Grid > 0W?
• Czy SOC się ustabilizował?
• Czy są jakieś błędy w aplikacji?
```

---

### Analiza wyników testu:

#### Obliczenia:

```
Load przed przerwą:     ____W  (A)
Load podczas backup:    ____W  (B)
Różnica:               ____W  (A - B)
Procent utraty:        ____%  ((A-B)/A * 100%)

Przykład z Twojego przypadku 27.10.2025:
Load przed:    1600W
Load backup:    350W (średnia 150-600W)
Różnica:       1250W
Utrata:         78%  ⚠️ PROBLEM!
```

#### Interpretacja wyników:

```
┌────────────────────────────────────────────────┐
│ WYNIK: Load backup ≈ Load normalny (-5-10%)   │
├────────────────────────────────────────────────┤
│ ✅ ŚWIETNIE! Większość domu jest na backup    │
│ • Mini spadek to normalne straty              │
│ • System działa poprawnie                     │
│ • Nie potrzebujesz zmian                      │
└────────────────────────────────────────────────┘

┌────────────────────────────────────────────────┐
│ WYNIK: Load backup ≈ 50-70% Load normalnego   │
├────────────────────────────────────────────────┤
│ ⚠️ ŚREDNIO - Część domu bez backup           │
│ • Kluczowe urządzenia działają                │
│ • Rozważ rozszerzenie backup circuit          │
│ • Nie krytyczne, ale można poprawić          │
└────────────────────────────────────────────────┘

┌────────────────────────────────────────────────┐
│ WYNIK: Load backup < 30% Load normalnego      │
├────────────────────────────────────────────────┤
│ ❌ PROBLEM! Większość domu BEZ backup         │
│ • Tylko podstawowe urządzenia działają        │
│ • System backup nieefektywny                  │
│ • PILNIE: Rozszerzenie backup circuit!        │
│                                                │
│ → TO JEST TWÓJ PRZYPADEK (350W / 1600W)      │
└────────────────────────────────────────────────┘
```

---

## 📄 Metoda 3: Analiza dokumentacji

### Co szukać w dokumentach:

#### 1. Dokumentacja instalacji PV
```
Poszukaj:
├── "Projekt instalacji fotowoltaicznej"
├── "Schemat elektryczny"
├── "Protokół odbioru instalacji"
└── "Instrukcja użytkownika systemu"

W dokumentach szukaj:
├── Sekcji "Backup" lub "EPS" lub "Off-grid"
├── Schematu rozdzielnicy
├── Listy obwodów backup
└── Rysunków technicznych
```

#### 2. Protokół odbioru instalacji
```
Powinien zawierać:
├── Specyfikację falownika (GW10KN-ET)
├── Specyfikację baterii (Lynx-D)
├── Listę obwodów backup (!!!)
├── Testy funkcjonalne EPS
└── Podpis instalatora i odbiór

❓ Pytanie do instalatora:
"Proszę o kopię protokołu odbioru z listą obwodów backup"
```

#### 3. Certyfikat/świadectwo instalacji
```
Dla instalacji > 0.8kW wymagane:
├── Świadectwo zgodności z NC RfG
├── Protokół pomiarów
├── Schemat instalacji
└── Deklaracja instalatora

Sprawdź czy jest wzmianka o backup/EPS
```

---

## 🔬 Metoda 4: Analiza danych z SEMS (retrospektywnie)

### Sprawdź historię z 27.10.2025:

```
W aplikacji SEMS:
├── History → 27.10.2025
├── Godziny: 07:00 - 11:00
└── Parametry: Grid, Load, Battery, SOC

Dane które już masz:
├── 07:55 Grid: 5W,    Load: 1569W ← PRZED przerwą
├── 08:00 Grid: 1W,    Load: 352W  ← START przerwy
├── 08:30 Grid: 1W,    Load: 166W  ← PODCZAS
├── 09:30 Grid: 7W,    Load: 594W  ← PODCZAS
├── 10:10 Grid: -10637W, Load: 1625W ← PO przerwie

WNIOSEK:
• Load spadło z 1569W do 166-594W
• Średnio ~350W podczas backup
• To tylko 22% normalnego obciążenia!
• 78% domu było BEZ zasilania ❌
```

---

## 📊 Porównanie metod

| Metoda | Łatwość | Dokładność | Bezpieczeństwo | Koszt | Czas |
|--------|---------|------------|----------------|-------|------|
| **Fizyczne sprawdzenie** | ⭐⭐ | ⭐⭐⭐ | ✅ Bezpieczne | 0 PLN | 30 min |
| **Test kontrolowany** | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⚠️ Ostrożnie | 0 PLN | 1h |
| **Analiza dokumentacji** | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ✅ Bezpieczne | 0 PLN | 15 min |
| **Dane historyczne** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ✅ Bezpieczne | 0 PLN | 5 min |

**Zalecenie:** Zacznij od metody 4 (dane historyczne) + 3 (dokumentacja), potem 1 (fizyczne), na końcu 2 (test) jeśli potrzebne.

---

## 📋 Szablon raportu z testu

### Wypełnij po teście:

```
========================================
RAPORT Z TESTU BACKUP CIRCUIT
========================================

Data testu: ___________________
Godzina: _____________________
Pogoda: ______________________
SOC przed testem: ________%

OBCIĄŻENIE:
├── Przed przerwą:      ______W
├── Podczas backup:     ______W
├── Po przywróceniu:    ______W
└── Utrata mocy:        ______W (___%)

URZĄDZENIA DZIAŁAJĄCE PODCZAS BACKUP:
[ ] Lodówka(i): które?_________________
[ ] Oświetlenie: które pokoje?_________
[ ] Router/modem: TAK / NIE
[ ] Komputery: które?__________________
[ ] TV: które?_________________________
[ ] Gniazdka salon: które?_____________
[ ] Gniazdka kuchnia: które?___________
[ ] Gniazdka sypialnia: które?_________
[ ] Gniazdka biuro: które?_____________
[ ] Ogrzewanie: TAK / NIE
[ ] Pompa wody: TAK / NIE
[ ] Inne: _____________________________

URZĄDZENIA NIE DZIAŁAJĄCE:
[ ] _________________________________
[ ] _________________________________
[ ] _________________________________
[ ] _________________________________

OBSERWACJE:
├── Czas przełączenia: ~_____ms
├── Czy światła mrugały: TAK / NIE
├── Czy komputery się zrestartowały: TAK / NIE
├── Problemy podczas testu: ___________
└── Inne uwagi: ______________________

ZDJĘCIA/PLIKI:
[ ] Zdjęcie SEMS - Load podczas backup
[ ] Zdjęcie rozdzielnicy
[ ] Zdjęcie falownika
[ ] Notatki szczegółowe

WNIOSKI:
_______________________________________
_______________________________________
_______________________________________

PLAN DZIAŁANIA:
[ ] Wystarczający backup - brak zmian
[ ] Rozszerzenie backup circuit - konsultacja z elektrykiem
[ ] Instalacja SZR - wycena
[ ] Inne: ______________________________

========================================
```

---

## 🎯 Co robić z wynikami?

### Scenariusz A: Backup działa dobrze (Load > 70%)
```
✅ Większość domu ma backup
✅ System działa poprawnie
✅ Nie potrzebujesz zmian

Opcjonalnie:
• Dodaj alerty w systemie o przełączeniu na backup
• Zrób test backup raz na kwartał
```

### Scenariusz B: Backup częściowy (Load 30-70%)
```
⚠️ Część domu bez backup
📞 Rozważ konsultację z elektrykiem
💰 Wycena rozszerzenia backup circuit

Koszt: 500-2000 PLN
Czas: 1 dzień pracy
Efekt: +30-40% urządzeń na backup
```

### Scenariusz C: Backup minimalny (Load < 30%) ← TWÓJ PRZYPADEK
```
❌ Większość domu BEZ backup
🚨 Pilne rozszerzenie systemu backup
📞 Kontakt z instalatorem + elektrykiem

Opcje:
1. Rozszerzenie backup circuit (500-2000 PLN)
   → Dodanie kluczowych obwodów
   
2. Instalacja SZR/Smart Grid Ready (2000-5000 PLN)
   → Pełne zabezpieczenie całego domu
   → ZALECANE dla Twojego przypadku!

Priorytetowe obwody do dodania:
├── Lodówka/zamrażarki (jedzenie!)
├── Ogrzewanie/pompa ciepła (komfort)
├── Komputery/biuro (praca)
├── Więcej gniazdek w kluczowych miejscach
└── Kluczowe oświetlenie
```

---

## 📞 Pytania do instalatora

**Skontaktuj się z instalatorem i zapytaj:**

```
1. DOKUMENTACJA:
   "Proszę o protokół odbioru z listą obwodów backup"
   "Proszę o schemat elektryczny instalacji"
   
2. OBECNA KONFIGURACJA:
   "Które obwody są obecnie na backup/EPS?"
   "Jaki jest limit mocy backup w mojej instalacji?"
   "Czy jest osobna rozdzielnia backup?"
   
3. ROZSZERZENIE:
   "Czy można dodać więcej obwodów do backup?"
   "Ile kosztowałoby dodanie [lista obwodów]?"
   "Czy polecacie instalację SZR?"
   "Jaki czas realizacji i koszt?"
   
4. PRZYCZYNA:
   "Dlaczego tylko część domu jest na backup?"
   "Czy to była świadoma decyzja czy ograniczenie?"
   "Co możemy zrobić żeby poprawić sytuację?"
```

---

## ✅ Checklist - Co zrobić krok po kroku

```
KROK 1: Analiza danych historycznych (WYKONANE ✅)
[ ] Przeanalizowałeś dane z 27.10.2025
[ ] Load spadło z 1600W do 350W
[ ] Zidentyfikowałeś problem

KROK 2: Sprawdź dokumentację (DO ZROBIENIA)
[ ] Znajdź protokół odbioru instalacji
[ ] Poszukaj schematu elektrycznego
[ ] Zobacz czy jest lista obwodów backup
[ ] Skontaktuj się z instalatorem o dokumenty

KROK 3: Fizyczne sprawdzenie (DO ZROBIENIA)
[ ] Zrób zdjęcia rozdzielnicy
[ ] Poszukaj oznaczenia "BACKUP" lub "EPS"
[ ] Sprawdź czy jest dodatkowa mini-rozdzielnia
[ ] Zanotuj co widzisz

KROK 4: Test kontrolowany (OPCJONALNE)
[ ] Przygotuj listę urządzeń
[ ] Sprawdź SOC > 80%
[ ] Przeprowadź test (wyłącz prąd)
[ ] Zanotuj co działa podczas backup
[ ] Zmierz Load w SEMS
[ ] Zrób raport

KROK 5: Konsultacja z instalatorem (NASTĘPNY KROK)
[ ] Przedstaw wyniki testu
[ ] Zapytaj o rozszerzenie backup circuit
[ ] Uzyskaj wycenę
[ ] Zdecyduj o dalszych krokach

KROK 6: Realizacja (W PRZYSZŁOŚCI)
[ ] Wybierz rozwiązanie (rozszerzenie / SZR)
[ ] Umów termin z elektrykiem
[ ] Wykonanie prac
[ ] Test po zmianach
[ ] Dokumentacja nowej konfiguracji
```

---

## 🎓 Podsumowanie

### Jak sprawdzić obwód backup:

1. **Najszybciej:** Dane historyczne (masz już - 350W/1600W = problem!)
2. **Najprostsze:** Dokumentacja instalacji (zapytaj instalatora)
3. **Najbezpieczniejsze:** Fizyczne sprawdzenie rozdzielnicy
4. **Najdokładniejsze:** Kontrolowany test backup

### Twój przypadek:

```
Status: PROBLEM ZIDENTYFIKOWANY ✅
├── Load podczas backup: 350W (średnio)
├── Load normalny: 1600W  
├── Utrata: 78% urządzeń
└── Przyczyna: Ograniczony backup circuit

Następne kroki:
1. ✅ Znajdź dokumentację instalacji
2. ✅ Skontaktuj się z instalatorem
3. ✅ Uzyskaj wycenę rozszerzenia
4. ✅ Zdecyduj: Rozszerzenie (500-2000 PLN) vs SZR (2000-5000 PLN)

Zalecenie: Instalacja SZR dla pełnego zabezpieczenia domu
```

---

**Data utworzenia:** 29 października 2025  
**Wersja:** 1.0  
**Status:** Gotowe do użycia





