import React from 'react';
import Layout from '../components/Layout';
import { Badge } from '../components/common/Badge';
import { 
  Brain, 
  LineChart, 
  Shield, 
  Newspaper, 
  ArrowDown, 
  ArrowRight, 
  Cpu, 
  CheckCircle2 
} from 'lucide-react';
import { cn } from '../utils/cn';

// `Icon` is used via JSX (<Icon .../>) below -- this project has no eslint-plugin-react
// installed to teach no-unused-vars that pattern.
// eslint-disable-next-line no-unused-vars
const AgentNode = ({ icon: Icon, title, description, className }) => (
  <div className={cn(
    "relative flex flex-col items-center p-6 sheet transition-colors hover:border-[var(--stamp)]",
    className
  )}>
    <div className="p-3 mb-3 border border-[var(--rule-strong)]">
      <Icon className="w-7 h-7 text-[var(--stamp)]" strokeWidth={1.5} />
    </div>
    <h3 className="text-lg font-bold mb-2">{title}</h3>
    <p className="text-sm text-center text-muted-foreground">{description}</p>
    
    {/* Connector Dots for visual flows */}
    <div className="absolute -bottom-3 left-1/2 -translate-x-1/2 w-1.5 h-1.5 bg-[var(--rule-strong)]" />
    <div className="absolute -top-3 left-1/2 -translate-x-1/2 w-1.5 h-1.5 bg-[var(--rule-strong)]" />
  </div>
);

const FlowArrow = ({ className }) => (
  <div className={cn("flex flex-col items-center justify-center text-muted-foreground/50", className)}>
    <ArrowDown className="w-6 h-6 animate-flow-down" />
  </div>
);

const SystemArchitecturePage = () => {
  return (
    <Layout>
      <div className="max-w-5xl mx-auto space-y-12 animate-in fade-in slide-in-from-bottom-4 duration-700">
        
        {/* Header */}
        <div className="text-center space-y-4">
            <Badge variant="outline" className="mb-2">System Architecture</Badge>
            <h1 className="text-4xl font-bold tracking-tight">Autonomous Agentic Workflow</h1>
            <p className="text-xl text-muted-foreground max-w-2xl mx-auto">
                Visualizing how the Master Agent orchestrates a swarm of specialized AI agents to deliver institutional-grade analysis.
            </p>
        </div>

        {/* Diagram Container */}
        <div className="relative p-8 md:p-12 sheet overflow-hidden">
            {/* Background Elements */}
            
            
            <div className="relative flex flex-col items-center gap-8">
                
                {/* Level 1: User Input (Implicit) */}
                <div className="text-sm font-medium text-muted-foreground uppercase tracking-widest mb-4">Input: Stock Symbol</div>

                {/* Level 2: Master Agent */}
                <AgentNode 
                    icon={Brain} 
                    title="Master Agent" 
                    description="Orchestrator. Decomposes tasks, delegates analysis, and synthesizes final verdict."
                    
                    className="w-full max-w-md"
                />

                <FlowArrow />

                {/* Level 3: Specialist Agents Grid */}
                <div className="grid grid-cols-1 md:grid-cols-3 gap-8 w-full relative">
                    {/* Horizontal Connector Line */}
                    <div className="hidden md:block absolute top-1/2 left-10 right-10 h-0.5 bg-border -z-10 -mt-10" />

                    {/* Analyst */}
                    <div className="flex flex-col items-center gap-4">
                         <div className="hidden md:block h-8 w-0.5 bg-border -mt-12" /> {/* Vertical Connector */}
                        <AgentNode 
                            icon={Newspaper} 
                            title="Analyst Agent" 
                            description="Scrapes live news, analyzes sentiment, and identifies key corporate events."
                            
                            className="h-full"
                        />
                        <ArrowDown className="w-5 h-5 text-muted-foreground/30" />
                        <div className="doc-meta border border-[var(--rule)] px-2 py-1">Sentiment Score</div>
                    </div>

                    {/* Quant */}
                    <div className="flex flex-col items-center gap-4">
                        <div className="hidden md:block h-8 w-0.5 bg-border -mt-12" />
                        <AgentNode 
                            icon={LineChart} 
                            title="Quant Agent" 
                            description="Calculates technical indicators (RSI, MACD) and detects chart patterns."
                            
                            className="h-full"
                        />
                        <ArrowDown className="w-5 h-5 text-muted-foreground/30" />
                        <div className="doc-meta border border-[var(--rule)] px-2 py-1">Tech Signals</div>
                    </div>

                    {/* Risk */}
                    <div className="flex flex-col items-center gap-4">
                        <div className="hidden md:block h-8 w-0.5 bg-border -mt-12" />
                        <AgentNode 
                            icon={Shield} 
                            title="Risk Agent" 
                            description="Evaluates exposure, enforces stop-losses, and calculates safe position sizing."
                            className="h-full"
                        />
                        <ArrowDown className="w-5 h-5 text-muted-foreground/30" />
                        <div className="doc-meta border border-[var(--rule)] px-2 py-1">Risk Checks</div>
                    </div>
                </div>

                <div className="w-full max-w-3xl border-t border-border mt-8 mb-4" />

                {/* Level 4: Final Output */}
                <div className="relative flex items-center gap-4 sheet p-5 border-[var(--stamp)] w-full max-w-2xl">
                    <div className="p-2.5 border border-[var(--stamp)] text-[var(--stamp)]">
                        <CheckCircle2 className="w-8 h-8" />
                    </div>
                    <div className="flex-1">
                        <h3 className="text-xl font-bold">Final Decision & Reasoning</h3>
                        <p className="text-muted-foreground">Comprehensive report with Buy/Sell/Hold signal, confidence score, and rationale.</p>
                    </div>
                    <div className="flex gap-2">
                        <Badge variant="success">BUY</Badge>
                        <Badge variant="destructive">SELL</Badge>
                        <Badge variant="secondary">HOLD</Badge>
                    </div>
                </div>

            </div>
        </div>

        {/* Tech Stack Hints */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-center">
            <div className="sheet p-4">
                <Cpu className="w-6 h-6 mx-auto mb-2 text-indigo-400" />
                <div className="font-semibold">LangGraph</div>
                <div className="text-xs text-muted-foreground">Orchestration</div>
            </div>
            <div className="sheet p-4">
                <Brain className="w-6 h-6 mx-auto mb-2 text-orange-400" />
                <div className="font-semibold">Gemini Pro</div>
                <div className="text-xs text-muted-foreground">Reasoning Engine</div>
            </div>
             <div className="sheet p-4">
                <LineChart className="w-6 h-6 mx-auto mb-2 text-green-400" />
                <div className="font-semibold">TA-Lib</div>
                <div className="text-xs text-muted-foreground">Technical Analysis</div>
            </div>
             <div className="sheet p-4">
                <Shield className="w-6 h-6 mx-auto mb-2 text-red-400" />
                <div className="font-semibold">FastAPI</div>
                <div className="text-xs text-muted-foreground">High Perf API</div>
            </div>
        </div>

      </div>
    </Layout>
  );
};

export default SystemArchitecturePage;
