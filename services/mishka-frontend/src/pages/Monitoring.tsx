import { useEffect, useState } from "react";
import axios from "axios";
import { Activity, Server, ShieldAlert } from 'lucide-react';

// Access Vite env vars safely
const API_URL = (import.meta as any).env.VITE_API_URL || "http://localhost:8080";

// Types
interface ServiceHealth {
    service_name: string;
    status: string;
    last_seen: string;
    details: string;
}

interface SystemError {
    id: number;
    service: string;
    level: string;
    message: string;
    traceback: string;
    created_at: string;
}

export default function Monitoring() {
    const [health, setHealth] = useState<ServiceHealth[]>([]);
    const [errors, setErrors] = useState<SystemError[]>([]);
    const token = localStorage.getItem("token");

    const fetchData = async () => {
        try {
            const [hResp, eResp] = await Promise.all([
                axios.get(`${API_URL}/monitoring/health`, { headers: { Authorization: `Bearer ${token}` } }),
                axios.get(`${API_URL}/monitoring/errors`, { headers: { Authorization: `Bearer ${token}` } })
            ]);
            setHealth(hResp.data);
            setErrors(eResp.data);
        } catch (e) {
            console.error(e);
        }
    };

    useEffect(() => {
        fetchData();
        const interval = setInterval(fetchData, 10000); // Poll every 10s
        return () => clearInterval(interval);
    }, []);

    const getStatusColor = (status: string) => {
        if (status === "healthy") return "bg-green-100 text-green-800 border-green-200";
        if (status === "unhealthy") return "bg-yellow-100 text-yellow-800 border-yellow-200";
        return "bg-red-100 text-red-800 border-red-200";
    };

    return (
        <div className="min-h-screen bg-gray-50 p-8">
            <div className="max-w-7xl mx-auto">
                <header className="mb-8 flex items-center gap-3">
                    <Activity size={32} className="text-blue-600" />
                    <div>
                        <h1 className="text-3xl font-bold text-gray-900">System Monitoring</h1>
                        <p className="text-gray-500">Real-time health status and error logs</p>
                    </div>
                </header>

                {/* Health Grid */}
                <h2 className="text-xl font-semibold mb-4 flex items-center gap-2"><Server size={20} /> Service Health</h2>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
                    {health.map(svc => (
                        <div key={svc.service_name} className={`p-4 rounded-lg border flex flex-col justify-between ${getStatusColor(svc.status)}`}>
                            <div className="flex justify-between items-start mb-2">
                                <span className="font-bold text-lg">{svc.service_name}</span>
                                <span className="text-xs font-mono uppercase px-2 py-1 bg-white bg-opacity-50 rounded">{svc.status}</span>
                            </div>
                            <div className="text-xs opacity-75">
                                Last seen: {new Date(svc.last_seen).toLocaleTimeString()}
                            </div>
                            {svc.details && (
                                <div className="mt-2 text-xs bg-white bg-opacity-50 p-1 rounded font-mono truncate">
                                    {svc.details}
                                </div>
                            )}
                        </div>
                    ))}
                </div>

                {/* Error Log */}
                <h2 className="text-xl font-semibold mb-4 flex items-center gap-2"><ShieldAlert size={20} /> System Errors (Last 50)</h2>
                <div className="bg-white rounded-lg shadow overflow-hidden">
                    <table className="min-w-full divide-y divide-gray-200">
                        <thead className="bg-gray-50">
                            <tr>
                                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Time</th>
                                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Service</th>
                                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Level</th>
                                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Message</th>
                            </tr>
                        </thead>
                        <tbody className="bg-white divide-y divide-gray-200">
                            {errors.map(err => (
                                <tr key={err.id} className="hover:bg-gray-50">
                                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                                        {new Date(err.created_at).toLocaleString()}
                                    </td>
                                    <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                                        {err.service}
                                    </td>
                                    <td className="px-6 py-4 whitespace-nowrap text-sm">
                                        <span className={`px-2 inline-flex text-xs leading-5 font-semibold rounded-full ${err.level === 'CRITICAL' ? 'bg-red-200 text-red-800' : 'bg-orange-100 text-orange-800'}`}>
                                            {err.level}
                                        </span>
                                    </td>
                                    <td className="px-6 py-4 text-sm text-gray-500 max-w-xl break-words">
                                        <details>
                                            <summary className="cursor-pointer hover:text-blue-600">{err.message.slice(0, 80)}...</summary>
                                            <pre className="mt-2 text-xs bg-gray-100 p-2 rounded overflow-auto max-h-40">
                                                {err.traceback || "No traceback"}
                                            </pre>
                                        </details>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    );
}
