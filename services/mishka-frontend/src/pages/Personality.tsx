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



const PersonalityPage: React.FC = () => {
    const [personalities, setPersonalities] = useState<Personality[]>([]);
    const [loading, setLoading] = useState(false);
    const [evolving, setEvolving] = useState(false);
    const [error, setError] = useState("");
    const navigate = useNavigate();

    const token = localStorage.getItem("token");

    const fetchPersonalities = async () => {
        try {
            const res = await axios.get(`${API_URL}/admin/personalities`, {
                headers: { Authorization: `Bearer ${token}` }
            });
            setPersonalities(res.data);
        } catch (err: any) {
            setError("Failed to load personalities");
        }
    };

    useEffect(() => {
        if (!token) {
            navigate("/login");
            return;
        }
        fetchPersonalities();
    }, [token, navigate]);

    const handleActivate = async (id: string) => {
        try {
            setLoading(true);
            await axios.post(`${API_URL}/admin/personalities/${id}/activate`, {}, {
                headers: { Authorization: `Bearer ${token}` }
            });
            await fetchPersonalities(); // Refresh
        } catch (err: any) {
            setError("Failed to activate");
        } finally {
            setLoading(false);
        }
    };

    const handleEvolve = async () => {
        try {
            setEvolving(true);
            const res = await axios.post(`${API_URL}/admin/personalities/evolve`,
                { reason: "Manual Admin Trigger" },
                { headers: { Authorization: `Bearer ${token}` } }
            );
            alert(`Evolution Complete! New Traits:\n${res.data.traits}`);
        } catch (err: any) {
            alert(`Evolution Failed: ${err.response?.data?.detail || err.message}`);
        } finally {
            setEvolving(false);
        }
    };

    const handleReset = async () => {
        if (!confirm("Are you sure? This will clear acquired traits.")) return;
        try {
            await axios.post(`${API_URL}/admin/personalities/reset`, {},
                { headers: { Authorization: `Bearer ${token}` } }
            );
            alert("Traits reset.");
        } catch (err: any) {
            alert("Reset failed.");
        }
    }

    return (
        <div style={{ padding: "20px", fontFamily: "sans-serif", maxWidth: "800px", margin: "0 auto" }}>
            <h1>Personality Manager</h1>
            <button onClick={() => navigate("/dashboard")} style={{ marginBottom: "20px" }}>&larr; Back</button>

            {error && <div style={{ color: "red", marginBottom: "10px" }}>{error}</div>}

            <div style={{ display: "flex", gap: "10px", marginBottom: "20px" }}>
                <button
                    onClick={handleEvolve}
                    disabled={evolving}
                    style={{
                        padding: "10px 20px",
                        backgroundColor: evolving ? "#ccc" : "#6200ea",
                        color: "white",
                        border: "none",
                        borderRadius: "5px",
                        cursor: "pointer"
                    }}
                >
                    {evolving ? "Analyzing History..." : "Force Evolve (Analyze Chat)"}
                </button>

                <button
                    onClick={handleReset}
                    style={{
                        padding: "10px 20px",
                        backgroundColor: "#d32f2f",
                        color: "white",
                        border: "none",
                        borderRadius: "5px",
                        cursor: "pointer"
                    }}
                >
                    Reset Traits
                </button>
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "1fr", gap: "10px" }}>
                {personalities.map(p => (
                    <div key={p.id} style={{
                        border: p.is_active ? "2px solid #6200ea" : "1px solid #ccc",
                        padding: "15px",
                        borderRadius: "8px",
                        backgroundColor: p.is_active ? "#f3e5f5" : "white"
                    }}>
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                            <h3>{p.name} {p.is_active && "(Active)"}</h3>
                            {!p.is_active && (
                                <button
                                    onClick={() => handleActivate(p.id)}
                                    disabled={loading}
                                    style={{ padding: "5px 10px", cursor: "pointer" }}
                                >
                                    Activate
                                </button>
                            )}
                        </div>
                        <p style={{ whiteSpace: "pre-wrap", color: "#555" }}>{p.base_prompt}</p>
                    </div>
                ))}
            </div>
        </div>
    );
};

export default PersonalityPage;
