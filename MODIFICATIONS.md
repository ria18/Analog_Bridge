# Code-Modifikationen für BOS-Radio-Bridge

Diese Datei dokumentiert die erforderlichen Code-Modifikationen, um Analog_Bridge für den Software-only-Betrieb ohne DV3000-Hardware anzupassen.

## Übersicht

Die Standard-Binaries von Analog_Bridge (v1.6.4) stürzen ab, da sie zwingend einen DV3000-Hardware-Chip auf Port 2460 erwarten. Diese Modifikationen stellen sicher, dass das Programm stabil ohne Hardware-Reset läuft und softAMBE als Standardverhalten verwendet.

## Erforderliche Modifikationen

### 1. Hardware-Check entfernen (Port 2460)

**Ziel**: Entfernen des zwingenden Hardware-Checks für DV3000 auf Port 2460.

**Zu suchende Stellen in `Analog_Bridge.cpp` oder relevanten Header-Dateien:**

#### 1.1 DV3000-Verbindungscheck
```cpp
// TYPISCHER CODE (zu finden und zu modifizieren):
// Suche nach Verbindungen zu Port 2460
// Suche nach connectToDV3000() oder ähnlichen Funktionen
// Suche nach exit(1) oder fatalen Fehlern bei Hardware-Fehlschlag

// BEISPIEL VORHER:
if (!connectToDV3000("127.0.0.1", 2460)) {
    std::cerr << "Fatal Error: DV3000 not found at 127.0.0.1:2460" << std::endl;
    exit(1);  // <-- Dies muss entfernt/kommentiert werden
}

// BEISPIEL NACHHER:
/*
if (!connectToDV3000("127.0.0.1", 2460)) {
    std::cerr << "Fatal Error: DV3000 not found at 127.0.0.1:2460" << std::endl;
    exit(1);
}
*/
// Software-only Modus: Hardware-Check deaktiviert
// softAMBE wird als Fallback verwendet
```

#### 1.2 Reset-Sequenz auf Port 2460
```cpp
// TYPISCHER CODE (zu finden):
// Suche nach Reset-Kommandos für DV3000
// Suche nach UDP-Kommunikation auf Port 2460
// Suche nach bytearray/Byte-Arrays mit Reset-Kommandos (z.B. "61 00 07 00 34 05 00 00 0F 00 00")

// BEISPIEL VORHER:
bool resetDV3000() {
    // Reset-Kommando senden
    sendResetCommand("127.0.0.1", 2460);
    if (!waitForResponse()) {
        std::cerr << "Fatal Error: DV3000 reset failed" << std::endl;
        exit(1);  // <-- Dies muss entfernt werden
    }
    return true;
}

// BEISPIEL NACHHER:
bool resetDV3000() {
    // Hardware-Reset deaktiviert für Software-only Betrieb
    /*
    sendResetCommand("127.0.0.1", 2460);
    if (!waitForResponse()) {
        std::cerr << "Fatal Error: DV3000 reset failed" << std::endl;
        exit(1);
    }
    */
    // Software-only: Kein Hardware-Reset erforderlich
    return true;  // Immer erfolgreich (Software-Modus)
}
```

### 2. softAMBE als Standard setzen

**Ziel**: softAMBE standardmäßig verwenden, wenn keine Hardware gefunden wird.

#### 2.1 Initialisierung anpassen
```cpp
// TYPISCHER CODE (zu finden):
// Suche nach Initialisierungsroutinen
// Suche nach AMBE-Codec-Auswahl
// Suche nach Hardware/Software-Umschaltung

// BEISPIEL VORHER:
bool initializeCodec() {
    if (connectToDV3000("127.0.0.1", 2460)) {
        useHardwareCodec = true;
        return true;
    } else {
        std::cerr << "Error: No hardware codec found" << std::endl;
        return false;  // <-- Muss geändert werden
    }
}

// BEISPIEL NACHHER:
bool initializeCodec() {
    // Hardware-Check optional (nicht zwingend)
    if (connectToDV3000("127.0.0.1", 2460)) {
        useHardwareCodec = true;
        useSoftAMBE = false;
        return true;
    } else {
        // Software-only: softAMBE als Standard verwenden
        useHardwareCodec = false;
        useSoftAMBE = true;  // <-- Standardverhalten
        std::cout << "Info: Using softAMBE (software-only mode)" << std::endl;
        return true;  // <-- Immer erfolgreich
    }
}
```

#### 2.2 Fallback-Mechanismus
```cpp
// TYPISCHER CODE (zu finden):
// Suche nach decoderFallBack oder ähnlichen Flags
// Suche nach Software-Decoder-Initialisierung

// BEISPIEL VORHER:
if (decoderFallBack) {
    // Soft-Decoder nur als Fallback
    if (hardwareDecoderFailed) {
        initializeSoftDecoder();
    }
}

// BEISPIEL NACHHER:
// softAMBE als Standardverhalten
if (decoderFallBack || useSoftAMBE) {
    // Soft-Decoder als Standard verwenden
    initializeSoftDecoder();  // <-- Standardverhalten
    useSoftAMBE = true;
}
```

### 3. Konfigurationsabfrage anpassen

**Ziel**: Konfigurationseinstellungen berücksichtigen, die Software-only-Modus erlauben.

```cpp
// TYPISCHER CODE (zu finden):
// Suche nach Konfigurationsdatei-Lesung
// Suche nach [DV3000] Sektion
// Suche nach serial/useSerial Flags

// BEISPIEL:
// In Konfigurationsdatei: decoderFallBack = true
// Im Code:
bool decoderFallBack = config.getBool("GENERAL", "decoderFallBack", true);
if (decoderFallBack) {
    useSoftAMBE = true;  // Standardverhalten
}
```

## Suchkriterien für Code-Analyse

Verwenden Sie diese Suchbegriffe, um die relevanten Code-Stellen zu finden:

### In C++ Source-Dateien suchen:
- `2460` - Port-Nummer für DV3000
- `DV3000` - Hardware-Name
- `exit(1)` - Fataler Fehler (zu entfernen)
- `connectToDV3000` - Verbindungsfunktion
- `reset` - Reset-Sequenz
- `Fatal Error` oder `Fatal Error` - Fehlermeldungen
- `decoderFallBack` - Fallback-Flag
- `useEmulator` - Emulator-Flag
- `softAMBE` - Software-AMBE
- `AMBE` - AMBE-Codec-Bezüge

### In Header-Dateien suchen:
- Funktionen, die DV3000 verwenden
- Initialisierungsfunktionen
- Codec-Auswahl-Mechanismen

## Code-Beispiele aus Analog_Bridge

Basierend auf den Test-Skripten (`AMBEtest4.py`, `AMBEtest4_p3.py`) und der Konfiguration:

### Port 2460 - UDP-Kommunikation
Der DV3000 verwendet UDP-Port 2460 für Kommunikation. Suchen Sie nach:
- UDP-Socket-Erstellung
- `sendto()` / `recvfrom()` auf Port 2460
- IP-Adresse `127.0.0.1:2460`

### Reset-Kommando
Das Reset-Kommando ist typischerweise:
```
61 00 07 00 34 05 00 00 0F 00 00
```

Suchen Sie nach Byte-Arrays mit diesen Werten oder ähnlichen Hex-Strings.

## Testen der Modifikationen

Nach den Modifikationen sollte das Programm:

1. **Ohne Hardware starten**: Kein Crash, kein exit(1)
2. **softAMBE verwenden**: Software-Codec wird initialisiert
3. **Log-Nachrichten ausgeben**: "Using softAMBE" oder ähnlich
4. **Stabil laufen**: Keine Fehler bei fehlender Hardware

### Test-Strategie

```bash
# 1. Build testen
make clean
make

# 2. Ohne Hardware starten (sollte nicht abstürzen)
./Analog_Bridge

# 3. Log-Datei prüfen
tail -f Analog_Bridge.log

# 4. Erwartete Ausgabe:
# - Keine "Fatal Error" Meldungen
# - "Using softAMBE" oder ähnliche Nachricht
# - Programm läuft stabil
```

## Bekannte Probleme

### Problem 1: Binary stürzt ab
**Ursache**: Hardware-Check führt zu exit(1)
**Lösung**: Alle exit(1) bei Hardware-Fehlschlag entfernen/kommentieren

### Problem 2: softAMBE wird nicht verwendet
**Ursache**: Code verwendet noch Hardware-Modus als Standard
**Lösung**: Initialisierung so ändern, dass softAMBE Standard ist

### Problem 3: Port 2460 wird noch verwendet
**Ursache**: Code versucht noch, auf Port 2460 zuzugreifen
**Lösung**: Port-Zugriffe kommentieren oder optional machen

## Hinweise

- **Vorsicht**: Modifikationen sollten sorgfältig getestet werden
- **Backup**: Original-Source-Code sichern vor Modifikationen
- **Versionierung**: Git verwenden für Versionskontrolle
- **Dokumentation**: Alle Änderungen dokumentieren

## Referenzen

- Analog_Bridge Test-Skripte: `scripts/AMBEtest4*.py`
- Konfigurationsdatei: `Analog_Bridge/Analog_Bridge.ini`
- DVSwitch Dokumentation

---

**Wichtig**: Diese Modifikationen können nur durchgeführt werden, wenn der Source-Code verfügbar ist. Das ursprüngliche Repository enthält nur Binaries.

