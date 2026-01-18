import { useEffect, useState } from 'react'
import axios from 'axios'
import { useNavigate } from 'react-router-dom';

interface Stats {
    user_requesting: number;
    role: string;
    cpu_load: string;
    memory_usage: string;
    active_chats: number;
    facts_in_memory: number;
}

export default function Dashboard() {
    const [stats, setStats] = useState<Stats | null>(null);
    const [error, setError] = useState('');
    const navigate = useNavigate();

    const [tools, setTools] = useState<any[]>([]);

    useEffect(() => {
        const fetchData = async () => {
            try {
                const token = localStorage.getItem('token');
                const headers = { Authorization: `Bearer ${token}` };

                // Parallel fetch
                const [statsRes, toolsRes] = await Promise.all([
                    axios.get('/api/dashboard/stats', { headers }),
                    axios.get('/api/tools', { headers })
                ]);

                setStats(statsRes.data);
                setTools(toolsRes.data);
            } catch (err: any) {
                if (err.response?.status === 401) {
                    localStorage.removeItem('token');
                    navigate('/login');
                }
                setError('Failed to fetch data');
            }
        };
        fetchData();
    }, [navigate]);

    const logout = () => {
        localStorage.removeItem('token');
        navigate('/login');
    }

    const isSuperadmin = stats?.role === 'superadmin';

    return (
        <div className="p-4 space-y-6 max-w-4xl mx-auto">
            <div className="flex justify-between items-center border-b pb-4">
                <div>
                    <h1 className="text-2xl font-bold">Mishka Dashboard</h1>
                    {stats && (
                        <span className={`text-xs px-2 py-1 rounded ${isSuperadmin ? 'bg-red-100 text-red-800' : 'bg-blue-100 text-blue-800'}`}>
                            {stats.role}
                        </span>
                    )}
                </div>
                <div className="flex gap-4 items-center">
                    {isSuperadmin && (
                        <>
                            <button
                                onClick={() => navigate('/settings')}
                                className="text-sm font-medium text-blue-600 hover:text-blue-800 bg-blue-50 px-3 py-1 rounded"
                            >
                                Config Settings
                            </button>
                            <button
                                onClick={() => navigate('/personality')}
                                className="text-sm font-medium text-purple-600 hover:text-purple-800 bg-purple-50 px-3 py-1 rounded"
                            >
                                Personality
                            </button>
                            <button
                                onClick={() => navigate('/monitoring')}
                                className="text-sm font-medium text-green-600 hover:text-green-800 bg-green-50 px-3 py-1 rounded"
                            >
                                Monitoring
                            </button>
                        </>
                    )}
                    <button onClick={logout} className="text-sm text-gray-500 hover:text-red-500">Logout</button>
                </div>
            </div>

            {error && <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded">{error}</div>}

            {!stats ? (
                <div className="text-center py-10 text-gray-500">Loading...</div>
            ) : (
                <div className="space-y-8">
                    {/* Stats Grid */}
                    <section>
                        <h2 className="text-lg font-semibold mb-3">Statistics</h2>
                        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                            <Card title="Active Chats" value={stats.active_chats} />
                            <Card title="CPU Load" value={stats.cpu_load} />
                            <Card title="RAM Usage" value={stats.memory_usage} />
                            <Card title="Facts Stored" value={stats.facts_in_memory} />
                        </div>
                    </section>

                    {/* Tools List */}
                    <section>
                        <h2 className="text-lg font-semibold mb-3 flex items-center justify-between">
                            Connected Tools
                            <span className="text-xs font-normal text-gray-500">{tools.length} available</span>
                        </h2>
                        <div className="grid gap-4 md:grid-cols-2">
                            {tools.map((tool: any, idx) => (
                                <div key={idx} className="bg-white p-4 rounded-lg shadow border border-gray-200">
                                    <div className="flex justify-between items-start mb-2">
                                        <h3 className="font-bold text-lg">{tool.name}</h3>
                                        <span className="text-xs bg-gray-100 px-2 py-1 rounded">{tool.endpoint.split(':')[2]?.split('/')[0] || 'Unknown Port'}</span>
                                    </div>
                                    <p className="text-sm text-gray-600 mb-4 h-10 line-clamp-2">{tool.description}</p>

                                    {/* Config Preview */}
                                    <div className="bg-gray-900 text-green-400 p-2 rounded text-xs font-mono overflow-x-auto mb-3">
                                        {JSON.stringify(tool.parameters, null, 2)}
                                    </div>

                                    {isSuperadmin ? (
                                        <button className="w-full bg-blue-600 text-white py-1 rounded hover:bg-blue-700 text-sm">
                                            Edit Configuration
                                        </button>
                                    ) : (
                                        <div className="text-center text-xs text-gray-400 italic">
                                            Read-only access
                                        </div>
                                    )}
                                </div>
                            ))}
                        </div>
                    </section>

                    <div className="text-xs text-gray-400 text-center mt-10">
                        User ID: {stats.user_requesting}
                    </div>
                </div>
            )}
        </div>
    )
}

const Card = ({ title, value }: { title: string, value: string | number }) => (
    <div className="p-4 bg-white dark:bg-gray-800 shadow rounded-lg border border-gray-200 dark:border-gray-700">
        <h3 className="text-sm text-gray-500 dark:text-gray-400">{title}</h3>
        <p className="text-2xl font-bold mt-1">{value}</p>
    </div>
)
