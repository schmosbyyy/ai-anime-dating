# AI Anime Dating Backend API

A Flask-based backend service that powers interactive AI anime character experiences through integrated speech synthesis, animation, and visual storytelling.

## 🚀 Overview

This application creates immersive anime dating experiences by combining:
- **Conversational AI** (Google Gemini 2.0 Flash)
- **Speech Synthesis** (Azure Cognitive Services)
- **Character Animation** (SSML bookmarks)
- **Visual Storytelling** (Script segmentation for video generation)

The service transforms user messages into:
- Natural AI responses with emotional expression
- Synchronized speech audio with lip-sync data
- Character animations triggered by speech content
- Granular video segments for seamless visual storytelling

## 🏗️ Architecture

### Core Components

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Frontend      │    │   Flask API      │    │   AI Services    │
│   (React/Vue)   │◄──►│   /api/respond   │◄──►│   Gemini + TTS   │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                              │
                              ▼
                       ┌─────────────────┐
                       │   Response      │
                       │   Processing    │
                       └─────────────────┘
```

### Service Integration

- **Google Gemini 2.0 Flash**: Dual-purpose AI processing
  - Conversational responses with SSML markup
  - Script segmentation for video generation
- **Azure Speech Services**: Text-to-speech with viseme timing
- **Flask-CORS**: Cross-origin resource sharing for frontend integration

## 📋 API Reference

### POST `/api/respond`

Main endpoint for processing user interactions and generating AI responses.

#### Request Body

```json
{
  "message": "Hello! How are you today?",
  "personality": "cheerful",
  "styledegree": "1",
  "getAiResponse": true,
  "getScriptContext": true
}
```

#### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `message` | string | ✅ | - | User input text |
| `personality` | string | ❌ | "cheerful" | Voice personality style |
| `styledegree` | string | ❌ | "1" | Intensity of personality style (0-2) |
| `getAiResponse` | boolean | ❌ | true | Generate AI conversational response |
| `getScriptContext` | boolean | ❌ | true | Generate script segments for video |

#### Response Format

##### Success Response (200)

```json
{
  "audio_url": "base64_encoded_audio_data",
  "ai_response": "<speak>...SSML markup...</speak>",
  "phoneme_timings": [
    {
      "time": 0.123,
      "viseme": 2
    }
  ],
  "word_timings": [
    {
      "time": 0.456,
      "word": "hello"
    }
  ],
  "bookmark_timings": [
    {
      "time": 1.234,
      "mark": "Happy"
    }
  ],
  "splitContext": [
    {
      "text": "Sarah smiled warmly,",
      "visual_representation_of_text": "Close-up of Sarah's face lighting up with a gentle, welcoming smile",
      "style_modifier": "warm golden lighting"
    }
  ],
  "style": "anime_style"
}
```

##### Error Response (400/500)

```json
{
  "error": "Error Category",
  "details": "Detailed error description",
  "api": "Service that failed"
}
```

#### Error Categories

- `Invalid Request` - Missing or malformed request data
- `Script Context Generation Failed` - Gemini API failure for segmentation
- `AI Response Generation Failed` - Gemini API failure for conversation
- `Direct AI Response Generation Failed` - Gemini API failure for direct SSML
- `Azure Speech Synthesis Configuration Failed` - TTS setup failure
- `Azure Speech Synthesis Failed` - TTS processing failure
- `Internal Server Error` - Unexpected application errors

## 🔧 Installation & Setup

### Prerequisites

- Python 3.8+
- API Keys:
  - Google Gemini API key
  - Azure Cognitive Services Speech API key

### Installation

1. **Clone and setup:**
```bash
git clone <repository-url>
cd ai-anime-dating
pip install -p requirements.txt
```

2. **Environment Variables:**
```bash
export GEMINI_API_KEY="your_gemini_api_key"
export AZURE_API_KEY="your_azure_api_key"
export PORT=5000  # Optional, defaults to 5000
```

3. **Run the application:**
```bash
python app.py
```

For production deployment:
```bash
gunicorn --bind 0.0.0.0:$PORT app:app
```

## 🎭 AI Processing Pipeline

### 1. Input Processing

- Validates request parameters
- Extracts user message and configuration options

### 2. AI Response Generation

**Two Processing Modes:**

#### Full Response Mode (`getAiResponse: true`)
- Generates conversational AI response with SSML markup
- Includes natural speech patterns and emotional expression
- Adds animation bookmarks for character reactions

#### Direct Response Mode (`getAiResponse: false`)
- Converts input directly to SSML without AI conversation
- Focuses purely on speech synthesis and animation

### 3. Script Segmentation (`getScriptContext: true`)

When enabled, processes the user input through the segmentation pipeline:

```json
{
  "segments": [
    {
      "text": "Character performs action,",
      "visual_representation_of_text": "Detailed visual description of the moment",
      "style_modifier": "lighting or effect adjustments"
    }
  ],
  "script_scene_style": "global visual style"
}
```

**Segmentation Rules:**
- High granularity: 2-3x more segments than traditional breakdowns
- Each segment represents a single visual moment (3-5 seconds)
- Focus on action changes, visual shifts, and emotional beats

### 4. Speech Synthesis

**Azure TTS Configuration:**
- Voice: `en-US-AriaNeural`
- Express-as style: Dynamic based on personality parameter
- SSML processing with animation bookmarks

**Timing Extraction:**
- **Visemes**: Lip-sync data for mouth animations
- **Words**: Word-level timing for text highlighting
- **Bookmarks**: Animation triggers for character expressions

### 5. Response Assembly

Combines all generated data into unified JSON response with:
- Base64-encoded audio data
- Timing arrays for synchronization
- Visual segments for video generation
- Global style definitions

## 🎨 Animation System

### Available Animations

**Emotional Expressions:**
- Happy, Sad, Content, Angry, Confused, Bored
- Surprised, Irritated, WTF, Confident, Fear
- Bereft, Flirty, Serious, Silly, Deadpan
- Suspicious, Pouty, Rage, Disgusted, Thinking

**Physical Gestures:**
- Body-Tilt, Neck-Shift, Head-Tilt, Head-X/Y
- Brow-L/R-Tilt, Brow-L/R-Raise
- Pupils-X/Y, Blink

### SSML Integration

```xml
<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis">
  <voice name="en-US-AriaNeural">
    <mstts:express-as style="cheerful" styledegree="1">
      <bookmark mark="Happy"/>I'm so excited to meet you!
      <bookmark mark="Head-Tilt"/>
    </mstts:express-as>
  </voice>
</speak>
```

## 🔒 Security & Error Handling

### Environment Variables
- All API keys stored as environment variables
- No hardcoded credentials in source code
- Secure key validation before API calls

### Error Handling Patterns
- Comprehensive try-catch blocks at each integration point
- Detailed error logging with context
- Graceful degradation (fallback to defaults on parsing errors)
- Specific error categorization for frontend handling

### Logging
- Structured logging with timestamps and context
- Different log levels (INFO, ERROR) for different scenarios
- Request tracing for debugging API issues

## 🚀 Deployment

### Local Development
```bash
python app.py
# Server runs on http://localhost:5000
```

### Production (Render.com)
- Automatic port detection via `PORT` environment variable
- Gunicorn WSGI server for production serving
- CORS configured for production frontend domain

### Docker Support
```dockerfile
FROM python:3.9-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
EXPOSE 5000
CMD ["python", "app.py"]
```

## 🧪 Testing

### API Testing
```bash
# Test basic functionality
curl -X POST http://localhost:5000/api/respond \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello!", "getAiResponse": true, "getScriptContext": false}'

# Test with all features
curl -X POST http://localhost:5000/api/respond \
  -H "Content-Type: application/json" \
  -d '{"message": "Tell me a story", "personality": "excited", "getAiResponse": true, "getScriptContext": true}'
```

### Error Testing
```bash
# Test invalid request
curl -X POST http://localhost:5000/api/respond \
  -H "Content-Type: application/json" \
  -d '{}'
```

## 🔄 Development Patterns

### Code Organization
- Single-file Flask application for simplicity
- Clear separation of concerns within the main endpoint
- Embedded system instructions as string constants

### Integration Patterns
- Sequential API calls with error handling
- Async operation handling with `.get()` method
- Response transformation and validation

### Data Processing
- Robust JSON parsing with fallback defaults
- String manipulation for SSML formatting
- Base64 encoding for binary audio data

## 📊 Performance Considerations

- **API Latency**: Gemini calls are sequential, consider parallel processing for high traffic
- **Audio Size**: Base64 encoding increases payload size by ~33%
- **Memory Usage**: Large audio files and timing arrays
- **Rate Limiting**: Implement on API keys to prevent abuse

## 🔮 Future Enhancements

- **Caching**: Response caching for repeated inputs
- **Streaming**: Real-time audio streaming instead of base64
- **Multiple Voices**: Voice selection based on character
- **Batch Processing**: Multiple segment processing
- **WebSocket Support**: Real-time conversation streaming

---

## 📝 Implementation Notes

This codebase follows a modular integration pattern where each AI service handles a specific aspect of the character experience. The emphasis is on robust error handling and detailed logging to ensure reliable operation across multiple external API dependencies.
