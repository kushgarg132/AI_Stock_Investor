import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { useNavigate } from 'react-router-dom';
import { ArrowLeft, Save, Plus, Trash2, GraduationCap, TrendingUp, Shield, Target, Zap, Eye, CheckCircle, AlertCircle, Edit3 } from 'lucide-react';

// Available icons for goals
const iconOptions = [
    { name: 'Target', icon: Target },
    { name: 'Education', icon: GraduationCap },
    { name: 'Growth', icon: TrendingUp },
    { name: 'Shield', icon: Shield },
    { name: 'Zap', icon: Zap },
    { name: 'Eye', icon: Eye },
];

const colorOptions = ['blue', 'green', 'orange', 'purple', 'pink', 'cyan'];

const GoalsPage = () => {
    const navigate = useNavigate();
    const [saving, setSaving] = useState(false);
    const [message, setMessage] = useState(null);

    const [goals, setGoals] = useState([
        {
            id: 1,
            iconName: 'Education',
            title: 'Educational Focus',
            color: 'blue',
            description: 'Educate users on algorithmic trading with focus on technical analysis patterns and the underlying causes and reasoning for using these.'
        },
        {
            id: 2,
            iconName: 'Growth',
            title: 'Profit Target',
            color: 'green',
            description: 'Generate a profit of 5% monthly with minimum drawdown.'
        },
        {
            id: 3,
            iconName: 'Shield',
            title: 'Risk Management',
            color: 'orange',
            description: 'Have guard rails to prevent extreme losses.'
        }
    ]);

    const [editingId, setEditingId] = useState(null);
    const [editData, setEditData] = useState({ title: '', description: '' });

    useEffect(() => {
        fetchGoals();
    }, []);

    const fetchGoals = async () => {
        try {
            const response = await axios.get('http://localhost:8001/api/v1/goals/parsed');
            if (response.data.goals && response.data.goals.length > 0) {
                setGoals(response.data.goals);
            }
        } catch (err) {
            console.log('Using default goals');
        }
    };

    const startEdit = (goal) => {
        setEditingId(goal.id);
        setEditData({ title: goal.title, description: goal.description });
    };

    const cancelEdit = () => {
        setEditingId(null);
        setEditData({ title: '', description: '' });
    };

    const saveEdit = (goalId) => {
        setGoals(prev => prev.map(g =>
            g.id === goalId
                ? { ...g, title: editData.title, description: editData.description }
                : g
        ));
        setEditingId(null);
        setEditData({ title: '', description: '' });
    };

    const addNewGoal = () => {
        const newId = Math.max(...goals.map(g => g.id), 0) + 1;
        const newGoal = {
            id: newId,
            iconName: 'Target',
            title: 'New Goal',
            color: colorOptions[newId % colorOptions.length],
            description: 'Click to edit this goal description...'
        };
        setGoals([...goals, newGoal]);
        // Automatically start editing the new goal
        setEditingId(newId);
        setEditData({ title: newGoal.title, description: newGoal.description });
    };

    const deleteGoal = (goalId) => {
        if (goals.length <= 1) {
            setMessage({ type: 'error', text: 'Must have at least one goal' });
            setTimeout(() => setMessage(null), 3000);
            return;
        }
        setGoals(goals.filter(g => g.id !== goalId));
    };

    const changeIcon = (goalId, iconName) => {
        setGoals(prev => prev.map(g =>
            g.id === goalId ? { ...g, iconName } : g
        ));
    };

    const saveAllGoals = async () => {
        setSaving(true);
        setMessage(null);

        // Generate GOALS.md content
        const goalsContent = `# AI Stock Investor - Project Goals

> **This file defines the core objectives of the AI Stock Investor system.**
> All AI agents, strategies, and system components should align with these goals.
> Users can update this file as needed. Systems should re-read this file for current objectives.

---

## 🎯 Primary Goals

${goals.map((goal, index) => `### ${index + 1}. ${goal.title}
**Objective**: ${goal.description}
`).join('\n')}

---

## 📊 Key Performance Indicators (KPIs)

| Metric | Target | Minimum Acceptable |
|--------|--------|-------------------|
| Monthly Return | +5% | +2% |
| Maximum Drawdown | <5% | <10% |
| Win Rate | >60% | >50% |
| Risk/Reward Ratio | >2:1 | >1.5:1 |

---

## 🛡️ Risk Rules (Non-Negotiable)

1. **NO trade without a stop-loss**
2. **NO position larger than 5% of portfolio**
3. **STOP trading after 3 consecutive losses (cool-off period)**
4. **HALT system if daily loss exceeds -2%**
5. **HALT system if drawdown exceeds -10%**

---

## 🔄 Update Log

| Date | Changes |
|------|---------|
| ${new Date().toISOString().split('T')[0]} | Goals updated via UI |

---

*Last Updated: ${new Date().toLocaleString()}*
`;

        try {
            await axios.post('http://localhost:8001/api/v1/goals/save', { content: goalsContent });
            await axios.post('http://localhost:8001/api/v1/goals/reload');
            setMessage({ type: 'success', text: 'Goals saved to GOALS.md!' });
            setTimeout(() => setMessage(null), 3000);
        } catch (err) {
            setMessage({ type: 'error', text: 'Failed to save goals' });
        } finally {
            setSaving(false);
        }
    };

    const getColorClasses = (color) => {
        const colors = {
            blue: 'bg-blue-600',
            green: 'bg-green-600',
            orange: 'bg-orange-600',
            purple: 'bg-purple-600',
            pink: 'bg-pink-600',
            cyan: 'bg-cyan-600'
        };
        return colors[color] || colors.blue;
    };

    const getIcon = (iconName) => {
        const found = iconOptions.find(i => i.name === iconName);
        return found ? found.icon : Target;
    };

    return (
        <div className="min-h-screen bg-slate-900 text-white">
            {/* Header */}
            <header className="border-b border-slate-800 bg-slate-900/80 backdrop-blur-md sticky top-0 z-50">
                <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-4 flex items-center justify-between">
                    <div className="flex items-center gap-4">
                        <button
                            onClick={() => navigate('/')}
                            className="p-2 hover:bg-slate-800 rounded-lg transition-colors"
                        >
                            <ArrowLeft className="w-5 h-5 text-slate-400" />
                        </button>
                        <h1 className="text-xl font-bold text-white">Project Goals</h1>
                    </div>
                    <div className="flex items-center gap-3">
                        <button
                            onClick={addNewGoal}
                            className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-white rounded-lg flex items-center gap-2 transition-colors"
                        >
                            <Plus className="w-4 h-4" />
                            Add Goal
                        </button>
                        <button
                            onClick={saveAllGoals}
                            disabled={saving}
                            className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-lg flex items-center gap-2 transition-colors disabled:opacity-50"
                        >
                            <Save className="w-4 h-4" />
                            {saving ? 'Saving...' : 'Save All'}
                        </button>
                    </div>
                </div>
            </header>

            {/* Message Banner */}
            {message && (
                <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 pt-4">
                    <div className={`p-4 rounded-xl flex items-center gap-3 ${message.type === 'success'
                        ? 'bg-green-500/10 border border-green-500/30 text-green-400'
                        : 'bg-red-500/10 border border-red-500/30 text-red-400'
                        }`}>
                        {message.type === 'success' ? <CheckCircle className="w-5 h-5" /> : <AlertCircle className="w-5 h-5" />}
                        <p>{message.text}</p>
                    </div>
                </div>
            )}

            {/* Goals Cards */}
            <main className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
                <div className="grid gap-6">
                    {goals.map((goal, index) => {
                        const Icon = getIcon(goal.iconName);
                        const isEditing = editingId === goal.id;

                        return (
                            <div
                                key={goal.id}
                                className="bg-slate-800/50 rounded-2xl border border-slate-700 p-6 hover:border-slate-600 transition-colors"
                            >
                                <div className="flex items-start gap-4">
                                    {/* Icon with dropdown */}
                                    <div className="relative group">
                                        <div className={`w-12 h-12 rounded-xl flex items-center justify-center flex-shrink-0 cursor-pointer ${getColorClasses(goal.color)}`}>
                                            <Icon className="w-6 h-6 text-white" />
                                        </div>
                                        {/* Icon selector dropdown */}
                                        <div className="absolute left-0 top-14 bg-slate-800 rounded-lg border border-slate-700 p-2 hidden group-hover:flex gap-1 z-10">
                                            {iconOptions.map(opt => {
                                                const OptIcon = opt.icon;
                                                return (
                                                    <button
                                                        key={opt.name}
                                                        onClick={() => changeIcon(goal.id, opt.name)}
                                                        className="p-2 hover:bg-slate-700 rounded-lg transition-colors"
                                                        title={opt.name}
                                                    >
                                                        <OptIcon className="w-4 h-4 text-slate-300" />
                                                    </button>
                                                );
                                            })}
                                        </div>
                                    </div>

                                    <div className="flex-1">
                                        <div className="flex items-center justify-between mb-2">
                                            <span className="text-slate-500 text-sm font-medium">Goal {index + 1}</span>
                                            <div className="flex items-center gap-2">
                                                {!isEditing && (
                                                    <button
                                                        onClick={() => startEdit(goal)}
                                                        className="p-1.5 hover:bg-slate-700 rounded-lg transition-colors"
                                                        title="Edit"
                                                    >
                                                        <Edit3 className="w-4 h-4 text-slate-400" />
                                                    </button>
                                                )}
                                                <button
                                                    onClick={() => deleteGoal(goal.id)}
                                                    className="p-1.5 hover:bg-red-500/20 rounded-lg transition-colors"
                                                    title="Delete"
                                                >
                                                    <Trash2 className="w-4 h-4 text-red-400" />
                                                </button>
                                            </div>
                                        </div>

                                        {isEditing ? (
                                            <div className="space-y-3">
                                                <input
                                                    type="text"
                                                    value={editData.title}
                                                    onChange={(e) => setEditData({ ...editData, title: e.target.value })}
                                                    className="w-full bg-slate-900 text-white text-lg font-semibold p-2 rounded-lg border border-slate-600 focus:border-blue-500 outline-none"
                                                    placeholder="Goal title..."
                                                />
                                                <textarea
                                                    value={editData.description}
                                                    onChange={(e) => setEditData({ ...editData, description: e.target.value })}
                                                    className="w-full bg-slate-900 text-slate-200 p-3 rounded-lg border border-slate-600 focus:border-blue-500 outline-none resize-none"
                                                    rows={3}
                                                    placeholder="Goal description..."
                                                />
                                                <div className="flex gap-2">
                                                    <button
                                                        onClick={() => saveEdit(goal.id)}
                                                        className="px-3 py-1.5 bg-blue-600 hover:bg-blue-500 text-white text-sm rounded-lg transition-colors"
                                                    >
                                                        Save
                                                    </button>
                                                    <button
                                                        onClick={cancelEdit}
                                                        className="px-3 py-1.5 bg-slate-700 hover:bg-slate-600 text-white text-sm rounded-lg transition-colors"
                                                    >
                                                        Cancel
                                                    </button>
                                                </div>
                                            </div>
                                        ) : (
                                            <>
                                                <h3 className="text-lg font-semibold text-white mb-2">{goal.title}</h3>
                                                <p className="text-slate-300 leading-relaxed">{goal.description}</p>
                                            </>
                                        )}
                                    </div>
                                </div>
                            </div>
                        );
                    })}
                </div>

                {/* Tip */}
                <p className="text-center text-slate-500 text-sm mt-8">
                    Click the edit icon to modify goals • Hover on icons to change them • Click "Save All" to update GOALS.md
                </p>
            </main>
        </div>
    );
};

export default GoalsPage;
