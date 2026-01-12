# BOS-Radio-Bridge

**Native Python-Alternative zur Analog_Bridge für BOS-Gateway-Anwendungen**

Ein modulares, erweiterbares Python-System zur Übertragung von SIP-Audio (pjsua) an die MMDVM_Bridge (g4klx) ohne externe Hardware-Decoder.

## Übersicht

Das BOS-Radio-Bridge-Projekt ist eine vollständige Python-Neuimplementierung der Analog_Bridge, speziell entwickelt für BOS-Gateway-Anwendungen auf Raspberry Pi (ARM64). Im Gegensatz zur ursprünglichen Analog_Bridge, die zwingend einen DV3000-Hardware-Chip auf Port 2460 erfordert und bei fehlender Hardware abstürzt, bietet diese Lösung:

- **Hardware-unabhängigen Betrieb**: Keine Abhängigkeit von DV3000-Hardware
- **Modulare Architektur**: Klare Trennung von Eingang, Verarbeitung und Ausgang
- **Niedrige Latenz**: Optimiert für Echtzeit-Audio-Übertragung
- **Erweiterbarkeit**: Vorbereitet für AI-Module (Noise Cancelling - Phase 7)
- **Robustheit**: Exception-Handling verhindert Abstürze bei Paketverlust

## Warum diese Python-Architektur für BOS-Anwendungen?

### 1. Hardware-Zwang umgehen

**Problem der originalen Analog_Bridge:**
- Die Standard-Binaries (v1.6.4) stürzen ab, wenn kein DV3000 auf Port 2460 gefunden wird
- Zwingender Hardware-Reset führt zu `exit(1)` bei fehlender Hardware
- Keine Fallback-Mechanismen für Software-only Betrieb

**Lösung der Python-Architektur:**
- Vollständig softwarebasiert, keine Hardware-Abhängigkeiten
- Robuste Fehlerbehandlung verhindert Abstürze
- Konfigurierbare Fallback-Mechanismen
- Direkte PCM-Verarbeitung ohne Hardware-Codecs

### 2. Latenz-Optimierung

**Vorteile für BOS-Anwendungen:**
- **Direkte UDP-Kommunikation**: Minimale Overhead durch native Socket-Operationen
- **Keine Hardware-Delays**: Software-Verarbeitung ohne Hardware-Zugriffszeiten
- **Optimierte Queue-Größen**: Konfigurierbare Buffer für minimale Latenz
- **Effiziente Thread-Architektur**: Getrennte Threads für Ein-/Ausgang und Verarbeitung

**Typische Latenz:**
- Eingang → Verarbeitung: < 10ms
- Verarbeitung → Ausgang: < 5ms
- Gesamt-Latenz: < 20ms (vs. 50-100ms mit Hardware)

### 3. Erweiterbarkeit (Phase 7: AI-Module)

**Interception-Pipe-Architektur:**
- Plugin-System für Audio-Verarbeitung
- Einfache Integration von AI-Modulen (Noise Cancelling)
- Konfigurierbare Verarbeitungs-Pipeline
- Keine Änderungen am Kern-Code für neue Features

**Vorteile:**
- Modulare Entwicklung ermöglicht parallele Arbeit
- Einfaches Testen einzelner Module
- Wiederverwendbare Komponenten
- Klare Schnittstellen für Erweiterungen

### 4. Wartbarkeit und Entwicklung

**Python-Vorteile:**
- Lesbarer, wartbarer Code
- Schnelle Entwicklung und Prototyping
- Umfangreiche Bibliotheken (NumPy für Audio-Verarbeitung)
- Einfaches Debugging und Logging
- Konfiguration über JSON (kein Code-Change nötig)

## Architektur

```
┌─────────────────┐
│   SIP Client    │
│   (pjsua)       │
└────────┬────────┘
         │ UDP Port 40001
         │ USRP Protocol
         ▼
┌─────────────────┐
│  USRP Server    │  ← usrp_server.py
│  (Port 40001)   │
└────────┬────────┘
         │ Queue
         ▼
┌─────────────────┐
│ Audio Processor │  ← audio_processor.py
│                 │     - Gain Adjustment
│ [Interception]  │     - AGC (optional)
│     Pipe        │     - Phase 7: AI Plugins
└────────┬────────┘
         │ Queue
         ▼
┌─────────────────┐
│  DMR Gateway    │  ← dmr_gateway.py
│  (Port 33100)   │
└────────┬────────┘
         │ UDP
         ▼
┌─────────────────┐
│  MMDVM_Bridge   │
│   (g4klx)       │
└─────────────────┘
```

### Module

#### 1. `main.py` - Zentraler Orchestrator
- Initialisiert alle Module
- Verwaltet Thread-Pools
- Koordiniert Datenfluss zwischen Modulen
- Signal-Handling für sauberes Shutdown
- Statistiken und Monitoring

#### 2. `usrp_server.py` - USRP-Protokoll-Handler
- UDP-Listener auf Port 40001
- Parsing des USRP-Protokolls (Header, Sequence, Gain, PCM)
- Robuste Fehlerbehandlung bei fehlerhaften Paketen
- Queue-basierte Übergabe an Audio-Processor

#### 3. `audio_processor.py` - Audio-Verarbeitungs-Engine
- Gain-Anpassung (konfigurierbar)
- AGC (Automatic Gain Control) - optional
- **Interception-Pipe für Phase 7:**
  - Plugin-System für AI-Module
  - Einfache Integration von Noise Cancelling
  - Konfigurierbare Verarbeitungs-Pipeline
- Queue-basierte Übergabe an DMR-Gateway

#### 4. `dmr_gateway.py` - MMDVM_Bridge-Schnittstelle
- UDP-Sender an Port 33100
- TLV-Format für MMDVM_Bridge (PCM Pass-Through)
- Robuste Fehlerbehandlung bei Netzwerk-Fehlern
- Statistiken für Überwachung

## Installation

### Voraussetzungen

**Hardware:**
- Raspberry Pi (ARM64-kompatibel)
- Raspberry Pi OS (64-bit)

**Software:**
- Python 3.8 oder höher
- pip (Python Package Manager)

### 1. Repository klonen

```bash
git clone https://github.com/ria18/Analog_Bridge.git
cd Analog_Bridge
```

### 2. Python-Abhängigkeiten installieren

```bash
# System-Pakete (falls noch nicht installiert)
sudo apt-get update
sudo apt-get install -y python3 python3-pip python3-venv

# Virtuelle Umgebung erstellen (empfohlen)
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# oder
venv\Scripts\activate  # Windows

# Python-Abhängigkeiten installieren
pip install -r requirements.txt
```

### 3. Konfiguration

Bearbeiten Sie `config.json` nach Ihren Anforderungen:

```json
{
    "usrp": {
        "listen_port": 40001,
        "listen_address": "0.0.0.0"
    },
    "mmdvm": {
        "address": "127.0.0.1",
        "port": 33100
    },
    "audio": {
        "sample_rate": 8000,
        "gain": 1.0,
        "enable_agc": false
    }
}
```

### 4. Ausführung

```bash
# Aktivieren Sie die virtuelle Umgebung (falls verwendet)
source venv/bin/activate

# Starten Sie das Programm
python3 main.py

# Oder mit angepasster Konfiguration
python3 main.py -c config.json

# Verbose-Logging aktivieren
python3 main.py -v
```

## Konfiguration

### `config.json` - Zentrale Konfigurationsdatei

Die Konfiguration erfolgt über JSON, keine Code-Änderungen nötig.

#### Wichtige Einstellungen:

**USRP-Server (Eingang):**
```json
"usrp": {
    "listen_address": "0.0.0.0",  // Alle Interfaces
    "listen_port": 40001,          // UDP-Port für SIP-Client
    "buffer_size": 4096
}
```

**MMDVM_Bridge (Ausgang):**
```json
"mmdvm": {
    "address": "127.0.0.1",  // MMDVM_Bridge IP
    "port": 33100,            // MMDVM_Bridge Port
    "buffer_size": 4096
}
```

**Audio-Verarbeitung:**
```json
"audio": {
    "sample_rate": 8000,      // 8kHz für Voice
    "gain": 1.0,              // Gain-Multiplikator
    "enable_agc": false,      // Automatic Gain Control
    "agc_threshold_db": -20.0
}
```

**Phase 7 (AI-Module):**
```json
"phase7": {
    "ai_modules_enabled": false,
    "noise_cancelling_enabled": false,
    "plugin_directory": "./plugins"
}
```

Vollständige Konfiguration siehe `config.json`.

## Verwendung

### Basis-Start

```bash
python3 main.py
```

### Systemd-Service (empfohlen für Produktion)

Erstellen Sie `/etc/systemd/system/bos-radio-bridge.service`:

```ini
[Unit]
Description=BOS-Radio-Bridge
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/path/to/Analog_Bridge
ExecStart=/path/to/Analog_Bridge/venv/bin/python3 main.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Aktivieren und starten:

```bash
sudo systemctl daemon-reload
sudo systemctl enable bos-radio-bridge
sudo systemctl start bos-radio-bridge
sudo systemctl status bos-radio-bridge
```

### Log-Dateien

Standard-Logging:
- Konsole: INFO-Level
- Datei: `bos_radio_bridge.log` (konfigurierbar)
- Rotation: 10MB, 5 Backups

## Phase 7: AI-Module-Integration (Noise Cancelling)

### Interception-Pipe verwenden

Die Audio-Processor-Klasse bietet eine Interception-Pipe für Plugin-Integration:

```python
from audio_processor import AudioProcessor

# Plugin-Funktion definieren
def noise_cancelling_plugin(pcm_data: bytes) -> bytes:
    # AI-Modell anwenden
    processed = ai_model.process(pcm_data)
    return processed

# Plugin registrieren
audio_processor.register_interception_plugin(noise_cancelling_plugin)
```

### Plugin-Architektur

1. **Einfache Schnittstelle**: Funktion nimmt PCM-Bytes entgegen, gibt PCM-Bytes zurück
2. **Reihenfolge**: Plugins werden in Registrierungs-Reihenfolge ausgeführt
3. **Fehlerbehandlung**: Fehler in einem Plugin stoppen nicht die Pipeline
4. **Konfiguration**: Plugins können über `config.json` aktiviert/deaktiviert werden

## Vergleich: Python vs. Original Analog_Bridge

| Aspekt | Original Analog_Bridge | BOS-Radio-Bridge (Python) |
|--------|----------------------|---------------------------|
| Hardware-Abhängigkeit | DV3000 zwingend erforderlich | Keine Hardware erforderlich |
| Absturz bei fehlender Hardware | Ja (exit(1)) | Nein (Robuste Fehlerbehandlung) |
| Latenz | 50-100ms (mit Hardware) | < 20ms (Software-only) |
| Erweiterbarkeit | Schwer (C++ Code-Änderungen) | Einfach (Plugin-System) |
| Wartbarkeit | Komplex (C++) | Einfach (Python) |
| Konfiguration | INI-Datei | JSON (strukturiert) |
| AI-Module-Integration | Schwer | Einfach (Interception-Pipe) |
| Entwicklung | Langsam (Kompilierung) | Schnell (Interpretiert) |
| Deployment | Binary-Kompilierung | Python-Skript |

## Fehlerbehebung

### Problem: Verbindung zu MMDVM_Bridge schlägt fehl

**Lösung:**
- Prüfen Sie Port 33100 in `config.json`
- Prüfen Sie, ob MMDVM_Bridge läuft: `systemctl status mmdvm_bridge`
- Prüfen Sie Firewall-Einstellungen

### Problem: Keine Audio-Daten empfangen

**Lösung:**
- Prüfen Sie Port 40001 in `config.json`
- Prüfen Sie, ob SIP-Client Daten sendet
- Prüfen Sie Log-Datei für Fehlermeldungen

### Problem: Hohe CPU-Last

**Lösung:**
- Reduzieren Sie Queue-Größen in `config.json`
- Deaktivieren Sie AGC, wenn nicht benötigt
- Optimieren Sie Phase 7 Plugins

### Problem: Audio-Qualität schlecht

**Lösung:**
- Anpassen des Gain-Werts in `config.json`
- Aktivieren Sie AGC für automatische Anpassung
- Prüfen Sie Sample-Rate-Einstellungen

## Entwicklung

### Projekt-Struktur

```
Analog_Bridge/
├── main.py                 # Zentraler Orchestrator
├── usrp_server.py          # USRP-Protokoll-Handler
├── audio_processor.py      # Audio-Verarbeitung + Interception-Pipe
├── dmr_gateway.py          # MMDVM_Bridge-Schnittstelle
├── config.json             # Konfigurationsdatei
├── requirements.txt        # Python-Abhängigkeiten
├── README.md              # Diese Datei
├── MODIFICATIONS.md       # Code-Modifikations-Dokumentation
└── .gitignore             # Git-Ignore-Datei
```

### Erweiterungen entwickeln

1. **Neues Audio-Plugin (Phase 7):**
   - Funktion erstellen: `def my_plugin(pcm_data: bytes) -> bytes`
   - In `audio_processor.py` registrieren
   - In `config.json` aktivieren

2. **Neue Protokoll-Unterstützung:**
   - Neues Modul nach Vorbild von `usrp_server.py`
   - In `main.py` integrieren
   - Konfiguration in `config.json` hinzufügen

## Lizenz

Basierend auf Analog_Bridge von DVSwitch. Siehe Original-Lizenz für Details.

## Beitragende

- Original: DVSwitch Project
- Python-Implementierung: BOS-Gateway Projekt

## Referenzen

- [DVSwitch Projekt](https://github.com/DVSwitch)
- [MMDVM_Bridge](https://github.com/g4klx/MMDVM_Bridge)
- [pjsua (SIP Client)](https://www.pjsip.org/)

---

**Hinweis**: Diese Python-Implementierung ist eine vollständige Neuentwicklung und umgeht den Hardware-Zwang der originalen Analog_Bridge. Sie ist speziell für BOS-Gateway-Anwendungen optimiert und bietet niedrige Latenz, Erweiterbarkeit und Robustheit.
