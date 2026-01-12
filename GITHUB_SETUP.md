# GitHub Repository Setup

## Repository erstellen

1. Gehen Sie zu: https://github.com/ria18
2. Klicken Sie auf "New" oder "+" → "New repository"
3. Repository-Name: `Analog_Bridge`
4. Beschreibung (optional): "BOS-Radio-Bridge - Modified Analog_Bridge for software-only operation"
5. Sichtbarkeit: Public oder Private (nach Bedarf)
6. **WICHTIG**: Lassen Sie alle Optionen leer (keine README, .gitignore oder Lizenz)
7. Klicken Sie auf "Create repository"

## Code hochladen

Nach dem Erstellen des Repositories führen Sie diese Befehle aus:

```bash
# Stellen Sie sicher, dass Sie im richtigen Verzeichnis sind
cd K:\NexoVibe\Analog_bridge

# Pushen Sie den Code
git push -u origin main
```

Falls Sie nach Authentifizierung gefragt werden:
- Verwenden Sie einen Personal Access Token (PAT) statt eines Passworts
- Oder verwenden Sie GitHub CLI (`gh auth login`)

## Alternativ: GitHub CLI verwenden

Falls GitHub CLI installiert ist:

```bash
gh repo create ria18/Analog_Bridge --public --source=. --remote=origin --push
```

