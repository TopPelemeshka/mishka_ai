
import { useEffect, useState } from 'react';
import axios from 'axios';
import { useNavigate } from 'react-router-dom';

interface ConfigItem {
    key: string;
    value: string;
    description: string | null;
    type: string;
}

interface ServiceConfigs {
    [serviceName: string]: ConfigItem[];
}

export default function Settings() {
    const [configs, setConfigs] = useState<ServiceConfigs | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');
    const navigate = useNavigate();

    // Local state for edits: { "custody-service.key": "new_value" }
    const [edits, setEdits] = useState<{ [id: string]: string }>({});
    const [saving, setSaving] = useState<{ [id: string]: boolean }>({});

    const token = localStorage.getItem('token');
    const headers = { Authorization: `Bearer ${token}` };

    useEffect(() => {
        fetchConfigs();
    }, []);

    const fetchConfigs = async () => {
        try {
            setLoading(true);
            const res = await axios.get('/api/admin/configs', { headers });
            setConfigs(res.data);
            setLoading(false);
        } catch (err: any) {
            if (err.response?.status === 401) {
                navigate('/login');
            }
            setError('Failed to load configurations');
            setLoading(false);
        }
    };

    const handleEdit = (service: string, key: string, value: string) => {
        setEdits(prev => ({ ...prev, [`${service}.${key}`]: value }));
    };

    const handleSave = async (service: string, item: ConfigItem) => {
        const id = `${service}.${item.key}`;
        const newValue = edits[id];

        if (newValue === undefined || newValue === item.value) return; // No change

        try {
            setSaving(prev => ({ ...prev, [id]: true }));

            await axios.post('/api/admin/configs', {
                service: service,
                key: item.key,
                value: newValue,
                type: item.type
            }, { headers });

            // Update local state to reflect saved value
            // We can either re-fetch or manual update
            // Let's re-fetch to be safe and get updated list
            await fetchConfigs();

            // Clear edit state for this item
            setEdits(prev => {
                const copy = { ...prev };
                delete copy[id];
                return copy;
            });

            setSaving(prev => ({ ...prev, [id]: false }));
        } catch (err) {
            alert('Failed to save configuration');
            setSaving(prev => ({ ...prev, [id]: false }));
        }
    };

    if (loading) return <div className="p-8 text-center text-gray-500">Loading settings...</div>;

    return (
        <div className="p-4 max-w-4xl mx-auto space-y-6">
            <div className="flex items-center justify-between border-b pb-4">
                <h1 className="text-2xl font-bold">System Configuration</h1>
                <button
                    onClick={() => navigate('/')}
                    className="text-blue-600 hover:text-blue-800"
                >
                    &larr; Back to Dashboard
                </button>
            </div>

            {error && <div className="bg-red-100 text-red-700 p-3 rounded">{error}</div>}

            {configs && Object.keys(configs).map(service => (
                <div key={service} className="bg-white rounded-lg shadow p-6 border border-gray-200">
                    <h2 className="text-xl font-bold mb-4 capitalize border-b pb-2 text-gray-700">
                        {service.replace('mishka-', '').replace('-', ' ')}
                    </h2>

                    <div className="space-y-6">
                        {configs[service].map(item => {
                            const id = `${service}.${item.key}`;
                            const isEditing = edits[id] !== undefined;
                            const currentValue = isEditing ? edits[id] : item.value;
                            const isDirty = isEditing && edits[id] !== item.value;
                            const isSaving = saving[id];

                            return (
                                <div key={item.key} className="grid md:grid-cols-12 gap-4 items-start">
                                    <div className="md:col-span-4">
                                        <label className="block text-sm font-medium text-gray-900 font-mono">
                                            {item.key}
                                        </label>
                                        <p className="text-xs text-gray-500 mt-1">
                                            {item.description || item.type}
                                        </p>
                                    </div>

                                    <div className="md:col-span-8 flex gap-2 items-start">
                                        {item.value.length > 50 || item.key.includes('prompt') || item.key.includes('instructions') ? (
                                            <textarea
                                                className="w-full border rounded p-2 text-sm font-mono h-32 focus:ring-2 focus:ring-blue-500 outline-none"
                                                value={currentValue}
                                                onChange={(e) => handleEdit(service, item.key, e.target.value)}
                                            />
                                        ) : (
                                            <input
                                                type={item.type === 'int' || item.type === 'float' ? 'number' : 'text'}
                                                className="w-full border rounded p-2 text-sm font-mono focus:ring-2 focus:ring-blue-500 outline-none"
                                                value={currentValue}
                                                onChange={(e) => handleEdit(service, item.key, e.target.value)}
                                                step={item.type === 'float' ? '0.1' : '1'}
                                            />
                                        )}

                                        <button
                                            onClick={() => handleSave(service, item)}
                                            disabled={!isDirty || isSaving}
                                            className={`px-3 py-2 rounded text-sm font-medium transition-colors
                                                ${!isDirty
                                                    ? 'bg-gray-100 text-gray-400 cursor-not-allowed'
                                                    : 'bg-green-600 text-white hover:bg-green-700 shadow-sm'
                                                }
                                            `}
                                        >
                                            {isSaving ? '...' : 'Save'}
                                        </button>
                                    </div>
                                </div>
                            );
                        })}
                    </div>
                </div>
            ))}
        </div>
    );
}
