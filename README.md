# AI-gestützte Verarbeitung von Support-Anfragen

Eine kleine Anwendung, die eingehende Support-Anfragen automatisiert analysiert und verarbeitet. Sie nimmt eine Anfrage über eine REST-API entgegen, klassifiziert sie (Kategorie, Priorität, Team, Zusammenfassung), kennzeichnet kritische Fälle und speichert das Ergebnis in einer Datenbank.

## Live-Deployment

**API-URL:** https://support-ticket-ai-production.up.railway.app

- **Swagger-Docs:** https://support-ticket-ai-production.up.railway.app/docs
- **Health-Check:** https://support-ticket-ai-production.up.railway.app/health
- **Git-Repo:** https://github.com/padeck/support-ticket-ai

> Beispiel: `curl -X POST https://support-ticket-ai-production.up.railway.app/api/tickets -H "Content-Type: application/json" -d '{"request":"Seit heute Morgen ist das Produktivsystem nicht erreichbar."}'`

## Was die App macht

- **POST** einer Support-Anfrage → automatische Analyse → persistiertes Ticket als Ergebnis
- Eingehende Anfragen werden als `manual_review_required` markiert, wenn sie kritisch sind (z. B. Produktionssystem-Ausfall)
- Tickets können einzeln oder als Liste (mit Filtern) abgerufen, und deren Status aktualisiert werden

## Technologien

| Komponente | Technologie |
|---|---|
| Sprache | Python 3.11 (Docker) / 3.14 (lokal) |
| Framework | FastAPI |
| ORM | SQLAlchemy 2.x |
| Datenbank | PostgreSQL (Railway) / SQLite (lokal, Fallback) |
| AI | OpenAI API, Ollama (`qwen3:14b`), oder simulierte Rule-Engine |
| Testing | pytest |
| Deployment | Railway (Dockerfile) |

## Schnellstart (lokal)

```bash
cd support-ticket-ai
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Die API läuft dann auf `http://localhost:8000`. Die interaktive Swagger-Dokumentation findest du auf `http://localhost:8000/docs`.

> Hinweis: Ohne Konfiguration verwendet die App die **simulierte Rule-Engine** (kein externer API-Key nötig).

### Konfiguration

Alle Einstellungen erfolgen über Environment-Variablen (optional in einer lokalen `.env`-Datei):

| Variable | Default | Beschreibung |
|---|---|---|
| `AI_PROVIDER` | `auto` | `auto` \| `openai` \| `ollama` \| `simulated` |
| `OPENAI_API_KEY` | – | OpenAI-Key für echtes LLM (falls gesetzt → OpenAI als Primary) |
| `OLLAMA_URL` | `http://localhost:11434` | Lokale Ollama-Instanz |
| `OLLAMA_MODEL` | `qwen3:14b` | Ollama-Modellname |
| `DATABASE_URL` | `sqlite:///./local.db` | PostgreSQL-URL (Produktion) oder SQLite (lokal) |
| `API_KEY` | – | Optionaler `X-API-Key`-Schutz (nur aktiv, wenn gesetzt) |
| `RATE_LIMIT_PER_MINUTE` | `30` | Requests pro Minute pro IP |

Beispiel (lokale `.env`):

```bash
# AI provider: auto | openai | ollama | simulated
AI_PROVIDER=auto
OPENAI_API_KEY=sk-...
```

## API-Endpunkte

### 1. Ticket erstellen

```bash
curl -X POST http://localhost:8000/api/tickets \
  -H "Content-Type: application/json" \
  -d '{"request": "Mein Benutzerkonto ist gesperrt und ich kann mich nicht anmelden."}'
```

**Beispiel-Antwort:**
```json
{
  "ticketId": "T-a3f2b1",
  "category": "account_access",
  "priority": "medium",
  "assignedTeam": "identity-operations",
  "summary": "Mein Benutzerkonto ist gesperrt und ich kann mich nicht anmelden.",
  "status": "open",
  "aiProvider": "simulated",
  "createdAt": "2026-09-03T12:24:00"
}
```

> **`aiProvider`** gibt an, **welche Methode** den Fall tatsächlich klassifiziert hat: `openai`, `ollama` oder `simulated`. Dieses Feld wird zusammen mit dem Ticket dauerhaft in der Datenbank gespeichert.

### 2. Ticket abrufen

```bash
curl http://localhost:8000/api/tickets/T-a3f2b1
```

### 3. Alle Tickets (mit optionalen Filtern)

```bash
curl "http://localhost:8000/api/tickets?status=manual_review_required&category=incident"
```

### 4. Status aktualisieren

```bash
curl -X PATCH http://localhost:8000/api/tickets/T-a3f2b1 \
  -H "Content-Type: application/json" \
  -d '{"status": "resolved"}'
```

Erlaubte Statuswerte: `open`, `in_progress`, `resolved`, `manual_review_required`.

### 5. Health-Check

```bash
curl http://localhost:8000/health
```

## AI-Komponente: Provider-Kaskade

Die Analyse läuft in folgender Priorität:

1. **OpenAI** – falls `OPENAI_API_KEY` gesetzt ist (Modell `gpt-4o-mini`, temperatur 0, strukturiertes JSON-Output)
2. **Ollama** – falls ein lokales Ollama läuft (Standardmodell `qwen3:14b`)
3. **Simulierte Rule-Engine** – immer verfügbar, garantiert einen funktionierenden Fallback

**Robustes Fallback-Verhalten:** Schlägt ein Provider fehl (z. B. fehlendes OpenAI-Guthaben → HTTP 401/402, Timeout, oder Netzwerkfehler), wird automatisch der nächste Provider versucht. Die Anwendung stürzt dabei **nie** ab. Der letztlich verwendete Provider ist pro Ticket über das Feld `aiProvider` nachvollziehbar.

Der aktive Provider lässt sich über `AI_PROVIDER=auto|openai|ollama|simulated` steuern.

### Simulierte Rule-Engine (nachvollziehbar)

Die Rule-Engine nutzt **gewichtetes Keyword-Scoring**:

- **Kategorien** mit Keywords und Gewicht (z. B. `account_access`: "gesperrt", "anmelden", "login" × 3)
- **Priorität** mit Keywords und Gewicht (`critical`: "produktionssystem", "alle nutzer" × 5; `low`: "wie kann" × 2)
- **Team-Mapping** ist deterministisch aus der Kategorie abgeleitet

Die Logik ist vollständig in `app/ai_service.py` dokumentiert und unit-getestet.

**Manual-Review-Regel:** Ein Ticket wird mit `status="manual_review_required"` markiert, wenn `category == "incident"` **und** `priority == "critical"` ist.

## Deployment auf Railway

1. Repo auf GitHub pushen (z. B. `git push origin main`)
2. Auf [Railway.app](https://railway.app) → **New Project** → **Deploy from GitHub repo**
3. Optional: PostgreSQL-Datenbank als Service hinzufügen → `DATABASE_URL` wird automatisch gesetzt
4. Optional: Env-Variablen `OPENAI_API_KEY` oder `AI_PROVIDER` konfigurieren
5. Deploy startet automatisch (Dockerfile erkannt)

Das Projekt enthält eine `railway.json` mit Health-Check-Konfiguration.

## Tests

```bash
pytest -v
# 26 Tests: API-Endpunkte + Rule-Engine-Logik + Provider-Fallback
```

## Annahmen & Entscheidungen

- **Ticket-ID** als kryptographisch sicheres, kurzes UUID (`T-<hex>`) statt sequenzieller Nummer → vermeidet Race Conditions bei parallelen Requests
- **Optionaler API-Key-Schutz** (`X-API-Key` Header) über die Env-Variable `API_KEY` – nur aktiv, wenn gesetzt (für die Demo standardmäßig deaktiviert)
- **SQLite als lokaler Fallback**, PostgreSQL in Produktion – über `DATABASE_URL` konfigurierbar
- **In-Memory Rate Limiting** (kein Redis), 30 Requests/Minute/IP – ausreichend für die Demo
- **JSON-Structured Logging** mit Request-ID für jede Anfrage
- Einfache `create_all()`-Migration statt Alembic – bewusst pragmatisch für den Demo-Zweck
- Mehrsprachige Eingaben (deutsch/englisch) werden über die Keyword-Listen beider Sprachen unterstützt

## Eingesetzte Hilfsmittel

- **Claude (opencode)** – Implementierung
- **Ollama** mit lokalem `qwen3:14b` – als lokales LLM zur Analyse (optional)

## Punkte, die ich mit mehr Zeit noch umgesetzt hätte

- **Authentifizierung & Autorisierung** (JWT / Rollen) anstelle der einfachen API-Key-Prüfung
- **Pagination** mit Cursor-Basiertem Ansatz und Sortierung
- **Webhook-Benachrichtigung** bei `manual_review_required` (z. B. an Slack/Teams)
- **Einfaches Dashboard/Frontend** zur Ticket-Übersicht
- **DB-Migrationen mit Alembic** für produktionsreife Schema-Evolution
- **OpenTelemetry/Monitoring** + Metriken
- **Rate-Limiting mit Redis** für Multi-Instance-Deployments
- **Rate-Limit/Layer für LLM** mit Retry + Batch-Verarbeitung
- **Automatische Status-Workflows** (SLA-Zeiten, Eskalation)
- **CI/CD mit Deployment-Stage** (Railway API), nicht nur Tests
