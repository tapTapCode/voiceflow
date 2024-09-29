# VoiceFlow Testing Documentation

## Overview

VoiceFlow includes comprehensive automated tests for all core functionality. Tests are organized into unit tests and integration tests using pytest.

## Test Structure

```
tests/
├── conftest.py              # Shared fixtures and configuration
├── test_inbound_agent.py    # Unit tests for agent logic
├── test_inbound_routes.py   # Integration tests for API
└── __init__.py
```

## Running Tests

### Quick Start
```bash
# Install dependencies (including dev)
uv sync

# Run all tests
uv run pytest

# Run with coverage report
uv run pytest --cov=backend --cov-report=html
```

### Specific Test Suites

```bash
# Unit tests only
uv run pytest tests/test_inbound_agent.py -v

# Integration tests only
uv run pytest tests/test_inbound_routes.py -v

# Single test
uv run pytest tests/test_inbound_agent.py::test_sentiment_analysis_positive -v

# Tests matching pattern
uv run pytest -k "escalation" -v
```

### Advanced Options

```bash
# Stop on first failure
uv run pytest -x

# Show print statements
uv run pytest -s

# Parallel execution (requires pytest-xdist)
uv run pytest -n auto

# Generate HTML coverage report
uv run pytest --cov=backend --cov-report=html

# Generate XML for CI/CD
uv run pytest --cov=backend --cov-report=xml
```

## Test Coverage

### Unit Tests (test_inbound_agent.py)

**Sentiment Analysis:**
- ✅ `test_sentiment_analysis_positive` - Detect positive sentiment
- ✅ `test_sentiment_analysis_neutral` (implicit) - Handle neutral sentiment
- ✅ `test_escalation_detection` - Negative sentiment triggers escalation
- ✅ `test_call_quality_negative_sentiment` - Quality scoring

**Escalation Logic:**
- ✅ `test_escalation_detection` - Sentiment-based escalation
- ✅ `test_escalation_intent` - Intent-based escalation (keywords)
- ✅ `test_escalation_message_generation` - Message generation

**Conversation Flow:**
- ✅ `test_start_call` - Initialize call and greeting
- ✅ `test_process_customer_message` - Process and respond to messages
- ✅ `test_multiple_messages_conversation` - Multi-turn conversation
- ✅ `test_end_call` - Call termination and summary

**Quality & Analytics:**
- ✅ `test_call_quality_score` - Positive sentiment scoring
- ✅ `test_closure_message_success` - Resolution message generation
- ✅ `test_closure_message_unresolved` - Unresolved issue handling

**Total Unit Tests: 13**

### Integration Tests (test_inbound_routes.py)

**Health & Info:**
- ✅ `test_health_check` - System health endpoint
- ✅ `test_root_endpoint` - API documentation endpoint

**Call Management:**
- ✅ `test_start_call_success` - Initiate new call
- ✅ `test_start_call_duplicate_customer` - Handle repeat customers
- ✅ `test_process_message_success` - API message processing
- ✅ `test_process_message_not_found` - Error handling for missing call
- ✅ `test_end_call_success` - Call completion
- ✅ `test_get_call_success` - Retrieve call details
- ✅ `test_get_call_not_found` - Handle missing call

**Analytics & Feedback:**
- ✅ `test_list_calls` - Paginated call listing
- ✅ `test_list_calls_with_status_filter` - Call filtering
- ✅ `test_submit_feedback_success` - CSAT scoring
- ✅ `test_submit_feedback_invalid_score` - Validation
- ✅ `test_analytics_summary` - Dashboard metrics

**Total Integration Tests: 13**

## Fixtures (conftest.py)

### Mock Services
- `mock_llm_service` - Mock OpenAI GPT responses
- `mock_voice_service` - Mock ElevenLabs synthesis
- `mock_twilio_service` - Mock Twilio API

### Data & Sessions
- `inbound_agent` - Fresh agent instance
- `db_session` - In-memory SQLite database
- `sample_call_data` - Test call parameters
- `sample_customer_data` - Test customer info
- `mock_env_vars` - Environment variable mocks

## Test Data

### Sample Sentiment Values
- Positive: score 0.7-0.9
- Neutral: score 0.4-0.6
- Negative: score 0.1-0.3

### Sample Call SIDs
- Format: `CA{random_alphanumeric}`
- Example: `CA123456789abcdef`

### Sample Phone Numbers
- Customer: `+1234567890`
- Agent: `+0987654321`

## CI/CD Integration

### GitHub Actions Example
```yaml
name: Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: "3.11"
      - run: pip install uv
      - run: uv sync
      - run: uv run pytest --cov=backend --cov-report=xml
      - uses: codecov/codecov-action@v3
```

## Test Quality Metrics

**Target Coverage:**
- Overall: >80%
- core/: >90%
- inbound/: >85%
- routes: >80%

**To Check Current Coverage:**
```bash
uv run pytest --cov=backend --cov-report=term-missing
```

## Debugging Tests

### Enable Logging
```bash
uv run pytest -v -s --log-cli-level=DEBUG
```

### Stop on First Failure
```bash
uv run pytest -x -v
```

### Run Last Failed Tests
```bash
uv run pytest --lf
```

### Interactive Debugging
```python
# Add in test
import pdb; pdb.set_trace()

# Then run:
uv run pytest -s test_file.py::test_function
```

## Adding New Tests

### Template
```python
@pytest.mark.asyncio
async def test_new_feature():
    """Test description."""
    # Setup
    agent = InboundSupportAgent()
    
    # Execute
    result = await agent.some_method()
    
    # Assert
    assert result is not None
    assert "expected" in result
```

### Best Practices
1. Use descriptive test names: `test_<feature>_<condition>_<outcome>`
2. Test one thing per test function
3. Use fixtures for common setup
4. Mock external APIs and services
5. Test both success and failure paths
6. Add docstrings explaining the test

## Common Issues

### Issue: Async Test Not Running
**Solution:** Ensure `@pytest.mark.asyncio` decorator is present

### Issue: Database Session Errors
**Solution:** Use provided `db_session` fixture, not `SessionLocal()`

### Issue: Mock Not Patching
**Solution:** Check patch path matches import location exactly

### Issue: Import Errors
**Solution:** Ensure running from project root with `uv run pytest`

## Performance

**Expected Test Execution Time:**
- Unit tests: ~2-3 seconds
- Integration tests: ~3-5 seconds
- Full suite: ~5-8 seconds

To check:
```bash
uv run pytest --durations=10
```

## Contact & Support

For test-related issues, check:
1. Test documentation above
2. Code comments in test files
3. Test fixtures in conftest.py
4. Issue tracker on GitHub
