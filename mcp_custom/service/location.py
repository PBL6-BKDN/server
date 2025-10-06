import asyncio
import httpx
from config import TOMTOM_API_KEY


async def get_traffic_data_from_address(address: str):
    async with httpx.AsyncClient() as client:
        res = await client.get(
            f"https://api.tomtom.com/search/2/geocode/{address}.json", params={
                "key": TOMTOM_API_KEY
            }
        )
        data = res.json()
        address_name = data["results"][0]["address"]["freeformAddress"]
        radius = 1000  # bán kính 1km
        lat = data["results"][0]["position"]["lat"]
        lon = data["results"][0]["position"]["lon"]
        print(f"Vị trí: {address_name}, Tọa độ: ({lat}, {lon})")

        res = await client.get("https://api.tomtom.com/traffic/services/5/incidentDetails", params={
            "point": f"{lat},{lon}",
            "radius": radius,
            "key": TOMTOM_API_KEY,
            "language": "en-US",
            "bbox": f"{lat - 0.01},{lon - 0.01},{lat + 0.01},{lon + 0.01}",
        })

        data = res.json()

        res = await client.get("https://api.tomtom.com/traffic/services/4/flowSegmentData/relative0/10/json", params={
            "point": f"{lat},{lon}",
            "key": TOMTOM_API_KEY
        })

        data = res.json()
    flow_data = data['flowSegmentData']

    road_type = flow_data['frc']
    current_speed = flow_data["currentSpeed"]
    free_speed = flow_data["freeFlowSpeed"]
    current_time = flow_data["currentTravelTime"]
    free_time = flow_data["freeFlowTravelTime"]
    confidence = flow_data["confidence"]
    roadClosure = flow_data["roadClosure"]
    # Phân tích
    congestion_ratio = current_time / free_time
    if congestion_ratio < 1.2:
        status = "Bình thường"
    elif congestion_ratio < 1.5:
        status = "Hơi đông"
    elif congestion_ratio < 2.0:
        status = "Đang kẹt xe"
    else:
        status = "Kẹt nghiêm trọng"
    match road_type:
        case "FRC1":
            road_type = "Đường cao tốc"
        case "FRC2":
            road_type = "Đường quốc lộ lớn"
        case "FRC3":
            road_type = "Đường thành phố lớn"
        case "FRC4":
            road_type = "Đường cấp địa phương"
        case "FRC5":
            road_type = "Đường dân sinh"
        case "FRC6":
            road_type = "Ngõ nhỏ, hẻm"
        case "FRC7":
            road_type = "lối đi bộ, đường trong khuôn viên"
        case _:
            road_type = "Không xác định"
    res = {
        "Tên vị trí": address_name,
        "Tình trạng của đường": status,
        "Tốc độ xe hiện tại": current_speed,
        "Tốc độ xe khi đường vắng": free_speed,
        "Loại đường": road_type,
    }
    incidents = []

    # In thông tin sự cố
    for incident in data.get("incidents", []):
        incident_info = {
            "description": incident.get("description", "Không rõ"),
            "incidentCategory": incident.get("incidentCategory", "Không rõ"),
            "severity": incident.get("severity", "Không rõ"),
            "frc": incident.get("frc", "Không rõ"),
        }
        incidents.append(incident_info)
    res["Sự cố giao thông"] = incidents
    return res


async def _main():
    print(await get_traffic_data_from_address("Nguyễn Văn Linh, Đà Nẵng"))

if __name__ == "__main__":
    asyncio.run(_main())
