import asyncio
import datetime
from mcp.server.fastmcp import FastMCP
from typing import List

from mcp_custom.service.location import get_traffic_data_from_address
from mcp_custom.service.search import fetch_page_text_extracted, search_information_from_google
from mcp_custom.service.weather import get_weather_data
from type import Money
from log import setup_logger

mcp = FastMCP(name="PBL6_MCP_Server")
logger = setup_logger(__name__)


@mcp.tool()
def ping():
    """
    Ping the server
    """
    return "Pong"


@mcp.tool()
def describe_image(image) -> str:
    """
    Describe the image
    """
    return "This is a image of a cat"


@mcp.tool()
def detect_money() -> list[Money]:
    """ Detect money from the image """
    return [
        Money(currency="VND", type=10000, amount=1),
        Money(currency="VND", type=50000, amount=1),
    ]


@mcp.tool()
def count_money(moneys: List[Money]) -> int:
    """ Count the money """
    return sum(money.amount for money in moneys)


@mcp.tool()
async def get_temperature_and_weather(city: str) -> dict:
    """
    Get the temperature and weather of a city
    Args: 
        city(str): The city to get the temperature and weather
    Returns:
        dict: The temperature and weather of the city with format:
        {
            "location": {
                "name": tên địa điểm,
                "region": tên vùng/ tỉnh/ thành phố,
                "country": tên quốc gia,
                "localtime": thời gian hiện tại,
            },
            "current": {
                "temp_c": nhiệt độ hiện tại,
                "condition": {
                    "text": trạng thái thời tiết,
                },
            },
        }
    """
    return await get_weather_data(city)


@mcp.tool()
async def get_traffic_data(address: str) -> dict:
    """
    Get the traffic data of a address
    Args:
        address(str): The address to get the traffic data
    Returns:
        dict: The traffic data of the address with format:
        {
        "Tên vị trí": là tên vị trí/ địa chỉ được tìm kiếm,
            "Tình trạng của đường"
            "Tốc độ xe hiện tại"
            "Tốc độ xe khi đường vắng"
            "Loại đường"
        }
    """
    return await get_traffic_data_from_address(address)


@mcp.tool()
def get_current_date_time() -> str:
    """ Get the current date and time 
    Args: None
    Returns:
        str: The current date and time in the format of "YYYY-MM-DD HH:MM:SS"
    """
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


@mcp.tool()
async def search_information(query: str) -> dict:
    """Search information based on the user's question.
    Args:
        query: Câu hỏi hoặc từ khóa cần tìm.
    Returns:
        dict: {
        "engine": tên công cụ tìm kiếm,
                "query": câu hỏi hoặc từ khóa cần tìm,
                "results": List[dict] gồm {
            "title": tiêu đề của kết quả,
                        "link": liên kết của kết quả,
                        "snippet": mô tả của kết quả,
                        "date": ngày của kết quả,
                    },

        }

    """
    return await search_information_from_google(query)


@mcp.tool()
async def fetch_page_text(url: str) -> str:
    """Get detail information from a page with url
    Args:
        url: The URL of the page to fetch.
    Returns:
        str: The detail information of the page.
    """
    return await fetch_page_text_extracted(url)


if __name__ == "__main__":
    mcp.run(transport='sse')
