# OpenAI Integration Setup

## Prerequisites

1. **OpenAI API Key**: Get your API key from [OpenAI Platform](https://platform.openai.com/api-keys)
2. **Python Package**: Install the OpenAI Python client

## Installation

```bash
# Install OpenAI client library
pip install openai
```

## Configuration

### Backend Setup

1. Set the environment variable in your `.env` file or system environment:

```bash
export OPENAI_API_KEY="sk-your-api-key-here"
export OPENAI_MODEL="gpt-4o"  # Optional, defaults to gpt-4o
```

2. For development, create a `.env` file in the `backend/` directory:

```env
# OpenAI Configuration
OPENAI_API_KEY=sk-your-api-key-here
OPENAI_MODEL=gpt-4o
```

3. If using Docker, add to `docker-compose.yml`:

```yaml
environment:
  - OPENAI_API_KEY=${OPENAI_API_KEY}
  - OPENAI_MODEL=gpt-4o
```

## Usage

### Chat Endpoint

The chat API is available at: `/api/chat/send`

**Request:**

```json
{
  "message": "Help me create a job",
  "conversation_history": [
    {"role": "user", "content": "Hi"},
    {"role": "assistant", "content": "Hello! How can I help?"}
  ],
  "model": "gpt-4o"
}
```

**Response:**

```json
{
  "response": "I'll help you create a job..."
}
```

## Features

- **AI Chat Assistant**: Get help with job creation, troubleshooting, and workflows
- **Conversation History**: Maintains context across multiple messages
- **Model Selection**: Support for GPT-4o and other OpenAI models
- **Context Attachment**: Allow attaching job metadata and templates to questions

## Troubleshooting

### API Key Not Configured
- Check that `OPENAI_API_KEY` environment variable is set
- Verify the key is valid at https://platform.openai.com/api-keys
- Check backend logs for configuration errors

### Connection Errors
- Verify internet connectivity
- Check firewall/proxy settings
- Ensure OpenAI API is accessible from your network

### Rate Limiting
- Monitor OpenAI API usage at https://platform.openai.com/account/usage
- Implement rate limiting on the backend if needed
- Check for quota limits on your OpenAI account

## Security Notes

- **Never commit** `OPENAI_API_KEY` to version control
- Use environment variables for sensitive configuration
- Consider using a separate API key for development/production
- Monitor API usage and costs regularly
- Implement rate limiting for public deployments

## Testing

To test the chat endpoint:

```bash
curl -X POST http://localhost:8000/api/chat/send \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Hello, who are you?",
    "conversation_history": [],
    "model": "gpt-4o"
  }'
```
