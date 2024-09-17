# VoiceFlow - AI Voice Agent Platform

Production-ready AI voice agents for inbound customer support and outbound lead generation using Twilio, ElevenLabs, and OpenAI.

## Features

### Inbound Agent (Customer Support)
- Real-time call handling and transcription
- Intelligent conversation routing
- Sentiment analysis for escalation detection
- Customer context memory
- Call recording and analytics

### Outbound Agent (Lead Generation)
- Automated lead qualification calls
- Dynamic conversation flows
- Calendar integration (appointment booking)
- Lead scoring algorithm
- CRM sync (HubSpot/Salesforce)
- Voicemail detection and follow-up

## Tech Stack

**Backend:**
- Python 3.11+
- FastAPI
- PostgreSQL
- Redis (caching/session management)
- OpenAI GPT-4
- ElevenLabs (voice synthesis)
- Twilio (call handling)

**Frontend:**
- Next.js 14
- React 18
- TailwindCSS
- Recharts (analytics)

**Integrations:**
- Twilio API
- ElevenLabs API
- OpenAI API
- Make.com / Zapier webhooks

## Project Structure

```
voiceflow/
├── backend/
│   ├── core/
│   │   ├── llm_service.py          # OpenAI integration
│   │   ├── voice_service.py        # ElevenLabs integration
│   │   ├── twilio_service.py       # Twilio call handling
│   │   └── memory_manager.py       # Context management
│   ├── inbound/
│   │   ├── agent.py                # Inbound agent logic
│   │   ├── models.py               # Database models
│   │   └── routes.py               # API endpoints
│   ├── outbound/
│   │   ├── agent.py                # Outbound agent logic
│   │   ├── models.py               # Database models
│   │   └── routes.py               # API endpoints
│   ├── main.py                     # FastAPI app
│   ├── database.py                 # DB configuration
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   ├── pages/
│   │   └── lib/
│   ├── package.json
│   └── tsconfig.json
├── docker-compose.yml
├── Dockerfile
├── .env.example
├── pyproject.toml
└── README.md
```

## Quick Start

### Prerequisites
- Python 3.11+
- Node.js 18+
- Docker & Docker Compose
- API Keys: OpenAI, ElevenLabs, Twilio

### Backend Setup

```bash
cd backend
uv sync
cp .env.example .env
# Edit .env with your API keys
docker-compose up
uv run python main.py
```

### Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

Visit `http://localhost:3000` for dashboard.

## API Examples

### Inbound Agent

```bash
# Webhook for incoming calls
POST /api/inbound/calls
{
  "from": "+1234567890",
  "to": "+0987654321",
  "call_sid": "CA123456"
}

# Get call transcript
GET /api/inbound/calls/{call_id}/transcript
```

### Outbound Agent

```bash
# Start outbound campaign
POST /api/outbound/campaigns
{
  "name": "Q4 Lead Generation",
  "leads": [...],
  "script": "...",
  "schedule": "daily"
}

# Get campaign metrics
GET /api/outbound/campaigns/{campaign_id}/metrics
```

## Features in Action

### Call Flow (Inbound)
1. Incoming call to Twilio number
2. Webhook triggers VoiceFlow agent
3. Real-time transcription and LLM processing
4. Agent responds via ElevenLabs voice
5. Sentiment detected → escalate if needed
6. Call logged with transcript and analytics

### Campaign Flow (Outbound)
1. Campaign scheduled
2. Agent calls lead
3. Dynamic conversation based on responses
4. Lead qualified and scored
5. Calendar synced if appointment requested
6. Follow-up email triggered
7. Analytics updated

## Dashboard Features

- Real-time call monitoring
- Call transcripts and recordings
- Agent performance metrics
- Campaign analytics
- Lead scoring insights
- Sentiment trends
- Cost tracking

## Performance Metrics

- Average call duration
- Resolution rate
- Customer satisfaction (CSAT)
- Lead qualification rate
- Appointment booking rate
- Cost per qualified lead

## Security

- End-to-end encrypted calls
- PII masking in logs
- Role-based access control
- API rate limiting
- Audit trails

## Deployment

Ready for AWS deployment:
- ECS for containerized services
- RDS for PostgreSQL
- ElastiCache for Redis
- S3 for call recordings
- CloudFront for dashboard CDN

## Testing

### Run All Tests
```bash
uv run pytest
```

### Run with Coverage
```bash
uv run pytest --cov=backend --cov-report=html
```

### Run Unit Tests Only
```bash
uv run pytest tests/test_inbound_agent.py -v
```

### Run Integration Tests Only
```bash
uv run pytest tests/test_inbound_routes.py -v
```

### Run Async Tests
```bash
uv run pytest --asyncio-mode=auto -v
```

### Test Coverage Report
```bash
uv run pytest --cov=backend --cov-report=term-missing
```

## Documentation

- [Setup Guide](./docs/SETUP.md)
- [API Documentation](./docs/API.md)
- [Agent Configuration](./docs/AGENTS.md)
- [Deployment Guide](./docs/DEPLOYMENT.md)

## License

MIT

## Contact

For inquiries about voice agent implementation, visit [voiceflow-demo.com](https://voiceflow-demo.com)
