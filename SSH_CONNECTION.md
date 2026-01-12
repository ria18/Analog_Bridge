# SSH-Verbindung zum Raspberry Pi 5

## Schnellstart

```bash
# Standard-Verbindung
ssh pi@192.168.178.29

# Bei erstem Verbindungsaufbau: Fingerprint mit "yes" bestätigen
```

## Detaillierte Anleitung

### Windows (PowerShell/CMD)

**PowerShell:**
```powershell
# SSH-Verbindung
ssh pi@192.168.178.29

# Mit explizitem Port
ssh -p 22 pi@192.168.178.29
```

**CMD:**
```cmd
ssh pi@192.168.178.29
```

**PuTTY (GUI):**
- Host Name: `192.168.178.29`
- Port: `22`
- Connection Type: `SSH`
- Klicken Sie auf "Open"

### Linux/Mac

```bash
# Standard-Verbindung
ssh pi@192.168.178.29

# Mit Verbose-Modus (für Debugging)
ssh -v pi@192.168.178.29
```

### Standard-Anmeldedaten

- **Benutzername**: `pi` (Standard für Raspberry Pi OS)
- **Passwort**: (Standard: `raspberry` - sollte geändert werden!)
- **IP-Adresse**: `192.168.178.29`
- **Port**: `22` (Standard SSH-Port)

## SSH-Konfiguration (empfohlen)

### SSH-Config-Datei erstellen

**Linux/Mac (`~/.ssh/config`):**
```
Host pi5
    HostName 192.168.178.29
    User pi
    Port 22
    IdentityFile ~/.ssh/id_rsa
```

**Windows (`C:\Users\<USERNAME>\.ssh\config`):**
```
Host pi5
    HostName 192.168.178.29
    User pi
    Port 22
```

**Dann einfach:**
```bash
ssh pi5
```

## SSH-Key-basierte Authentifizierung

### 1. SSH-Key generieren (auf lokalem PC)

**Windows (PowerShell):**
```powershell
ssh-keygen -t ed25519 -C "your_email@example.com"
# Speicherort: C:\Users\<USERNAME>\.ssh\id_ed25519
```

**Linux/Mac:**
```bash
ssh-keygen -t ed25519 -C "your_email@example.com"
```

### 2. Public Key zum Raspberry Pi kopieren

**Windows:**
```powershell
# Falls ssh-copy-id nicht verfügbar
type $env:USERPROFILE\.ssh\id_ed25519.pub | ssh pi@192.168.178.29 "cat >> .ssh/authorized_keys"
```

**Linux/Mac:**
```bash
ssh-copy-id pi@192.168.178.29
```

### 3. Manuelle Installation (Alternative)

```bash
# Auf lokalem PC: Public Key anzeigen
cat ~/.ssh/id_ed25519.pub

# Auf Raspberry Pi (via SSH):
mkdir -p ~/.ssh
chmod 700 ~/.ssh
nano ~/.ssh/authorized_keys
# Public Key einfügen
chmod 600 ~/.ssh/authorized_keys
```

**Dann können Sie sich ohne Passwort verbinden:**
```bash
ssh pi@192.168.178.29
```

## Troubleshooting

### Problem: "Connection refused"

**Lösung:**
```bash
# Prüfen ob SSH-Service läuft (auf dem Pi)
sudo systemctl status ssh

# SSH-Service starten (falls nicht aktiv)
sudo systemctl start ssh
sudo systemctl enable ssh
```

### Problem: "Host key verification failed"

**Lösung:**
```bash
# Bekannten Host-Key entfernen
ssh-keygen -R 192.168.178.29

# Oder in ~/.ssh/known_hosts die entsprechende Zeile löschen
```

### Problem: "Permission denied"

**Lösung:**
- Passwort prüfen
- Benutzername prüfen (möglicherweise nicht "pi")
- SSH-Key-Setup prüfen

### Problem: "Network unreachable"

**Lösung:**
```bash
# Ping testen
ping 192.168.178.29

# Netzwerk-Verbindung prüfen
# - Pi und PC im gleichen Netzwerk?
# - IP-Adresse korrekt?
# - Firewall blockiert?
```

### SSH-Service auf Raspberry Pi aktivieren

**Falls SSH nicht aktiv ist:**
```bash
# Via physischem Zugang oder VNC
sudo raspi-config
# -> Interface Options -> SSH -> Enable

# Oder direkt
sudo systemctl enable ssh
sudo systemctl start ssh
```

## SCP (Dateien übertragen)

### Von lokalem PC zum Raspberry Pi

**Windows (PowerShell):**
```powershell
# Einzelne Datei
scp file.py pi@192.168.178.29:~/

# Verzeichnis rekursiv
scp -r directory pi@192.168.178.29:~/
```

**Linux/Mac:**
```bash
# Einzelne Datei
scp file.py pi@192.168.178.29:~/

# Verzeichnis rekursiv
scp -r directory pi@192.168.178.29:~/
```

### Vom Raspberry Pi zum lokalem PC

```bash
scp pi@192.168.178.29:~/file.txt ./
```

## SFTP (Alternativ zu SCP)

```bash
# SFTP-Verbindung
sftp pi@192.168.178.29

# In SFTP-Shell:
put file.py              # Hochladen
get file.py              # Herunterladen
cd directory             # Verzeichnis wechseln
ls                       # Dateien auflisten
quit                     # Beenden
```

**Windows GUI-Tools:**
- **WinSCP**: https://winscp.net/
- **FileZilla**: https://filezilla-project.org/

## Port-Weiterleitung (falls nötig)

**Lokale Port-Weiterleitung:**
```bash
ssh -L 40001:localhost:40001 pi@192.168.178.29
```

**Remote Port-Weiterleitung:**
```bash
ssh -R 40001:localhost:40001 pi@192.168.178.29
```

## Automatisierung

### Bash-Skript für häufige Aufgaben

**`connect-pi.sh`:**
```bash
#!/bin/bash
ssh pi@192.168.178.29 "$@"
```

**Verwendung:**
```bash
chmod +x connect-pi.sh
./connect-pi.sh "sudo systemctl status bos-bridge"
```

### PowerShell-Skript (Windows)

**`Connect-Pi.ps1`:**
```powershell
param([string]$Command = "bash")

ssh pi@192.168.178.29 $Command
```

**Verwendung:**
```powershell
.\Connect-Pi.ps1 "sudo systemctl status bos-bridge"
```

## Sicherheit

### Passwort ändern

```bash
# Auf Raspberry Pi
passwd
```

### SSH-Konfiguration härten

**`/etc/ssh/sshd_config` (auf Raspberry Pi):**
```
PermitRootLogin no
PasswordAuthentication yes  # Für Key-basierte Auth auf "no" setzen
PubkeyAuthentication yes
```

**Nach Änderungen:**
```bash
sudo systemctl restart ssh
```

## Zusammenfassung

**Einfache Verbindung:**
```bash
ssh pi@192.168.178.29
```

**Mit SSH-Config:**
```bash
ssh pi5
```

**Dateien übertragen:**
```bash
scp -r directory pi@192.168.178.29:~/
```

**Service-Status prüfen (Remote):**
```bash
ssh pi@192.168.178.29 "sudo systemctl status bos-bridge"
```

