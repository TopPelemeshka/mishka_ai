import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { useNavigate } from 'react-router-dom';

const API_URL = "http://localhost:8081";

interface Personality {
    id: string;
    name: string;
    base_prompt: string;
    is_active: boolean;
}

interface EvolutionLog {
    id: string;
    traits: string;
    reason: string;
    created_at: string;
}

const PersonalityPage: React.FC = () => {
    const [personalities, setPersonalities] = useState<Personality[]>([]);
    const [activePersonality, setActivePersonality] = useState<Personality | null>(null);
    const [activeHistory, setActiveHistory] = useState<EvolutionLog[]>([]);

    // UI State
    const [loading, setLoading] = useState(false);
    const [evolving, setEvolving] = useState(false);
    const [error, setError] = useState("");

    // Modal State
    const [showModal, setShowModal] = useState(false);
    const [isEditing, setIsEditing] = useState(false);
    const [editId, setEditId] = useState("");
    const [pName, setPName] = useState("");
    const [pPrompt, setPPrompt] = useState("");

    const navigate = useNavigate();
    const token = localStorage.getItem("token");

    // --- Data Fetching ---
    const fetchData = async () => {
        try {
            setLoading(true);
            const res = await axios.get(`${API_URL}/admin/personalities`, {
                headers: { Authorization: `Bearer ${token}` }
            });
            const all: Personality[] = res.data;
            setPersonalities(all);

            const active = all.find(p => p.is_active);
            setActivePersonality(active || null);

            if (active) {
                const histRes = await axios.get(`${API_URL}/admin/personalities/${active.id}/history`, {
                    headers: { Authorization: `Bearer ${token}` }
                });
                setActiveHistory(histRes.data);
            }
        } catch (err: any) {
            setError("Failed to load data");
            if (err.response?.status === 401) navigate("/login");
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        if (!token) {
            navigate("/login");
            return;
        }
        fetchData();
    }, [token, navigate]);

    // --- Actions ---

    const openCreate = () => {
        setIsEditing(false);
        setPName("");
        setPPrompt("");
        setShowModal(true);
    };

    const openEdit = (p: Personality) => {
        setIsEditing(true);
        setEditId(p.id);
        setPName(p.name);
        setPPrompt(p.base_prompt);
        setShowModal(true);
    };

    const handleSave = async () => {
        try {
            if (isEditing) {
                await axios.put(`${API_URL}/admin/personalities/${editId}`,
                    { name: pName, base_prompt: pPrompt },
                    { headers: { Authorization: `Bearer ${token}` } }
                );
            } else {
                await axios.post(`${API_URL}/admin/personalities`,
                    { name: pName, base_prompt: pPrompt },
                    { headers: { Authorization: `Bearer ${token}` } }
                );
            }
            setShowModal(false);
            fetchData();
        } catch (err: any) {
            alert("Save failed");
        }
    };

    const handleActivate = async (id: string, e: React.MouseEvent) => {
        e.stopPropagation();
        if (!confirm("Activate this personality?")) return;
        try {
            await axios.post(`${API_URL}/admin/personalities/${id}/activate`, {}, {
                headers: { Authorization: `Bearer ${token}` }
            });
            fetchData();
        } catch (err: any) {
            alert("Activation failed");
        }
    };

    const handleEvolve = async () => {
        try {
            setEvolving(true);
            await axios.post(`${API_URL}/admin/personalities/evolve`,
                { reason: "Manual Admin Trigger" },
                { headers: { Authorization: `Bearer ${token}` } }
            );
            setTimeout(fetchData, 1000);
        } catch (err: any) {
            alert(`Evolution Failed: ${err.response?.data?.detail || err.message}`);
        } finally {
            setEvolving(false);
        }
    };

    const handleRollback = async (logId: string) => {
        if (!activePersonality) return;
        if (!confirm("Rollback to this state? (Creates a new revert entry)")) return;
        try {
            await axios.post(`${API_URL}/admin/evolution/${activePersonality.id}/rollback`,
                { target_log_id: logId },
                { headers: { Authorization: `Bearer ${token}` } }
            );
            fetchData();
        } catch (err: any) {
            alert("Rollback failed");
        }
    };

    // --- Components ---

    const ActiveDashboard = () => (
        <div className="bg-white p-6 rounded-lg shadow-md mb-8 border-l-4 border-purple-600">
            <h2 className="text-2xl font-bold mb-4 flex items-center justify-between">
                Active Soul: {activePersonality?.name || "None"}
                {activePersonality && <span className="text-sm bg-purple-100 text-purple-800 px-3 py-1 rounded-full">ACTIVE</span>}
            </h2>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div>
                    <h3 className="font-semibold text-gray-500 mb-2">Base Prompt</h3>
                    <div className="bg-gray-50 p-4 rounded text-sm whitespace-pre-wrap h-40 overflow-y-auto border">
                        {activePersonality?.base_prompt}
                    </div>
                </div>

                <div>
                    <h3 className="font-semibold text-gray-500 mb-2">Current Evolution Traits</h3>
                    <div className="bg-yellow-50 p-4 rounded text-sm text-gray-800 whitespace-pre-wrap h-40 overflow-y-auto border border-yellow-200">
                        {activeHistory.length > 0 ? activeHistory[0].traits : "No evolved traits yet."}
                    </div>
                </div>
            </div>

            <div className="mt-6 flex justify-end">
                <button
                    onClick={handleEvolve}
                    disabled={evolving}
                    className={`px-6 py-2 rounded font-bold text-white shadow transition
                        ${evolving ? 'bg-gray-400 cursor-not-allowed' : 'bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-700 hover:to-indigo-700'}
                    `}
                >
                    {evolving ?
                        <span className="flex items-center">
                            <svg className="animate-spin -ml-1 mr-3 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                            </svg>
                            Psychologist is analyzing...
                        </span>
                        : "Force Evolve"
                    }
                </button>
            </div>
        </div>
    );

    const Timeline = () => (
        <div className="bg-white p-6 rounded-lg shadow-md mb-8">
            <h3 className="text-xl font-bold mb-4 text-gray-800">Evolution Timeline</h3>
            <div className="overflow-x-auto">
                <table className="min-w-full text-left">
                    <thead>
                        <tr className="border-b bg-gray-50">
                            <th className="p-3 text-sm font-semibold text-gray-600">Date</th>
                            <th className="p-3 text-sm font-semibold text-gray-600">Reason</th>
                            <th className="p-3 text-sm font-semibold text-gray-600">Traits Snapshot</th>
                            <th className="p-3 text-sm font-semibold text-gray-600">Action</th>
                        </tr>
                    </thead>
                    <tbody>
                        {activeHistory.map((log) => (
                            <tr key={log.id} className="border-b hover:bg-gray-50 transition">
                                <td className="p-3 text-sm text-gray-500">
                                    {new Date(log.created_at).toLocaleString()}
                                </td>
                                <td className="p-3 text-sm text-gray-800 font-medium">{log.reason}</td>
                                <td className="p-3 text-xs text-gray-500 font-mono max-w-md truncate" title={log.traits}>
                                    {log.traits || "None"}
                                </td>
                                <td className="p-3">
                                    <button
                                        onClick={() => handleRollback(log.id)}
                                        className="text-xs bg-red-100 text-red-700 px-2 py-1 rounded hover:bg-red-200"
                                    >
                                        Rollback
                                    </button>
                                </td>
                            </tr>
                        ))}
                        {activeHistory.length === 0 && (
                            <tr>
                                <td colSpan={4} className="p-4 text-center text-gray-400">No evolution history recorded yet.</td>
                            </tr>
                        )}
                    </tbody>
                </table>
            </div>
        </div>
    );

    const PersonalityLibrary = () => (
        <div className="bg-white p-6 rounded-lg shadow-md">
            <div className="flex justify-between items-center mb-4">
                <h3 className="text-xl font-bold text-gray-800">Library</h3>
                <button
                    onClick={openCreate}
                    className="bg-green-600 text-white px-3 py-1 rounded text-sm hover:bg-green-700"
                >
                    + New Personality
                </button>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {personalities.map(p => (
                    <div key={p.id} className={`p-4 rounded border relative group ${p.is_active ? 'border-purple-500 bg-purple-50' : 'border-gray-200 hover:border-blue-400'}`}>
                        {p.is_active && <div className="absolute top-2 right-2 w-2 h-2 bg-purple-500 rounded-full"></div>}

                        <div className="mb-8">
                            <h4 className="font-bold text-gray-800">{p.name}</h4>
                            <p className="text-xs text-gray-500 mt-2 line-clamp-3">{p.base_prompt}</p>
                        </div>

                        <div className="absolute bottom-4 left-4 right-4 flex gap-2">
                            <button
                                onClick={() => openEdit(p)}
                                className="flex-1 py-1 rounded border border-gray-300 text-gray-600 text-xs hover:bg-gray-100"
                            >
                                Edit
                            </button>
                            {!p.is_active && (
                                <button
                                    onClick={(e) => handleActivate(p.id, e)}
                                    className="flex-1 py-1 rounded border border-purple-600 text-purple-600 text-xs hover:bg-purple-600 hover:text-white transition"
                                >
                                    Activate
                                </button>
                            )}
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );

    return (
        <div className="min-h-screen bg-gray-100 p-8">
            <div className="max-w-6xl mx-auto">
                {/* Header */}
                <div className="flex items-center justify-between mb-8">
                    <div>
                        <h1 className="text-3xl font-extrabold text-gray-900">Soul Management</h1>
                        <p className="text-gray-500">Monitor and guide Mishka's evolution</p>
                    </div>
                    <button onClick={() => navigate("/dashboard")} className="text-gray-600 hover:text-gray-900 font-medium">
                        &larr; Back to Dashboard
                    </button>
                </div>

                {error && <div className="bg-red-100 border-l-4 border-red-500 text-red-700 p-4 mb-6">{error}</div>}

                {/* Main Content */}
                {loading && !activePersonality ? (
                    <div className="text-center py-10">Loading soul data...</div>
                ) : (
                    <>
                        <ActiveDashboard />
                        <Timeline />
                        <PersonalityLibrary />
                    </>
                )}

                {/* Create/Edit Modal */}
                {showModal && (
                    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
                        <div className="bg-white p-6 rounded-lg w-full max-w-md">
                            <h2 className="text-xl font-bold mb-4">{isEditing ? "Edit Personality" : "Create New Personality"}</h2>
                            <input
                                className="w-full border p-2 rounded mb-3"
                                placeholder="Name (e.g. Pirate Mishka)"
                                value={pName}
                                onChange={e => setPName(e.target.value)}
                            />
                            <textarea
                                className="w-full border p-2 rounded mb-4 h-32"
                                placeholder="Base System Prompt..."
                                value={pPrompt}
                                onChange={e => setPPrompt(e.target.value)}
                            />
                            <div className="flex justify-end gap-2">
                                <button onClick={() => setShowModal(false)} className="px-4 py-2 text-gray-600 hover:bg-gray-100 rounded">Cancel</button>
                                <button onClick={handleSave} className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700">
                                    {isEditing ? "Save Changes" : "Create"}
                                </button>
                            </div>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
};

export default PersonalityPage;
