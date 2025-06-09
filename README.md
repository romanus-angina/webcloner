# Orchids SWE Intern Challenge Template

This project consists of a backend built with FastAPI and a frontend built with Next.js and TypeScript.

## Backend

The backend uses `uv` for package management.

### Prerequisites

- **Python 3.11+**
- **Node.js 18+**
- **Anthropic API Key**
- **Browserbase Account** (optional, local browser fallback available)

### Installation

1. **Clone the repository**

   ```bash
   git clone https://github.com/yourusername/ai-website-cloner.git
   cd ai-website-cloner
   ```

2. **Backend Setup**

   ```bash
   cd backend
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Environment Configuration**

   ```bash
   cp .env.example .env
   # Edit .env with your API keys
   ```

4. **Start Backend Server**

   ```bash
   uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
   ```

5. **Frontend Setup** *(Coming Soon)*

   ```bash
   cd frontend
   npm install
   npm start
   ```

## ⚙️ Configuration

### Required Environment Variables

```bash
# Core API Keys
ANTHROPIC_API_KEY=your_anthropic_api_key_here

# Optional Cloud Browser (Browserbase)
USE_CLOUD_BROWSER=true
BROWSERBASE_API_KEY=your_browserbase_key
BROWSERBASE_PROJECT_ID=your_project_id

# Local Browser Settings
BROWSER_TYPE=chromium
BROWSER_HEADLESS=true
BROWSER_TIMEOUT=30

# Application Settings
DEBUG=false
RATE_LIMIT_REQUESTS=10
RATE_LIMIT_WINDOW=60
```

## Core Endpoints

```http
POST /api/v1/clone
```

Start a new website cloning operation

```json
{
  "url": "https://example.com",
  "quality": "balanced",
  "include_styling": true
}
```

```http
GET /api/v1/clone/{session_id}
```

Get cloning status and results

```json
{
  "session_id": "uuid",
  "status": "completed",
  "similarity_score": 80.0,
  "component_analysis": {
    "total_components": 3,
    "components_detected": [...]
  }
}
```

```http
GET /api/v1/sessions
```

List all cloning sessions with pagination

### Additional Endpoints

- `DELETE /api/v1/clone/{session_id}` - Delete session
- `GET /api/v1/health` - Health check
- `GET /api/v1/screenshots/presets` - Viewport presets
- `POST /api/v1/dom/extract` - Direct DOM extraction

### Backend Tests

```bash
cd backend

# Run all tests
pytest -v

# Run with coverage
pytest --cov=app tests/

# Run specific test categories
pytest -m "unit"
pytest -m "integration"
pytest -m "api"
```

### Test Results

```
================== 177 passed, 1 skipped ==================
- Unit Tests: 145 passed
- Integration Tests: 25 passed  
- API Tests: 7 passed
- Coverage: 100%
```

### Running the Backend

To run the backend development server, use the following command:

```bash
   uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
   ```

## Frontend

The frontend is built with Next.js and TypeScript.

### Installation

To install the frontend dependencies, navigate to the frontend project directory and run:

```bash
npm install
```

### Running the Frontend

To start the frontend development server, run:

```bash
npm run dev
```
