# DIA - Digital Intelligent Assistant

A multimodal AI-powered assistant leveraging Retrieval-Augmented Generation (RAG) to support operators in industrial assembly processes.

## Overview

DIA combines computer vision, natural language processing, and a knowledge base system to provide real-time guidance during assembly tasks. The system analyzes both verbal queries and visual input to deliver contextual, accurate responses.

## Features

### Web Interface
- **Modern UI** — Responsive design with Bootstrap 5
- **Dual-panel Layout** — Live camera feed alongside chat interface
- **Real-time Feedback** — Instant responses with smooth animations

### Voice Capabilities
- **Speech Recognition** — Real-time voice input via Web Speech API
- **Natural TTS Output** — High-quality text-to-speech using OpenAI TTS-1-HD (Nova voice)
- **Audio Controls** — Toggle voice output on/off

### Image Analysis
- **WebRTC Camera** — Browser-based real-time camera access
- **Preview & Confirm** — Review captures before submission
- **GPT-4o Vision** — Automatic object identification and analysis

### AI & RAG System
- **Knowledge Base** — PDF-based documentation with LangChain integration
- **GPT-4o Backend** — Contextual, intelligent responses
- **Multimodal Processing** — Combined text and image analysis
- **Conversational Memory** — Context retention across interactions

### Metrics & Logging
- **Detailed Logging** — All interactions saved to Excel
- **Session Statistics** — Real-time metrics tracking
- **Image Archive** — Automatic storage of captured images

## Architecture

```
DIA/
├── app.py                 # Flask web server (primary interface)
├── main.py                # CLI interface (alternative)
├── config.py              # System configuration
├── rag_service.py         # RAG and knowledge base logic
├── metrics_service.py     # Logging and metrics
├── audio_service.py       # Audio processing (CLI)
├── vision_service.py      # Vision processing (CLI)
├── utils.py               # Utility functions
├── templates/
│   └── index.html         # Web interface
├── static/
│   ├── css/style.css      # Custom styles
│   └── js/app.js          # Frontend logic
└── content/
    └── pdf/               # Knowledge base documents
```

## Requirements

- Python 3.8+
- OpenAI API key
- Webcam (for image analysis features)
- Microphone (for voice input features)

## Installation

### Standard Setup

```bash
# Clone the repository
git clone https://github.com/yourusername/DIA.git
cd DIA

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/macOS
venv\Scripts\activate     # Windows

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env and add your OpenAI API key
```

### Docker Setup

```bash
# Build and run with Docker Compose
docker-compose up --build

# Or build manually
docker build -t dia .
docker run -p 5000:5000 --env-file .env dia
```

## Configuration

Create a `.env` file in the project root:

```env
OPENAI_API_KEY=your-api-key-here
```

Additional configuration options are available in `config.py`:

| Parameter | Description | Default |
|-----------|-------------|---------|
| `SPEECH_RATE` | TTS speech rate | 180 |
| `SILENCE_THRESHOLD` | Voice detection threshold | 1000 |
| `SILENCE_DURATION` | Silence duration to stop recording | 2.5s |

## Usage

### Web Interface (Recommended)

```bash
python app.py
```

Open your browser at `http://localhost:5000`

### CLI Interface

```bash
python main.py
```

### Workflow

1. **Initialize** — Enter participant ID and select job type
2. **Interact** — Use voice or text to ask questions
3. **Capture** — Say "PHOTO" or click the camera button to analyze objects
4. **Complete** — The system tracks all interactions automatically

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Web interface |
| `/chat` | POST | Send text message |
| `/upload_image` | POST | Upload image for analysis |
| `/metrics` | GET | Retrieve session metrics |

## Troubleshooting

### Common Issues

1. **Audio not working**
   - List available microphones and update `MIC_INDEX` in `config.py`

2. **Camera not opening**
   - Ensure no other application is using the camera
   - Check `CAMERA_INDEX` in `config.py`

3. **OpenAI API errors**
   - Verify your API key in `.env`
   - Check available credits on your OpenAI account

4. **PDFs not processed**
   - Verify files exist in `content/pdf/`
   - Check paths in `PDF_PATHS` configuration

### Debug Mode

Enable detailed debugging in `config.py`:
```python
DEBUG_MODE = True
```

## Security

> **Important:** Never commit API keys to version control. Always use `.env` files for sensitive credentials and restrict access to log files containing user data.

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/new-feature`)
3. Commit your changes (`git commit -am 'Add new feature'`)
4. Push to the branch (`git push origin feature/new-feature`)
5. Open a Pull Request

## License

MIT License

## Support

For issues and feature requests, please use the [GitHub Issues](https://github.com/yourusername/DIA/issues) page.
