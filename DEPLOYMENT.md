# BOS-Radio-Bridge Deployment auf Raspberry Pi 5

## SSH-Verbindung zum Raspberry Pi

### Verbindung herstellen

```bash
# SSH-Verbindung zum Raspberry Pi (192.168.178.29)
ssh pi@192.168.178.29

# Oder mit Benutzername (falls anders)
ssh <benutzername>@192.168.178.29

# Bei erstem Verbindungsaufbau:
# - Fingerprint wird angezeigt
# - Mit "yes" bestätigen
```

### SSH-Konfiguration (optional)

Fügen Sie in `~/.ssh/config` hinzu:

```
Host pi5
    HostName 192.168.178.29
    User pi
    Port 22
```

Dann können Sie einfach verwenden:
```bash
ssh pi5
```

### SSH-Key-basierte Authentifizierung (empfohlen)

```bash
# Auf Ihrem lokalen PC (falls noch nicht vorhanden)
ssh-keygen -t ed25519 -C "your_email@example.com"

# Public Key zum Pi kopieren
ssh-copy-id pi@192.168.178.29

# Dann können Sie ohne Passwort verbinden
ssh pi@192.168.178.29
```

## Installation auf Raspberry Pi 5

### 1. Code zum Raspberry Pi übertragen

**Option A: Git (empfohlen)**
```bash
# Auf dem Raspberry Pi
cd ~
git clone https://github.com/ria18/Analog_Bridge.git
cd Analog_Bridge
```

**Option B: SCP (von lokalem PC)**
```bash
# Auf Ihrem lokalen PC (Windows/PowerShell)
scp -r K:\NexoVibe\Analog_bridge pi@192.168.178.29:~/

# Oder nur die Python-Dateien
scp *.py config.json requirements.txt install.sh pi@192.168.178.29:~/bos-radio-bridge/
```

**Option C: SFTP**
```bash
# Mit WinSCP oder FileZilla
# Verbinden zu: sftp://192.168.178.29
# Benutzername: pi
# Dateien hochladen
```

### 2. Installation auf dem Raspberry Pi

**Via SSH verbinden:**
```bash
ssh pi@192.168.178.29
```

**Installations-Skript ausführen:**
```bash
cd ~/Analog_Bridge  # oder cd ~/bos-radio-bridge
chmod +x install.sh
sudo ./install.sh
```

**Oder manuelle Installation:**
```bash
# System-Updates
sudo apt-get update
sudo apt-get upgrade -y

# Python-Abhängigkeiten
sudo apt-get install -y python3 python3-pip python3-venv python3-dev

# NumPy installieren
pip3 install --upgrade pip
pip3 install numpy

# Code-Verzeichnis erstellen
sudo mkdir -p /opt/bos-radio-bridge
sudo cp *.py config.json /opt/bos-radio-bridge/
sudo chown -R pi:pi /opt/bos-radio-bridge
cd /opt/bos-radio-bridge
```

### 3. Konfiguration für MMDVMHost

**MMDVMHost Konfiguration (`/opt/MMDVMHost/MMDVM.ini`):**

```ini
[Network]
Port=62031
Address=127.0.0.1

[Transparent Data]
Enable=1
RemoteAddress=127.0.0.1
RemotePort=33100
LocalPort=33101
```

**BOS-Radio-Bridge Konfiguration (`/opt/bos-radio-bridge/config.json`):**

```json
{
    "mmdvm": {
        "address": "127.0.0.1",
        "port": 33100,
        "protocol": "TLV",
        "buffer_size": 4096
    },
    "mmdvm_rx": {
        "listen_address": "0.0.0.0",
        "rx_port": 33101,
        "protocol": "TLV",
        "buffer_size": 4096
    },
    "usrp": {
        "listen_address": "0.0.0.0",
        "listen_port": 40001,
        "protocol": "USRP",
        "header_size": 32,
        "buffer_size": 4096
    },
    "usrp_client": {
        "target_address": "127.0.0.1",
        "target_port": 40001,
        "protocol": "USRP",
        "buffer_size": 4096
    }
}
```

### 4. Systemd Service einrichten

**Service-Datei erstellen:**
```bash
sudo nano /etc/systemd/system/bos-bridge.service
```

**Inhalt:**
```ini
[Unit]
Description=BOS-Radio-Bridge - Bidirectional Python Radio Bridge
After=network.target mmdvmhost.service
Wants=network-online.target

[Service]
Type=simple
User=pi
Group=pi
WorkingDirectory=/opt/bos-radio-bridge
ExecStart=/usr/bin/python3 /opt/bos-radio-bridge/main.py
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal
SyslogIdentifier=bos-bridge

# Security settings
NoNewPrivileges=true
PrivateTmp=true

# Resource limits
LimitNOFILE=4096

[Install]
WantedBy=multi-user.target
```

**Service aktivieren:**
```bash
sudo systemctl daemon-reload
sudo systemctl enable bos-bridge
sudo systemctl start bos-bridge
```

### 5. Service-Status prüfen

```bash
# Status anzeigen
sudo systemctl status bos-bridge

# Logs anzeigen
sudo journalctl -u bos-bridge -f

# Logs der letzten 100 Zeilen
sudo journalctl -u bos-bridge -n 100

# Service neu starten
sudo systemctl restart bos-bridge

# Service stoppen
sudo systemctl stop bos-bridge
```

## Netzwerk-Konfiguration

### Ports die geöffnet sein müssen:

- **Port 40001**: USRP-Server (von pjsua/SIP-Client)
- **Port 33100**: DMR-Gateway TX (an MMDVMHost)
- **Port 33101**: MMDVM Receiver RX (von MMDVMHost)

**Port-Status prüfen:**
```bash
# Prüfen ob Ports offen sind
sudo netstat -tulpn | grep -E '40001|33100|33101'

# Oder mit ss
sudo ss -tulpn | grep -E '40001|33100|33101'
```

## Firewall-Konfiguration (falls aktiv)

```bash
# UFW Firewall (falls aktiviert)
sudo ufw allow 40001/udp
sudo ufw allow 33100/udp
sudo ufw allow 33101/udp

# Status prüfen
sudo ufw status
```

## Troubleshooting

### Problem: SSH-Verbindung schlägt fehl

```bash
# Ping testen
ping 192.168.178.29

# Port 22 prüfen
telnet 192.168.178.29 22

# SSH-Service prüfen (auf dem Pi)
sudo systemctl status ssh
```

### Problem: Service startet nicht

```bash
# Logs anzeigen
sudo journalctl -u bos-bridge -n 50

# Manuell starten (für Debugging)
cd /opt/bos-radio-bridge
python3 main.py

# Python-Pfad prüfen
which python3
python3 --version
```

### Problem: Port bereits belegt

```bash
# Prozess finden der Port verwendet
sudo lsof -i :40001
sudo lsof -i :33100
sudo lsof -i :33101

# Prozess beenden
sudo kill -9 <PID>
```

### Problem: MMDVMHost-Verbindung schlägt fehl

```bash
# Prüfen ob MMDVMHost läuft
sudo systemctl status mmdvmhost

# MMDVMHost-Logs prüfen
sudo journalctl -u mmdvmhost -f

# Port-Verbindung testen
nc -u -v 127.0.0.1 33100
```

## Log-Dateien

**Service-Logs:**
```bash
sudo journalctl -u bos-bridge -f
```

**Anwendungs-Logs:**
```bash
# Log-Datei (wenn konfiguriert)
tail -f /opt/bos-radio-bridge/bos_radio_bridge.log
```

## System-Informationen

**Raspberry Pi Info:**
```bash
# CPU-Info
cat /proc/cpuinfo | grep Model

# OS-Version
cat /etc/os-release

# Python-Version
python3 --version

# NumPy-Version
python3 -c "import numpy; print(numpy.__version__)"
```

## Nützliche Befehle

```bash
# Alle Python-Prozesse anzeigen
ps aux | grep python

# Service-Status aller Services
systemctl list-units --type=service | grep -E 'bos|mmdvm'

# Netzwerk-Verbindungen
sudo netstat -tulpn | grep python

# System-Ressourcen
htop
# oder
top
```

## Remote-Verwaltung

**Von lokalem PC (Windows) via SSH:**

```powershell
# PowerShell
ssh pi@192.168.178.29

# Service-Status prüfen
ssh pi@192.168.178.29 "sudo systemctl status bos-bridge"

# Logs anzeigen
ssh pi@192.168.178.29 "sudo journalctl -u bos-bridge -n 50"

# Service neu starten
ssh pi@192.168.178.29 "sudo systemctl restart bos-bridge"
```

## Zusammenfassung

1. **SSH-Verbindung**: `ssh pi@192.168.178.29`
2. **Code übertragen**: Git, SCP oder SFTP
3. **Installation**: `sudo ./install.sh` oder manuell
4. **Konfiguration**: `config.json` für MMDVMHost anpassen
5. **Service starten**: `sudo systemctl start bos-bridge`
6. **Logs prüfen**: `sudo journalctl -u bos-bridge -f`

Das Programm läuft **direkt auf dem Raspberry Pi 5** und kommuniziert mit MMDVMHost über die Ports 33100 (TX) und 33101 (RX).

