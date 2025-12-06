# AI Stock Investor - System Architecture

This document details the technical architecture, user flows, and agent workflows of the AI Stock Investor application.

## 1. System Architecture

The system follows a microservices-like architecture where a **Frontend** (React) communicates with a **Backend** (FastAPI). The Backend orchestrates a Multi-Agent System using **LangGraph** to analyze stocks.

```mermaid
graph TD
    subgraph "Frontend Layer (React + Vite)"
        UI[User Interface]
        Dash[Dashboard View]
        Scan[Scanner View]
        Goal[Goals View]
        Router[React Router]
    end

    subgraph "Backend Layer (FastAPI)"
        API[API Gateway / Server]
        Models[Pydantic Models]
        DB_Conn[Database Handler]
    end

    subgraph "Agentic Layer (LangGraph)"
        Master[Master Agent]
        Analyst[Analyst Agent]
        Quant[Quant Agent]
        Risk[Risk Agent]
    end

    subgraph "Data & Tools Layer"
        Mongo[(MongoDB)]
        Redis[(Redis Cache)]
        YF[YFinance Tool]
        News[News API Tool]
        LLM[LLM Service (OpenAI/Gemini)]
    end

    %% Connections
    UI --> Router
    Router --> Dash
    Router --> Scan
    Router --> Goal

    Dash -->|HTTP Request| API
    Scan -->|HTTP Request| API

    API --> Master

    Master -->|Orchestrates| Analyst
    Master -->|Orchestrates| Quant
    Master -->|Orchestrates| Risk

    Analyst -->|Calls| News
    Analyst -->|Calls| LLM

    Quant -->|Calls| YF
    Quant -->|Calls| LLM

    Risk -->|Calls| LLM

    Master -->|Reads/Writes| DB_Conn
    DB_Conn --> Mongo
    DB_Conn --> Redis
```

## 2. User Flow

The following diagram illustrates how a user interacts with the application to analyze a stock.

```mermaid
flowchart TD
    Start([User Opens App]) --> Dashboard[Dashboard Page]

    subgraph "Analysis Flow"
        Dashboard --> Search{Search Stock?}
        Search -->|Yes| Input[Enter Symbol]
        Input --> Loading[Show Loading State]
        Loading --> API_Call[Call Backend API]

        API_Call -->|Success| Display[Display Analysis Card]
        Display --> Charts[View Price Charts]
        Display --> Signals[View Trade Signals]
        Display --> News[View News Sentiment]

        API_Call -->|Error| ErrMsg[Show Error Message]
    end

    subgraph "Navigation"
        Dashboard -->|Click Nav| Scanner[Scanner Page]
        Dashboard -->|Click Nav| Goals[Goals Page]

        Scanner --> Filter[Set Filters]
        Filter --> ScanResults[View Scan Results]

        Goals --> SetGoal[Define Investment Goal]
        SetGoal --> Track[Track Progress]
    end
```

## 3. Agent Execution Workflow

The **Master Agent** utilizes a sequential graph to orchestrate the analysis process. This ensures that each step has the necessary context from the previous step.

```mermaid
sequenceDiagram
    participant API as FastAPI Server
    participant Master as Master Agent
    participant Info as Company Info
    participant Analyst as Analyst Agent
    participant Quant as Quant Agent
    participant Risk as Risk Agent

    API->>Master: Request Analysis (Symbol)
    activate Master

    Master->>Master: Resolve Symbol (Tickers)

    Master->>Info: Fetch Company Details
    activate Info
    Info-->>Master: Company Metadata
    deactivate Info

    Master->>Analyst: Run Fundamental Analysis
    activate Analyst
    Analyst-->>Master: News, Sentiment, Events
    deactivate Analyst

    Master->>Quant: Run Technical Analysis
    activate Quant
    Quant-->>Master: Trends, Support/Resistance, Signals
    deactivate Quant

    Master->>Risk: Evaluate Risk & Position Sizing
    activate Risk
    Risk-->>Master: Approved Signal, Sizing logic
    deactivate Risk

    Master->>Master: Final Decision & Reasoning

    Master-->>API: MasterOutput (JSON)
    deactivate Master
```

## 4. Key Components

### Frontend Components

- **Layout**: Main wrapper with Navigation bar.
- **Dashboard**: Entry point, displays the Search Bar and Analysis Results.
- **AnalysisCard**: Complex component to render charts, signals, and agent summaries.
- **ScannerPage**: For filtering market data (in development).
- **GoalsPage**: For managing user financial goals (in development).

### Backend Agents

- **Master Agent**: The controller. Defines the LangGraph workflow `Resolve -> Info -> Analyst -> Quant -> Risk -> Decision`.
- **Analyst Agent**: Scrapes news, analyzes sentiment using LLM, and identifies major events.
- **Quant Agent**: Fetches historical price data, calculates technical indicators (RSI, MACD, etc.), and generates trade signals.
- **Risk Agent**: Acts as a sanity check. Verifies if a trade aligns with risk parameters and calculates safe position sizes.

### Data Models

- **TradeSignal**: Represents a Buy/Sell/Hold recommendation with confidence score.
- **NewsArticle**: Structured news data with sentiment analysis.
- **PriceCandle**: OHLCV data point for charting.
