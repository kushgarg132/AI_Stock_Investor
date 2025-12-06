# AI Stock Investor

A comprehensive multi-agent system for autonomous stock analysis and trading. This project leverages specialized AI agents (Analyst, Quant, Risk) orchestrated by a Master Agent to make informed trading decisions based on fundamental news, technical analysis, and strict risk management rules.

## Features

- **Multi-Agent Architecture**:
  - **Master Agent**: Orchestrates the workflow and makes final decisions.
  - **Analyst Agent**: Analyzes news sentiment and financial events using LLMs.
  - **Quant Agent**: Performs technical analysis using strategies like Breakout, Mean Reversion, and Volume Surge.
  - **Risk Agent**: Validates trades against position sizing and exposure limits.
- **MCP-style Backend**: A FastAPI server acting as a Model Context Protocol layer, exposing tools for data fetching and analysis.
- **Backtesting Engine**: Simulate strategies against historical data.
- **Technical Indicators**: Built-in library for RSI, SMA, EMA, Bollinger Bands, etc.

## Prerequisites

- **Python 3.8+**
- **MongoDB**: For data persistence (ensure it's running locally or provide URL).
- **Redis**: For caching and messaging (ensure it's running locally).
- **OpenAI API Key**: For LLM-based sentiment analysis and summaries.

## Installation

1.  **Clone the repository**

    ```bash
    git clone <repository-url>
    cd AI_Stock_Investor
    ```

2.  **Create and activate a virtual environment**

    ```bash
    python -m venv .venv
    # Windows
    .venv\Scripts\activate
    # Linux/Mac
    source .venv/bin/activate
    ```

3.  **Install dependencies**
    ```bash
    pip install -r requirements.txt
    ```

## Configuration

1.  **Environment Variables**:
    The application uses `pydantic-settings`. You can set these via environment variables or a `.env` file.

    Key variables (see `configs/settings.py` for defaults):

    - `OPENAI_API_KEY`: Required for Analyst Agent.
    - `MONGODB_URL`: Default `mongodb://localhost:27017`
    - `REDIS_URL`: Default `redis://localhost:6379`

## Usage

### 1. Run the API Server

Start the backend server which exposes the tools and agents.

```bash
uvicorn backend.server:app --reload
```

The API will be available at `http://localhost:8000`.
Docs: `http://localhost:8000/api/v1/docs`

### 2. Run a Backtest

Test the strategies against historical data.

```bash
python run_backtest.py
```

### 3. Verify System

Run a quick health check and a test agent flow for a single symbol (e.g., AAPL).

```bash
python verify_system.py
```

## Documentation

For a detailed explanation of the project structure and file purposes, please refer to [project_overview.md](project_overview.md).
For detailed System Architecture and User Flow diagrams, please refer to [ARCHITECTURE.md](ARCHITECTURE.md).

## Project Structure

- `agents/`: AI Agents logic.
- `backend/`: FastAPI server and database connections.
- `core/`: Core trading logic (strategies, indicators, backtester).
- `mcp_tools/`: API endpoints exposed as tools.
- `configs/`: Configuration settings.
