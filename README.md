# BOS-Radio-Bridge

Ein angepasstes Analog_Bridge für das BOS-Gateway-Projekt auf Raspberry Pi (ARM64).

## Übersicht

Dieses Projekt basiert auf der Analog_Bridge (v1.6.4) von DVSwitch und wurde für den Betrieb ohne DV3000-Hardware-Chip modifiziert. Die Standard-Binaries stürzen ab, da sie zwingend einen DV3000 auf Port 2460 erwarten. Diese Version verwendet softAMBE (Software-AMBE-Codec) als Standardverhalten und läuft stabil ohne Hardware-Reset.

## Hauptmerkmale

- **Software-only Betrieb**: Keine Abhängigkeit von DV3000-Hardware
- **ARM64-optimiert**: Performance-optimiert für Raspberry Pi OS (ARM64)
- **softAMBE als Standard**: Verwendet Software-AMBE-Codec standardmäßig
- **Niedrige Latenz**: Natives Binary ohne Docker
- **Erweiterbar**: Vorbereitet für AI-Module (Noise Cancelling - Phase 7)

## Anforderungen

### Hardware
- Raspberry Pi (ARM64-kompatibel)
- Raspberry Pi OS (64-bit)

### Software-Abhängigkeiten
```bash
# Basis-Tools
sudo apt-get update
sudo apt-get install -y build-essential git cmake pkg-config

# C++ Compiler und Tools
sudo apt-get install -y g++ gcc make

# Bibliotheken (beispielhaft - anpassen nach tatsächlichen Abhängigkeiten)
sudo apt-get install -y libpthread-stubs0-dev libssl-dev
```

### softAMBE-Bibliothek
Die softAMBE-Bibliothek muss separat installiert werden. Details zur Installation finden Sie in der softAMBE-Dokumentation.

## Installation

### 1. Repository klonen
```bash
git clone <repository-url>
cd Analog_bridge
```

### 2. Source-Code vorbereiten
**Wichtig**: Das ursprüngliche Repository enthält nur Binaries. Für die Modifikationen wird der Source-Code benötigt.

Falls der Source-Code verfügbar ist:
```bash
# Source-Code in src/ Verzeichnis ablegen
mkdir -p src include
# Analog_Bridge.cpp und Header-Dateien nach src/ kopieren
```

### 3. Code-Modifikationen (wenn Source-Code verfügbar)

#### Hardware-Check entfernen
Suchen Sie in `Analog_Bridge.cpp` nach Code-Abschnitten, die den DV3000-Hardware-Check durchführen:

**Zu suchende Stellen:**
- Verbindungen zu Port 2460 (DV3000)
- `exit(1)` oder Fatal-Errors bei fehlendem Hardware-Reset
- Initialisierungsroutinen für DV3000

**Beispielhafte Modifikation:**
```cpp
// VORHER (Beispiel):
if (!connectToDV3000("127.0.0.1", 2460)) {
    std::cerr << "Fatal Error: DV3000 not found" << std::endl;
    exit(1);
}

// NACHHER (kommentiert/entfernt):
/*
if (!connectToDV3000("127.0.0.1", 2460)) {
    std::cerr << "Fatal Error: DV3000 not found" << std::endl;
    exit(1);
}
*/
// Software-only Modus aktiviert - softAMBE wird verwendet
```

#### softAMBE als Standard setzen
Stellen Sie sicher, dass softAMBE standardmäßig verwendet wird:

```cpp
// In der Initialisierung:
bool useSoftAMBE = true;  // Standard: Software-AMBE

// Hardware-Check optional (nicht mehr zwingend):
if (!connectToDV3000(...)) {
    useSoftAMBE = true;  // Fallback auf Software
    // KEIN exit(1) mehr!
}
```

### 4. Build

```bash
# Optimiertes Build für ARM64
make

# Oder Debug-Build
make debug
```

### 5. Installation

```bash
sudo make install
```

## Konfiguration

Die Konfigurationsdatei befindet sich unter `/etc/Analog_Bridge.ini` (nach Installation) oder lokal als `Analog_Bridge/Analog_Bridge.ini`.

### Wichtige Einstellungen

#### AMBE_AUDIO (MMDVM_Bridge)
```ini
[AMBE_AUDIO]
address = 127.0.0.1          ; IP-Adresse der MMDVM_Bridge
txPort = 33101               ; Transmit-Port zur MMDVM_Bridge
rxPort = 33100               ; Receive-Port von MMDVM_Bridge
ambeMode = DMR               ; Modus: DMR, DSTAR, P25, NXDN, etc.
```

#### DV3000 (Software-only)
```ini
[DV3000]
address = 127.0.0.1          ; Wird nicht verwendet (Software-only)
rxPort = 2460                ; Wird nicht verwendet (Software-only)
; serial = false             ; Software-Modus
```

#### General
```ini
[GENERAL]
decoderFallBack = true       ; Wichtig: Software-Decoder erlauben
useEmulator = false          ; softAMBE verwenden (nicht MD380-Emulator)
```

### Vollständige Beispielkonfiguration

Siehe `Analog_Bridge/Analog_Bridge.ini` für eine vollständige Konfigurationsdatei.

## Verwendung

### Start
```bash
# Als Service (empfohlen)
sudo systemctl start analog_bridge

# Oder manuell
/usr/local/bin/Analog_Bridge
```

### Log-Dateien
Standardmäßig werden Logs in der Datei `Analog_Bridge.log` geschrieben. Der Speicherort kann über die Umgebungsvariable `AnalogBridgeLogDir` konfiguriert werden.

### Systemd-Service

Ein Systemd-Service-Template befindet sich in `Analog_Bridge/systemd/analog_bridge.service`.

```bash
# Service installieren
sudo cp Analog_Bridge/systemd/analog_bridge.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable analog_bridge
sudo systemctl start analog_bridge
```

## Kommunikation mit MMDVM_Bridge

Die Kommunikation erfolgt über die Ports:
- **33100**: Receive-Port (Analog_Bridge empfängt von MMDVM_Bridge)
- **33101**: Transmit-Port (Analog_Bridge sendet an MMDVM_Bridge)

Stellen Sie sicher, dass diese Ports in beiden Konfigurationsdateien korrekt eingestellt sind.

## Build-Optimierungen

Das Makefile ist für Raspberry Pi (ARM64) optimiert:
- **CPU-Flags**: `-march=armv8-a+fp+simd -mtune=cortex-a72`
- **Optimierung**: `-O3 -flto` (Link-Time Optimization)
- **Performance**: Optimiert für Cortex-A72 (Raspberry Pi 4)

## Fehlerbehebung

### Problem: Binary stürzt ab
- **Ursache**: Hardware-Check für DV3000 schlägt fehl
- **Lösung**: Sicherstellen, dass Code-Modifikationen durchgeführt wurden (Hardware-Check entfernt)

### Problem: softAMBE wird nicht verwendet
- **Ursache**: Konfiguration oder Code verwendet noch Hardware-Modus
- **Lösung**: 
  - `decoderFallBack = true` in der Konfiguration setzen
  - Sicherstellen, dass softAMBE-Bibliothek korrekt verlinkt ist

### Problem: Verbindung zu MMDVM_Bridge schlägt fehl
- **Ursache**: Ports 33100/33101 nicht korrekt konfiguriert
- **Lösung**: Ports in beiden Konfigurationsdateien überprüfen

## Zukünftige Entwicklungen

### Phase 7: AI-Module für Noise Cancelling
Das System ist vorbereitet für die Integration von AI-Modulen:
- Plugin-System für Audio-Processing
- Schnittstellen für externe Module
- Konfigurierbare Audio-Pipeline

## Lizenz

Basierend auf Analog_Bridge von DVSwitch. Siehe Original-Lizenz für Details.

## Beitragende

- Original: DVSwitch Project
- Modifikationen: BOS-Gateway Projekt

## Support

Bei Fragen oder Problemen:
1. Überprüfen Sie die Log-Dateien
2. Prüfen Sie die Konfigurationsdatei
3. Stellen Sie sicher, dass alle Abhängigkeiten installiert sind

## Referenzen

- [DVSwitch Projekt](https://github.com/DVSwitch)
- [MMDVM_Bridge](https://github.com/g4klx/MMDVM_Bridge)
- softAMBE Dokumentation

---

**Hinweis**: Dieses Projekt erfordert den Source-Code der Analog_Bridge für vollständige Funktionalität. Das ursprüngliche Repository enthält nur Binaries. Kontaktieren Sie die DVSwitch-Community oder verwenden Sie einen Fork mit verfügbarem Source-Code.

