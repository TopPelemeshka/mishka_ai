import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import axios from 'axios'
import WebApp from '@twa-dev/sdk'

export default function Login() {
    const [password, setPassword] = useState('')
    const [error, setError] = useState('')
    const navigate = useNavigate()

    const handleLogin = async () => {
        try {
            setError('');
            // Use real initData from TWA or mock if empty (dev)
            const initData = WebApp.initData || "dev";

            // Note: In dev mode without TWA, initData is empty, backend will 401. 
            // In PROD inside Telegram, it works.

            const response = await axios.post('/api/auth/login', {
                initData: initData,
                password: password
            });

            const { access_token } = response.data;
            if (access_token) {
                localStorage.setItem('token', access_token);
                navigate('/');
            }
        } catch (err: any) {
            console.error(err);
            setError('Login failed: ' + (err.response?.data?.detail || err.message));
        }
    }

    return (
        <div className="flex flex-col items-center justify-center min-h-screen p-4">
            <h1 className="text-2xl font-bold mb-6">Mishka Admin Protected</h1>
            <div className="w-full max-w-xs space-y-4">
                <input
                    type="password"
                    placeholder="Master Password"
                    className="w-full p-2 border rounded text-black"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                />
                <button
                    onClick={handleLogin}
                    className="w-full bg-blue-500 text-white p-2 rounded hover:bg-blue-600 font-medium"
                >
                    Login
                </button>
                {error && <p className="text-red-500 text-sm">{error}</p>}

                {/* Debug Info */}
                <div className="text-xs text-gray-400 mt-10">
                    InitData Length: {WebApp.initData.length}
                </div>
            </div>
        </div>
    )
}
