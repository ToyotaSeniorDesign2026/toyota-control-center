# Quick Start: OpenAI Integration

This guide shows you how to get the AI chat working with OpenAI.

## Step 1: Get Your OpenAI API Key

1. Go to https://platform.openai.com/api-keys
2. Click "Create new secret key"
3. Copy the key (you won't be able to see it again)

## Step 2: Install Dependencies

```bash
# Backend - install OpenAI client
cd backend
pip install openai

# Frontend dependencies already installed
```

## Step 3: Configure Environment Variables

### For Local Development

Create a `.env` file in the `backend/` directory (or update existing):

```bash
# Add this line:
OPENAI_API_KEY=sk-your-actual-api-key-here
OPENAI_MODEL=gpt-4o
```

### For Docker

Update `backend/docker-compose.yml`:

```yaml
services:
  api:
    environment:
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - OPENAI_MODEL=gpt-4o
```

## Step 4: Start the Application

```bash
# Frontend
cd frontend
npm run dev

# Backend (in another terminal)
cd backend
python -m uvicorn app.main:app --reload
```

## Step 5: Test the Chat

1. Open http://localhost:5173 (or your frontend URL)
2. Click the chat icon
3. Type a message and press Enter
4. The AI should respond!

## Verify It's Working

Test via curl:

```bash
curl -X POST http://localhost:8000/api/chat/send \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Hello! What can you help me with?",
    "conversation_history": []
  }'
```

You should get a response like:

```json
{
  "response": "Hi! I'm CC Assistant... [AI response continues]"
}
```

## Troubleshooting

**"Chat service is not properly configured"**
- Check that `OPENAI_API_KEY` is set in environment
- Verify the key is not expired at https://platform.openai.com/account/api-keys

**"Module 'openai' not found"**
- Run: `pip install openai`

**"401 Unauthorized"**
- Check that your API key is valid
- Make sure it hasn't been revoked

**"Rate limit exceeded"**
- Your account may have hit usage limits
- Check https://platform.openai.com/account/usage

## Features Now Available

✅ AI Chat in the workspace
✅ Conversation history support
✅ Attach jobs and templates for context
✅ Model selection (GPT-4o, etc.)
✅ Real-time streaming responses

## API Reference

### Send Message
- **Endpoint**: `POST /api/chat/send`
- **Request**:
  ```json
  {
    "message": "Your question here",
    "conversation_history": [
      {"role": "user", "content": "Previous question"},
      {"role": "assistant", "content": "Previous answer"}
    ],
    "model": "gpt-4o"
  }
  ```
- **Response**:
  ```json
  {
    "response": "AI response here"
  }
  ```

## Next Steps

- Monitor API usage and costs at https://platform.openai.com/account/usage
- Customize the system prompt in `backend/app/services/chat_service.py`
- Implement user-specific rate limiting as needed
- Add more context types beyond jobs and templates
