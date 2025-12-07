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

const AgentNode = ({ icon: Icon, title, description, color, className }) => (
  <div className={cn(
    "relative flex flex-col items-center p-6 bg-card border border-border rounded-xl shadow-lg transition-all hover:scale-105 hover:shadow-primary/20",
    className
  )}>
    <div className={cn("p-4 rounded-full mb-4 bg-opacity-10", color)}>
      <Icon className={cn("w-8 h-8", color.replace('bg-', 'text-'))} />
    </div>
    <h3 className="text-lg font-bold mb-2">{title}</h3>
    <p className="text-sm text-center text-muted-foreground">{description}</p>
    
    {/* Connector Dots for visual flows */}
    <div className="absolute -bottom-3 left-1/2 -translate-x-1/2 w-3 h-3 bg-border rounded-full" />
    <div className="absolute -top-3 left-1/2 -translate-x-1/2 w-3 h-3 bg-border rounded-full" />
  </div>
);

const FlowArrow = ({ className }) => (
  <div className={cn("flex flex-col items-center justify-center text-muted-foreground/50", className)}>
    <ArrowDown className="w-6 h-6 animate-bounce" />
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
        <div className="relative p-8 md:p-12 rounded-3xl bg-secondary/10 border border-border/50 overflow-hidden">
            {/* Background Elements */}
            <div className="absolute inset-0 bg-grid-white/5 [mask-image:linear-gradient(to_bottom,transparent,black,transparent)]" />
            
            <div className="relative flex flex-col items-center gap-8">
                
                {/* Level 1: User Input (Implicit) */}
                <div className="text-sm font-medium text-muted-foreground uppercase tracking-widest mb-4">Input: Stock Symbol</div>

                {/* Level 2: Master Agent */}
                <AgentNode 
                    icon={Brain} 
                    title="Master Agent" 
                    description="Orchestrator. Decomposes tasks, delegates analysis, and synthesizes final verdict."
                    color="bg-purple-500"
                    className="w-full max-w-md border-purple-500/30"
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
                            color="bg-blue-500"
                            className="h-full"
                        />
                        <ArrowDown className="w-5 h-5 text-muted-foreground/30" />
                        <div className="text-xs font-mono bg-background/50 px-2 py-1 rounded">Sentiment Score</div>
                    </div>

                    {/* Quant */}
                    <div className="flex flex-col items-center gap-4">
                        <div className="hidden md:block h-8 w-0.5 bg-border -mt-12" />
                        <AgentNode 
                            icon={LineChart} 
                            title="Quant Agent" 
                            description="Calculates technical indicators (RSI, MACD) and detects chart patterns."
                            color="bg-emerald-500"
                            className="h-full"
                        />
                        <ArrowDown className="w-5 h-5 text-muted-foreground/30" />
                        <div className="text-xs font-mono bg-background/50 px-2 py-1 rounded">Tech Signals</div>
                    </div>

                    {/* Risk */}
                    <div className="flex flex-col items-center gap-4">
                        <div className="hidden md:block h-8 w-0.5 bg-border -mt-12" />
                        <AgentNode 
                            icon={Shield} 
                            title="Risk Agent" 
                            description="Evaluates exposure, enforces stop-losses, and calculates safe position sizing."
                            color="bg-red-500"
                            className="h-full"
                        />
                        <ArrowDown className="w-5 h-5 text-muted-foreground/30" />
                        <div className="text-xs font-mono bg-background/50 px-2 py-1 rounded">Risk Checks</div>
                    </div>
                </div>

                <div className="w-full max-w-3xl border-t border-border mt-8 mb-4" />

                {/* Level 4: Final Output */}
                <div className="relative flex items-center gap-4 bg-gradient-to-r from-background to-secondary/20 p-6 rounded-2xl border border-primary/20 w-full max-w-2xl">
                    <div className="p-3 bg-primary/20 rounded-full text-primary">
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
            <div className="p-4 rounded-lg bg-card border border-border">
                <Cpu className="w-6 h-6 mx-auto mb-2 text-indigo-400" />
                <div className="font-semibold">LangGraph</div>
                <div className="text-xs text-muted-foreground">Orchestration</div>
            </div>
            <div className="p-4 rounded-lg bg-card border border-border">
                <Brain className="w-6 h-6 mx-auto mb-2 text-orange-400" />
                <div className="font-semibold">Gemini Pro</div>
                <div className="text-xs text-muted-foreground">Reasoning Engine</div>
            </div>
             <div className="p-4 rounded-lg bg-card border border-border">
                <LineChart className="w-6 h-6 mx-auto mb-2 text-green-400" />
                <div className="font-semibold">TA-Lib</div>
                <div className="text-xs text-muted-foreground">Technical Analysis</div>
            </div>
             <div className="p-4 rounded-lg bg-card border border-border">
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
