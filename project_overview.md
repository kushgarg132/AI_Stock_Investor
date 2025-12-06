# AI Stock Investor - Project Overview

This document provides a comprehensive detailed explanation of the project structure, file purposes, architecture, and areas for improvement.

## Architecture Diagram

The system follows a multi-agent architecture where a **Master Agent** orchestrates specialized agents (**Analyst**, **Quant**, **Risk**) to make trading decisions. These agents rely on a **Backend API** (acting as a Model Context Protocol - MCP layer) which exposes core logic and data fetching capabilities.

```mermaid
graph TD
    subgraph "Agents Layer"
        MA[Master Agent]
        AA[Analyst Agent]
        QA[Quant Agent]
        RA[Risk Agent]
    end

    subgraph "Backend / MCP Layer"
        API[FastAPI Server]
        subgraph "Tools"
            NF[News Fetcher]
            NS[News Sentiment]
            EC[Event Classifier]
            PH[Price History]
            TA[Technical Analysis Tools]
            RR[Risk Rules]
        end
    end

    subgraph "Core Logic"
        Strat[Strategies]
        Ind[Indicators]
        Back[Backtester]
    end

    subgraph "External / Data"
        ExtAPI[External APIs (YFinance, News)]
        DB[(MongoDB / Redis)]
        LLM[LLM Service (OpenAI)]
    end

    %% Flows
    MA -->|Orchestrates| AA
    MA -->|Orchestrates| QA
    MA -->|Validates| RA
    
    AA -->|Calls| API
    QA -->|Calls| API
    RA -->|Calls| API
    
    API --> NF
    API --> NS
    API --> EC
    API --> PH
    API --> TA
    API --> RR
    
    TA --> Ind
    QA --> Strat
    
    NF --> ExtAPI
    PH --> ExtAPI
    NS --> LLM
    EC --> LLM
    
    API -.-> DB
```

## File Explanations & Scope of Improvement

### 1. Agents (`/agents`)

| File | Purpose | Scope for Improvement |
|------|---------|-----------------------|
| `master_agent.py` | Orchestrates the entire workflow. Calls Analyst and Quant agents in parallel, then validates with Risk agent. Makes the final decision. | Add more complex conflict resolution logic between agents. Implement state persistence for ongoing trades. |
| `analyst_agent.py` | Focuses on fundamental analysis. Fetches news, analyzes sentiment, detects events, and generates a summary using LLM. | Improve prompt engineering for better summaries. Add support for more news sources. Cache results to save API calls. |
| `quant_agent.py` | Focuses on technical analysis. Fetches price data, calculates indicators, and runs defined strategies (Breakout, Mean Reversion, etc.). | Add more strategies. Optimize data fetching (fetch once for all strategies). Support multi-timeframe analysis. |
| `risk_agent.py` | Acts as a gatekeeper. Checks if a proposed trade fits within risk parameters (position size, exposure limits). | Add portfolio-level risk checks (correlation, sector exposure). Implement dynamic risk sizing based on volatility. |

### 2. Backend (`/backend`)

| File | Purpose | Scope for Improvement |
|------|---------|-----------------------|
| `server.py` | The main entry point for the FastAPI application. Configures routes, middleware, and database connections. | Add authentication/authorization. Implement rate limiting. Add comprehensive logging and monitoring. |
| `models.py` | Defines Pydantic models for data validation and structure (e.g., `NewsArticle`, `TradeSignal`, `PriceCandle`). | Add validation methods to models. Ensure consistent use of Enums across the app. |
| `database.py` | Manages connections to MongoDB and Redis. | Add repository pattern for cleaner data access. Implement connection pooling configuration. |
| `llm.py` | Service wrapper for OpenAI API interactions. Handles prompts and responses. | Add support for local LLMs. Implement retry logic and cost tracking. |

### 3. Core Logic (`/core`)

| File | Purpose | Scope for Improvement |
|------|---------|-----------------------|
| `strategies.py` | Implements specific trading strategies (`TechnicalBreakout`, `MeanReversion`, `VolumeSurge`). | Parameterize strategies for easier optimization. Add more sophisticated entry/exit logic. |
| `indicators.py` | Library of technical indicators (RSI, SMA, EMA, Bollinger Bands, etc.). | Optimize using vectorization (pandas/numpy) if not already. Add more indicators (MACD, Stochastic, etc.). |
| `backtester.py` | Engine to run strategies against historical data and calculate performance metrics. | Optimize for speed (vectorization). Add more metrics (Sortino, Calmar). Support multi-asset backtesting. |
| `risk.py` | Contains pure logic for risk calculations (position sizing, exposure). | Add more advanced risk models (Kelly Criterion, volatility targeting). |
| `support_resistance.py` | Algorithms to identify support and resistance levels. | Improve algorithm to be more robust to noise. Add visualization helpers. |
| `trend.py` | Logic to determine market trend (Up, Down, Choppy). | Add multi-timeframe trend confirmation. Use ADX or other trend strength indicators. |

### 4. MCP Tools (`/mcp_tools`)

These files expose core functionality as API endpoints, allowing agents to use them as "tools".

| File | Purpose | Scope for Improvement |
|------|---------|-----------------------|
| `news_fetcher.py` | Endpoint to fetch news articles (currently mocks data). | Integrate real News API. Add filtering by date/relevance. |
| `news_sentiment.py` | Endpoint to analyze sentiment of articles using LLM. | Batch processing for efficiency. Fine-tune prompts for financial context. |
| `event_classifier.py` | Endpoint to extract financial events from text using LLM. | Improve extraction accuracy. Standardize event types. |
| `price_history_fetcher.py` | Endpoint to fetch historical price data via `yfinance`. | Add caching (Redis) to reduce external API calls. Handle API limits. |
| `trend_detector.py` | Endpoint to detect trend. | Expose configuration parameters for trend detection. |
| `support_resistance_detector.py` | Endpoint to find S/R levels. | Return levels with strength/significance scores. |
| `volume_spike_detector.py` | Endpoint to detect volume anomalies. | Add context (e.g., relative to time of day). |
| `risk_rules_tool.py` | Endpoint to check risk rules. | Sync with portfolio state in database. |

### 5. Configuration & Root

| File | Purpose | Scope for Improvement |
|------|---------|-----------------------|
| `configs/settings.py` | Centralized configuration using Pydantic BaseSettings (env vars). | Add validation for critical secrets. Separate dev/prod configs. |
| `run_backtest.py` | Script to run a backtest manually. | Make it a CLI tool with arguments. Save results to file/db. |
| `verify_system.py` | Script to verify system health and run a test agent flow. | Convert into a proper test suite (pytest). Add more coverage. |

## General Improvements

1.  **Testing**: The project lacks a comprehensive test suite. Unit tests for core logic and integration tests for agents are needed.
2.  **Data Persistence**: While database connections exist, the agents currently don't seem to save trade history or signals persistently.
3.  **Error Handling**: Robust error handling and recovery mechanisms (e.g., if an external API fails) should be implemented.
4.  **Logging**: Centralized logging with structured output would help in debugging and monitoring.
