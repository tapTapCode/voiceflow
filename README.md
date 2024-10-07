# Learning: Voice AI Agents Experiment

**This is a learning project** - I built this to understand how voice AI agents work with Twilio, ElevenLabs, and OpenAI. It's experimental code, not production-ready.

**What I was learning**: How to handle real-time phone calls with AI, voice synthesis, and conversation state management. Wanted to see if I could build something like those AI receptionist services.

## What I Built

- **Inbound calls**: AI answers phone, transcribes speech, generates response, speaks back
- **Outbound campaigns**: Automated calling with lead qualification
- **Basic dashboard**: See active calls, transcripts, simple analytics
- **Twilio integration**: Webhooks for call events, media streaming
- **Voice synthesis**: ElevenLabs for realistic voice (better than Twilio's default)

## Stack

- **Backend**: Python + FastAPI
- **Telephony**: Twilio
- **Voice**: ElevenLabs API
- **LLM**: OpenAI GPT-4
- **Database**: PostgreSQL + Redis for session state
- **Frontend**: Next.js + Tailwind

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

```bash
cd backend
uv sync
cp .env.example .env
# Add your API keys
uv run python main.py
```

## What I Learned

### Real-time Voice Pipeline
1. Twilio receives call → webhook to my server
2. Stream audio chunks to transcription service (I used OpenAI's Whisper API)
3. Send transcript to GPT-4 for response generation
4. Use ElevenLabs to synthesize voice
5. Stream audio back to Twilio

### Challenges I Hit
- **Latency**: Round-trip time (transcription → LLM → voice) was ~3-5 seconds. Too slow for natural conversation.
- **Interruptions**: Hard to detect when user starts speaking while AI is talking
- **Costs**: ElevenLabs + GPT-4 + Twilio adds up fast per minute of call
- **State management**: Keeping conversation context across multiple API calls was messy

### What I'd Do Differently
- Use Twilio's native speech recognition instead of Whisper (faster but less accurate)
- Implement streaming LLM responses (send chunks to voice synth as they arrive)
- Add websocket support for real-time dashboard updates
- Better error handling - right now failed calls just hang

## API Endpoints

- `POST /api/inbound/calls` - Twilio webhook for incoming calls
- `POST /api/outbound/campaigns` - Start a calling campaign
- `GET /api/inbound/calls/{id}/transcript` - Get call recording + transcript

## Environment Variables

```env
OPENAI_API_KEY=your_openai_key
ELEVENLABS_API_KEY=your_elevenlabs_key
TWILIO_ACCOUNT_SID=your_twilio_sid
TWILIO_AUTH_TOKEN=your_twilio_token
TWILIO_PHONE_NUMBER=your_twilio_number
```

## License

MIT - Experimental code, use at your own risk.

