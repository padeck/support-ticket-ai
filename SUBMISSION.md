# AI-gestützte Verarbeitung von Support-Anfragen — Abgabe

## Links

- **Quellcode:** https://github.com/padeck/support-ticket-ai
- **Live-API:** https://support-ticket-ai-production.up.railway.app
- **API-Doku (Swagger):** https://support-ticket-ai-production.up.railway.app/docs
- **Health-Check:** https://support-ticket-ai-production.up.railway.app/health

## Kurzbeschreibung

Die Anwendung nimmt eine Support-Anfrage über eine REST-API entgegen, analysiert sie automatisiert und bestimmt **Kategorie, Priorität, zuständiges Team, Zusammenfassung** sowie den **Status**. Kritische Anfragen (z. B. Produktionssystem-Ausfall) werden automatisch als `manual_review_required` gekennzeichnet. Das Ergebnis wird persistent in einer PostgreSQL-Datenbank gespeichert und ist über weitere Endpunkte abrufbar bzw. änderbar.

### Beispiel (Produktivsystem-Ausfall)

```json
POST /api/tickets  {"request": "Seit heute Morgen ist das Produktivsystem nicht erreichbar."}
→ {
  "ticketId": "T-9ba102",
  "category": "incident",
  "priority": "critical",
  "assignedTeam": "platform-operations",
  "summary": "Seit heute Morgen ist das Produktivsystem nicht erreichbar.",
  "status": "manual_review_required"
}
```

## API-Endpunkte

| Methode | Pfad | Zweck |
|---|---|---|
| `POST` | `/api/tickets` | Anfrage einreichen → KI-Analyse → speichern |
| `GET` | `/api/tickets?status=&category=` | Liste mit Filtern |
| `GET` | `/api/tickets/{id}` | Einzelticket abrufen |
| `PATCH` | `/api/tickets/{id}` | Status aktualisieren |
| `GET` | `/health` | Health-Check (DB-Ping) |

## Technologien

- **Python 3.11 / FastAPI** (API)
- **SQLAlchemy 2 + PostgreSQL** (Railway), SQLite als lokaler Fallback
- **AI:** OpenAI-API als primäres LLM; automatischer Fallback auf lokales Ollama (`qwen3:14b`) und eine **simulierte, nachvollziehbare Rule-Engine** (gewichtetes Keyword-Scoring)
- **Deployment:** Docker + Railway
- **CI:** GitHub Actions (`pytest`, 24 Tests)

## Wichtigste Annahmen & Entscheidungen

- **AI-Provider-Kaskade** (`auto`): OpenAI → Ollama → Regel-Engine. Damit ist die App auch ohne API-Key voll funktionsfähig und deterministisch.
- **Ticket-ID** als kurzes UUID (`T-<hex>`) statt sequenzieller Nummer → vermeidet Race Conditions bei parallelen Requests.
- **`manual_review_required`** wird gesetzt, wenn `category == "incident"` **und** `priority == "critical"` ist.
- **DB-Fallback:** ungültige/fehlende `DATABASE_URL` fällt auf SQLite zurück, damit die App nie beim Start crasht.
- **Konfiguration** rein über Environment-Variablen (kein Secret im Repo; `OPENAI_API_KEY` liegt nur als Railway-Env-Variable).
- **Sicherheit/Qualität:** optionaler `X-API-Key`-Schutz (deaktiviert wenn ungesetzt), Rate-Limiting (30 Req/min/IP), JSON-Structured Logging mit Request-ID.

## Eingesetzte Hilfsmittel

- **Claude (opencode)** für Implementierung und Deployment
- **Ollama** (`qwen3:14b`) für lokale LLM-Analyse (optional)

## Punkte, die ich mit mehr Zeit noch umgesetzt hätte

- Vollständige Authentifizierung/Autorisierung (JWT/Rollen) statt einfacher API-Key-Prüfung
- Cursor-basierte Pagination + Sortierung
- Webhook-Benachrichtigung (z. B. Slack/Teams) bei `manual_review_required`
- Einfaches Dashboard/Frontend
- DB-Migrationen mit Alembic
- OpenTelemetry/Monitoring & Metriken
- Redis-basiertes Rate-Limiting für Multi-Instance
- SLA-/Eskalations-Workflows mit automatischen Status-Übergängen
- CI/CD mit Deployment-Stage (Railway-API) statt nur Tests
