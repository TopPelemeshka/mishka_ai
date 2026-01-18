from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import httpx
from src.log_handler import setup_logger, start_log_handler, stop_log_handler

app = FastAPI(title="Mishka Weather Tool")

setup_logger()

@app.on_event("startup")
async def startup():
    await start_log_handler()

@app.on_event("shutdown")
async def shutdown():
    await stop_log_handler()

class WeatherRequest(BaseModel):
    city: str

@app.post("/weather")
async def get_weather(request: WeatherRequest):
    """
    Get current weather for a city using Open-Meteo.
    Note: Open-Meteo requires coordinates, so we first geocode the city name.
    """
    city = request.city
    
    try:
        # 1. Geocoding (City name -> Coordinates)
        geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={city}&count=1&language=ru&format=json"
        
        async with httpx.AsyncClient() as client:
            geo_resp = await client.get(geo_url)
            geo_resp.raise_for_status()
            geo_data = geo_resp.json()
            
            if not geo_data.get("results"):
                raise HTTPException(status_code=404, detail=f"Город '{city}' не найден")
            
            location = geo_data["results"][0]
            lat = location["latitude"]
            lon = location["longitude"]
            name = location["name"]

            # 2. Get Weather
            weather_url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true"
            weather_resp = await client.get(weather_url)
            weather_resp.raise_for_status()
            weather_data = weather_resp.json()
            
            current = weather_data["current_weather"]
            temp = current["temperature"]
            
            return {
                "city": name,
                "temperature": f"{temp}°C",
                "condition": "Данные с Open-Meteo"
            }
            
    except Exception as e:
        # Fallback to a mock on error
        return {
            "city": city,
            "temperature": "+15°C",
            "condition": "Sunny (MOCK)",
            "error": str(e)
        }

@app.get("/health")
async def health():
    return {"status": "ok"}
