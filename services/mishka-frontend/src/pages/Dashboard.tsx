import { useEffect, useState } from 'react'
import axios from 'axios'
import { useNavigate } from 'react-router-dom';

interface Stats {
    user_requesting: number;
    cpu_load: string;
    memory_usage: string;
    active_chats: number;
}

export default function Dashboard() {
    const [stats, setStats] = useState<Stats | null>(null);
    const [error, setError] = useState('');
    const navigate = useNavigate();

    useEffect(() => {
        const fetchStats = async () => {
            try {
                const token = localStorage.getItem('token');
                const res = await axios.get('/api/stats', {
                    headers: { Authorization: `Bearer ${token}` }
                });
                setStats(res.data);
            } catch (err: any) {
                if (err.response?.status === 401) {
                    localStorage.removeItem('token');
                    navigate('/login');
                }
                setError('Failed to fetch stats');
            }
        };
        fetchStats();
    }, [navigate]);

    const logout = () => {
        localStorage.removeItem('token');
        navigate('/login');
    }

    return (
        <div className="p-4 space-y-6">
            <div className="flex justify-between items-center">
                <h1 className="text-xl font-bold">Dashboard</h1>
                <button onClick={logout} className="text-sm text-red-500">Logout</button>
            </div>

            {error && <p className="text-red-500">{error}</p>}

            {!stats ? (
                <p>Loading...</p>
            ) : (
                <div className="grid grid-cols-2 gap-4">
                    <Card title="Active Chats" value={stats.active_chats} />
                    <Card title="CPU Load" value={stats.cpu_load} />
                    <Card title="RAM Usage" value={stats.memory_usage} />
                    <div className="col-span-2 p-4 bg-gray-100 dark:bg-gray-800 rounded-lg">
                        <p className="text-xs text-gray-500">Logged in as ID: {stats.user_requesting}</p>
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
