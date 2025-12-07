# AI Stock Investor

A comprehensive, agentic AI platform for autonomous stock analysis, trading simulation, and personalized investment insights. This system leverages a multi-agent architecture (Master, Analyst, Quant, Risk, Chat) to provide deep fundamental and technical analysis combined with strict risk management.

## Live Demo

- **Frontend (UI)**: [https://ai-stock-investor.vercel.app/](https://ai-stock-investor.vercel.app/)
- **Backend (API)**: [https://ai-stock-investor.onrender.com](https://ai-stock-investor.onrender.com)

---

## 🚀 Key Features

### 🤖 Multi-Agent AI Core

- **Master Agent**: Orchestrates the analysis workflow, synthesizing inputs from all sub-agents to make final Buy/Sell/Hold recommendations.
- **Analyst Agent**: Scrapes and analyzes financial news and sentiment using LLMs (Google Gemini) to understand market mood.
- **Quant Agent**: Performs rigorous technical analysis using TA-Lib (RSI, MACD, Bollinger Bands, Moving Averages) to identify trends and signals.
- **Risk Agent**: Evaluates trades against predefined risk rules, position sizing constraints, and portfolio exposure limits.
- **Chat Agent**: An interactive assistant that allows users to query stock data, ask for summaries, and get real-time insights via a chat interface.

### 📊 Modern User Interface

- **Interactive Dashboard**: Real-time view of market trends, indices (NIFTY 50, SENSEX), and top trending stocks.
- **Deep Analysis Cards**: Detailed visualization of stock performance, including dynamic price charts, technical signals, and AI-generated reasoning.
- **Stock Scanner**: dedicated tool to scan the market for bullish or bearish setups based on technical criteria.
- **Investment Goals**: A specialized module to define and track personalized investment objectives.
- **Smart Chat Widget**: Floating chat interface for instant AI assistance.

## 🛠️ Tech Stack

### Backend

- **Framework**: FastAPI (Python 3.11+)
- **AI/LLM**: LangChain, LangGraph, Google Gemini Pro
- **Data Processing**: TA-Lib (Technical Analysis), yfinance (Market Data), BeautifulSoup (Web Scraping)
- **Database**: MongoDB (Persistent Storage), Redis (Caching & Pub/Sub)

### Frontend

- **Framework**: React.js (Vite)
- **Styling**: Modern CSS3, Responsive Design
- **State/API**: Axios, React Hooks

### Infrastructure

- **Containerization**: Docker, Docker Compose
- **Deployment**: Render (Backend), Vercel (Frontend)

---

## ⚙️ Installation & Setup

### Prerequisites

- Docker & Docker Compose (Recommended)
- OR Python 3.11+, Node.js 18+, MongoDB, and Redis installed locally.
- API Keys: Google Gemini API Key (Required), NewsAPI/FMP (Optional).

### Option 1: Docker (Fastest)

1. **Clone the repository**

   ```bash
   git clone <repository-url>
   cd AI_Stock_Investor
   ```

2. **Setup Environment Variables**
   Create a `.env` file in the root directory:

   ```env
   GEMINI_API_KEY=your_gemini_key_here
   MONGODB_URL=mongodb://mongo:27017
   REDIS_URL=redis://redis:6379
   ```

3. **Run with Docker Compose**
   ```bash
   docker-compose up --build
   ```
   The backend will be available at `http://localhost:8000` and frontend at `http://localhost:5173`.

### Option 2: Manual Setup

#### Backend

1. Navigate to `backend/`:
   ```bash
   cd backend
   python -m venv .venv
   source .venv/bin/activate  # or .venv\Scripts\activate on Windows
   pip install -r requirements.txt
   ```
2. Run the server (ensure Mongo/Redis are running):
   ```bash
   uvicorn server:app --reload --port 8000
   ```

#### Frontend

1. Navigate to `frontend/`:
   ```bash
   cd frontend
   npm install
   npm run dev
   ```

---

## 📂 Project Structure

```
AI_Stock_Investor/
├── backend/
│   ├── agents/          # Agent logic (Master, Quant, Analyst, etc.)
│   ├── core/            # Core trading strategies and backtester
│   ├── mcp_tools/       # Tools for data fetching and analysis
│   ├── routers/         # FastAPI endpoints
│   ├── configs/         # Settings and logging configurations
│   ├── Dockerfile
│   └── requirements.txt
│
├── frontend/
│   ├── src/
│   │   ├── components/  # Reusable UI components (AnalysisCard, ChatWidget)
│   │   ├── pages/       # Main pages (Dashboard, Scanner, Goals)
│   │   └── utils/       # API integration
│   └── package.json
│
└── docker-compose.yml   # Container orchestration
```

## 📄 API Documentation

Once the backend is running, visit:

- **Swagger UI**: `http://localhost:8000/api/v1/docs`
- **ReDoc**: `http://localhost:8000/api/v1/redoc`
