# GoodWe - Detection Modes: Full Wave, Half Wave i Voltage Ride Through

**Dla falownika:** GoodWe GW10KN-ET  
**Kontekst:** Ustawienia wykrywania problemów z siecią i tryb backup/EPS

---

## 🔍 Co to jest Detection Mode?

**Detection Mode** to sposób, w jaki falownik **wykrywa utratę sieci** i decyduje kiedy przełączyć się w tryb backup/off-grid (EPS).

To kluczowe ustawienie dla:
- ✅ Bezpieczeństwa systemu (ochrona anty-wyspowa)
- ✅ Szybkości przełączania na backup
- ✅ Odporności na zakłócenia sieciowe  
- ✅ Zgodności z przepisami energetycznymi

---

## ⚡ DETECTION MODES - Typy wykrywania

### 1. **Full Wave Detection** (Detekcja pełnej fali)

**Jak działa:**
```
Monitoruje CAŁĄ falę sinusoidalną napięcia AC (360°)
├── Sprawdza dodatnią półfalę (0°-180°)
├── Sprawdza ujemną półfalę (180°-360°)  
├── Analizuje amplitudę, częstotliwość, fazę
└── Wymaga pełnego cyklu do podjęcia decyzji (20ms @ 50Hz)
```

**Charakterystyka:**
- ⏱️ **Czas detekcji:** ~20-50ms (1-2.5 cykli AC)
- 🎯 **Dokładność:** Bardzo wysoka
- 🛡️ **Odporność na zakłócenia:** Niska  
- ⚡ **Czas przełączania na backup:** Dłuższy (~50-100ms)
- 🔒 **Bezpieczeństwo:** Maksymalne (pełna analiza sygnału)

**Kiedy używać:**
```
✅ Stabilna sieć energetyczna (miasto)
✅ Wymóg maksymalnej dokładności detekcji
✅ Surowe przepisy anty-wyspowe
✅ Priorytet: bezpieczeństwo > szybkość
```

**Wady:**
```
❌ Fałszywe alarmy przy zakłóceniach
❌ Wolniejsze przełączanie na backup
❌ Wrażliwy na krótkie "mrugania" napięcia
```

---

### 2. **Half Wave Detection** (Detekcja połówki fali)

**Jak działa:**
```
Monitoruje tylko POŁOWĘ fali sinusoidalnej (180°)
├── Analizuje tylko dodatnią LUB ujemną półfalę
├── Szybsza analiza (połowa danych)
├── Decyzja po półcyklu (10ms @ 50Hz)
└── Mniej wrażliwa na przejściowe zakłócenia
```

**Charakterystyka:**
- ⏱️ **Czas detekcji:** ~10-30ms (0.5-1.5 cyklu AC)
- 🎯 **Dokładność:** Dobra
- 🛡️ **Odporność na zakłócenia:** Wysoka
- ⚡ **Czas przełączania na backup:** Szybszy (~30-70ms)
- 🔒 **Bezpieczeństwo:** Dobre (wystarczające dla większości zastosowań)

**Kiedy używać:**
```
✅ Niestabilna sieć (wieś, zakłócenia)
✅ Wymóg szybkiego przełączania na backup
✅ Częste chwilowe spadki napięcia
✅ Priorytet: szybkość > dokładność
```

**Zalety:**
```
✅ 2x szybsze przełączanie na backup
✅ Mniej fałszywych alarmów
✅ Lepsza odporność na "mrugania"
```

---

### 3. **Voltage Ride Through (VRT)** - Przejazd przez zakłócenia

**Czym jest VRT:**
```
Funkcja pozwalająca falownikowi POZOSTAĆ ONLINE 
podczas krótkotrwałych zakłóceń napięcia

Zamiast od razu się wyłączać:
├── Czeka 0.5-3 sekundy
├── Sprawdza czy napięcie wróci do normy
├── Jeśli wróci → kontynuuje pracę
└── Jeśli nie wróci → wyłącza się / przełącza na backup
```

**Rodzaje VRT:**

#### **LVRT (Low Voltage Ride Through)** - Przejazd przez spadki
```
Profil przykładowy dla GoodWe:

Spadek do 90%:  pracuj bez ograniczeń przez 3s
Spadek do 50%:  pracuj przez 1-2s
Spadek do 20%:  pracuj przez 0.5s
Spadek < 20%:   natychmiastowe odłączenie

Po powrocie napięcia: szybkie reconnect (2-5s)
```

#### **HVRT (High Voltage Ride Through)** - Przejazd przez wzrosty
```
Profil przykładowy dla GoodWe:

Wzrost do 110%: pracuj bez ograniczeń przez 3s
Wzrost do 130%: pracuj przez 1s + redukcja mocy
Wzrost > 130%:  natychmiastowe odłączenie

Po powrocie napięcia: szybkie reconnect (2-5s)
```

**Charakterystyka VRT:**
- ⏱️ **Tolerancja czasu:** 0.15-3 sekundy (zależy od poziomu zakłócenia)
- 🎯 **Cel:** Stabilizacja sieci, unikanie masowych odłączeń PV
- 🛡️ **Odporność:** Bardzo wysoka na przejściowe problemy
- ⚡ **Wpływ na backup:** **Może opóźnić przełączenie o 0.5-3s!**

**Kiedy używać (WYMAGANE!):**
```
✅ OBOWIĄZKOWE w UE/Polsce dla instalacji > 0.8kW
✅ Przepis NC RfG (Network Code)
✅ Wysoka penetracja OZE w sieci
✅ Wspieranie stabilności sieci
```

**⚠️ Potencjalny problem:**
```
Podczas RZECZYWISTEJ przerwy w prądzie:
├── Sieć pada kompletnie
├── VRT czeka 0.5-3s sprawdzając czy wróci
├── Dopiero potem przełącza się na backup
└── = Krótka przerwa w zasilaniu (mrugają światła!)
```

---

## 🇵🇱 Przepisy w Polsce - NC RfG

### Wymagania dla falowników PV w Polsce:

```
┌───────────────────────────────────────────────────────┐
│ NC RfG (od 2018) - OBOWIĄZKOWE!                      │
├───────────────────────────────────────────────────────┤
│ Dla instalacji > 0.8kW:                               │
│                                                        │
│ ✅ LVRT (Low Voltage Ride Through):                   │
│    • 0% napięcia przez 150ms minimum                 │
│    • 15% napięcia przez 1.5s                         │
│    • 90% napięcia przez 3s                           │
│                                                        │
│ ✅ HVRT (High Voltage Ride Through):                  │
│    • 130% napięcia przez 3s minimum                  │
│                                                        │
│ ✅ Ochrona anty-wyspowa (Anti-Islanding)             │
│ ✅ Automatyczny reconnect po normalizacji            │
└───────────────────────────────────────────────────────┘
```

**Twoja instalacja (10kW GoodWe):**
- ✅ **MUSI** mieć włączony VRT (LVRT + HVRT)
- ✅ **MUSI** spełniać NC RfG
- ✅ Instalator powinien to skonfigurować przy montażu
- ✅ Certyfikat zgodności z NC RfG

---

## 🔄 Porównanie - Jaki tryb wybrać?

| Parametr | Full Wave | Half Wave | VRT Impact |
|----------|-----------|-----------|------------|
| **Czas wykrycia utraty sieci** | 20-50ms | 10-30ms | +500-3000ms |
| **Całkowity czas do backup** | 50-100ms | 30-70ms | 550-3100ms |
| **Odporność na zakłócenia** | Niska | Wysoka | Bardzo wysoka |
| **Fałszywe alarmy** | Często | Rzadko | Bardzo rzadko |
| **Wsparcie dla sieci** | Nie | Nie | Tak (wymagane) |
| **Zgodność NC RfG** | ✅ | ✅ | ✅ Obowiązkowe |

---

## 🎯 Wpływ na Twój problem (27.10.2025)

### Analiza dla Twojego przypadku:

**Podczas przerwy 27.10.2025 (8:00-10:00):**
```
├── Grid spadło z normalnego do 0-2W
├── Przerwa trwała ~2 godziny
├── Load spadło z 1600W do 150-600W
└── SOC: 64-70% (bateria wystarczająca)
```

### Możliwy przebieg zdarzeń:

#### Wariant 1: Full Wave + VRT Enabled (prawdopodobny)
```
08:00:00.000  Sieć pada kompletnie
08:00:00.020  Full Wave wykrywa problem (20ms)
08:00:00.520  VRT czeka 500ms (sprawdza czy wróci)
08:00:00.620  Przełączenie na EPS (100ms)
─────────────────────────────────────────────────
Całkowity czas: ~620ms

W CZASIE tych 620ms:
• Większość urządzeń traci zasilanie
• Komputery mogą się restartować  
• Światła "mrugają"
• UPS'y się włączają
```

#### Wariant 2: Half Wave + VRT z minimalnym delay
```
08:00:00.000  Sieć pada kompletnie
08:00:00.010  Half Wave wykrywa problem (10ms)
08:00:00.160  VRT czeka 150ms (minimum NC RfG)
08:00:00.200  Przełączenie na EPS (40ms)
─────────────────────────────────────────────────
Całkowity czas: ~200ms

W CZASIE tych 200ms:
• Większość urządzeń kontynuuje pracę
• Może być prawie niezauważalne
• Tylko czułe urządzenia zauważą
```

### ❌ **ALE: To NIE rozwiązuje Twojego głównego problemu!**

```
┌────────────────────────────────────────────────────┐
│ Detection Mode wpływa na:                          │
├────────────────────────────────────────────────────┤
│ ✅ Szybkość wykrycia utraty sieci                  │
│ ✅ Czas przełączenia na backup                     │
│ ✅ Komfort podczas przełączania                    │
│                                                     │
│ Detection Mode NIE wpływa na:                      │
├────────────────────────────────────────────────────┤
│ ❌ Moc dostępną podczas backup                     │
│ ❌ Które urządzenia są zasilane                    │
│ ❌ Obciążenie load podczas backup                  │
└────────────────────────────────────────────────────┘

TWÓJ PROBLEM:
• Falownik przełączył się na backup ✅ (działało)
• Backup trwał 2 godziny ✅ (działało)
• Ale load to tylko 150-600W zamiast 1600W ❌

PRZYCZYNA:
• Instalacja elektryczna (backup circuit)
• Większość domu NIE jest podłączona do EPS output
```

---

## ⚙️ Gdzie to sprawdzić w SEMS

### Lokalizacja ustawień:

```
SEMS Portal (aplikacja / web)
  └── Device → Inverter → Settings → Advanced Settings
      └── Grid Protection Settings
          ├── Detection Mode:
          │   • [o] Full Wave Detection  
          │   • [o] Half Wave Detection
          │
          ├── Voltage Ride Through (VRT):
          │   ├── [✓] Enable LVRT (required!)
          │   ├── [✓] Enable HVRT (required!)
          │   ├── LVRT Trip Time: [___] ms
          │   └── HVRT Trip Time: [___] ms
          │
          └── Grid Protection Parameters:
              ├── Over Voltage Trip: [___] V
              ├── Under Voltage Trip: [___] V
              ├── Over Frequency Trip: [___] Hz
              └── Under Frequency Trip: [___] Hz
```

**⚠️ UWAGA:**
```
┌─────────────────────────────────────────┐
│ Te ustawienia są zazwyczaj:            │
├─────────────────────────────────────────┤
│ 🔒 ZABLOKOWANE dla konta USER          │
│ 🔐 Dostępne dla INSTALLER / SERVICE    │
│ ⚠️ Chronione ze względów bezpieczeństwa│
│ ⚠️ Wymagają certyfikacji po zmianie    │
└─────────────────────────────────────────┘
```

---

## 💡 Zalecane ustawienia dla Twojej instalacji

### Dla Polski (Małopolska, obszar wiejski):

```yaml
Recommended Configuration:
  
  Detection Mode: Half Wave Detection
    Powód: 
      • Lepsza odporność na zakłócenia (wieś)
      • Szybsze przełączanie na backup (~30-70ms)
      • Mniej fałszywych alarmów
      
  LVRT (Low Voltage Ride Through): ENABLED ⚡ WYMAGANE
    Settings:
      • 0% voltage: 150ms minimum (NC RfG)
      • 15% voltage: 1500ms
      • 90% voltage: 3000ms
    Powód: Przepisy NC RfG (obowiązkowe)
      
  HVRT (High Voltage Ride Through): ENABLED ⚡ WYMAGANE  
    Settings:
      • 130% voltage: 3000ms minimum (NC RfG)
    Powód: Przepisy NC RfG (obowiązkowe)
    
  VRT Delay Optimization:
    • Użyj MINIMALNYCH dopuszczalnych czasów NC RfG
    • Szybsze przełączanie podczas prawdziwej przerwy
    • Nadal zgodne z przepisami
```

### Kompromis między zgodnością a szybkością:

```
┌─────────────────────────────────────────────────────┐
│ NAJSZYBSZE legalne przełączanie na backup:         │
├─────────────────────────────────────────────────────┤
│ • Detection Mode: Half Wave (~10ms)                │
│ • VRT LVRT Delay: 150ms (minimum NC RfG)          │
│ • Przełączenie EPS: ~40ms                          │
│ ─────────────────────────────────────────          │
│ RAZEM: ~200ms całkowitego czasu                    │
│                                                     │
│ VS standardowa konfiguracja:                       │
│ • Full Wave + VRT 500ms = ~620ms                   │
│                                                     │
│ WYGRANA: 3x szybsze przełączanie! ✅               │
└─────────────────────────────────────────────────────┘
```

---

## 🔧 Plan działania

### Co możesz zrobić:

#### Krok 1: Sprawdź obecną konfigurację
```
1. Zaloguj się do SEMS Portal
2. Sprawdź Device → Settings → Advanced
3. Zanotuj:
   • Detection Mode: Full/Half Wave?
   • VRT Enabled: Yes/No?
   • LVRT/HVRT Times: ile ms?
```

#### Krok 2: Skontaktuj się z instalatorem
```
Pytania do instalatora:
├── Jaki jest obecnie Detection Mode?
├── Czy VRT jest włączony? (powinien!)
├── Czy można zmienić na Half Wave?
├── Czy można zmniejszyć VRT delay do minimum NC RfG?
├── Czy to wymaga ponownej certyfikacji?
└── Jaki wpływ na gwarancję?
```

#### Krok 3: Nie zmieniaj sam!
```
⚠️ NIE ZMIENIAJ tych ustawień samodzielnie:
├── Wymaga dostępu INSTALLER
├── Może naruszyć przepisy energetyczne
├── Może unieważnić certyfikację
├── Może wpłynąć na gwarancję
└── Operator sieci może zażądać przywrócenia
```

---

## 📊 Co to zmieni w praktyce?

### Realistyczne oczekiwania:

#### Scenariusz A: Optymalizacja Detection Mode
```
Przed: Full Wave + VRT 500ms = 620ms do backup
Po:    Half Wave + VRT 150ms = 200ms do backup

EFEKT:
✅ 3x szybsze przełączanie  
✅ Mniej "mrugania" podczas przerwy
✅ Lepszy komfort
✅ Niektóre urządzenia mogą nie zauważyć przerwy

ALE:
❌ Nadal tylko 150-600W load podczas backup
❌ Większość domu nadal bez zasilania
```

#### Scenariusz B: Przeróbka instalacji elektrycznej (PRIORYTET!)
```
Przed: Backup circuit = 150-600W
Po:    Backup circuit = 3000-6000W

EFEKT:
✅ 5-10x więcej mocy podczas backup
✅ Większość domu działa podczas przerwy
✅ Pełne wykorzystanie możliwości systemu

To jest GŁÓWNE rozwiązanie Twojego problemu!
```

---

## 📋 Checklist diagnoza

Przed kontaktem z instalatorem wypełnij:

```
[ ] Model falownika: GW10KN-ET
[ ] Moc: 10kW
[ ] Bateria: 2x Lynx-D (20kWh)
[ ] Data incydentu: 27.10.2025
[ ] SOC podczas incydentu: 64-70%
[ ] Czas przerwy: 2h (8:00-10:00)
[ ] Load przed przerwą: 1600W
[ ] Load podczas backup: 150-600W

Ustawienia (jeśli znane):
[ ] Detection Mode: _____________ (Full/Half?)
[ ] LVRT Enabled: _____________ (Yes/No?)
[ ] HVRT Enabled: _____________ (Yes/No?)
[ ] VRT Delay: _____________ ms
[ ] Over/Under Voltage Trip: _____________ V
[ ] Over/Under Frequency Trip: _____________ Hz

Priorytet działań:
[1] Sprawdź/zwiększ limity EPS w SEMS
[2] Przeróbka backup circuit (elektryk)
[3] Optymalizacja Detection Mode (instalator)
```

---

## 🎯 Podsumowanie

### Czym jest Detection Mode:

```
Full Wave Detection:
├── Analizuje całą falę AC (360°)
├── Wolniejszy (~20-50ms)
├── Dokładniejszy
└── Bardziej wrażliwy na zakłócenia

Half Wave Detection:
├── Analizuje połowę fali AC (180°)
├── Szybszy (~10-30ms)
├── Dostatecznie dokładny
└── Odporniejszy na zakłócenia

Voltage Ride Through (VRT):
├── OBOWIĄZKOWY w Polsce (NC RfG)
├── Pozwala "przetrwać" zakłócenia
├── Opóźnia przełączenie na backup (+150-3000ms)
└── Stabilizuje sieć
```

### Co to znaczy dla Ciebie:

```
┌────────────────────────────────────────────────┐
│ DOBRE WIEŚCI:                                 │
├────────────────────────────────────────────────┤
│ ✅ Detection Mode można zoptymalizować        │
│ ✅ Half Wave + min VRT = 3x szybciej          │
│ ✅ Mniej "mrugania" podczas przerw            │
│                                                │
│ ALE:                                          │
├────────────────────────────────────────────────┤
│ ❌ To nie rozwiąże problemu 150-600W load    │
│ ❌ Główny problem: backup circuit             │
│ ❌ Potrzebna: przeróbka instalacji            │
└────────────────────────────────────────────────┘
```

### Kolejność działań:

1. **Najpierw:** Sprawdź limity EPS w SEMS (0 PLN, 30 min)
2. **Potem:** Przeróbka backup circuit (500-5000 PLN, 1-2 dni) ⭐ PRIORYTET
3. **Na końcu:** Optymalizacja Detection Mode (konsultacja z instalatorem)

---

## 📞 Kontakt

**GoodWe Support Polska:**
- 📧 service@goodwe.pl
- ☎️ +48 22 299 96 93

**Twoja dokumentacja:**
- `docs/OFFGRID_PROBLEM_ANALYSIS_20251027.md` - główna analiza
- `docs/GOODWE_SEMS_BACKUP_CONFIGURATION.md` - konfiguracja SEMS
- `out/SEMS_QUICK_GUIDE.txt` - szybki przewodnik

---

**Data utworzenia:** 29 października 2025  
**Wersja:** 1.0
