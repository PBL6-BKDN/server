import httpx


from config import WEATHER_API_KEY


async def get_weather_data(city: str):
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            "https://api.weatherapi.com/v1/current.json",
            params={
                "key": WEATHER_API_KEY,
                "q": "Da Nang",
                "lang": "vi",
            },
        )
        resp.raise_for_status()
        payload = resp.json()

        return {
            "location": {
                "name": payload["location"]["name"],
                "region": payload["location"]["region"],
                "country": payload["location"]["country"],
                "localtime": payload["location"]["localtime"],
            },
            "current": {
                "temp_c": payload["current"]["temp_c"],
                "condition": {
                    "text": payload["current"]["condition"]["text"],
                },
            },
        }
