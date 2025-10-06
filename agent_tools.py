"""
Công cụ cho các agent trong hệ thống đa agent
"""
from mcp_custom.service.location import get_traffic_data_from_address
from mcp_custom.service.search import search_information_from_google, fetch_page_text_extracted
from mcp_custom.service.task import send_message, create_contact
from mcp_custom.service.weather import get_weather_data
from typing import List

from log import setup_logger
from mcp_custom.mcp_client import FunctionDefinition

logger = setup_logger(__name__)

def get_search_tools() -> List[FunctionDefinition]:
    """
    Lấy danh sách công cụ tìm kiếm
    
    Returns:
        List[FunctionDefinition]: Danh sách công cụ
    """
    search_web_func = FunctionDefinition(
        name="search_web",
        description="Tìm kiếm thông tin trên web",
        parameters={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Từ khóa tìm kiếm"
                }
            },
            "required": ["query"]
        },
        required=["query"],
        callable=search_information_from_google
    )
    
    search_weather_func = FunctionDefinition(
        name="search_weather",
        description="Tìm kiếm thông tin thời tiết",
        parameters={
            "type": "object",
            "properties": {
                "location": {
                    "type": "string",
                    "description": "Địa điểm cần tìm thời tiết"
                }
            },
            "required": ["location"]
        },
        required=["location"],
        callable=get_weather_data
    )
    
    search_detail_info_by_url = FunctionDefinition(
        name="search_detail_info_by_url",
        description="Tìm kiếm thông tin chi tiết từ url website",
        parameters={
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "URL website"
                },
                "max_chars": {
                    "type": "integer",
                    "description": "Số lượng ký tự tối đa"
                }
            },
            "required": ["url", "max_chars"]
        },
        required=["url", "max_chars"],
        callable=fetch_page_text_extracted
    )
    
    search_information_about_traffic = FunctionDefinition(
        name="search_information_about_traffic",
        description="Tìm kiếm thông tin về giao thông tại 1 địa điểm cụ thể",
        parameters={
            "type": "object",
            "properties": {
                "address": {
                    "type": "string",
                    "description": "Địa điểm cần tìm thông tin giao thông yêu cầu sắp xếp theo số nhà + tên đường hoặc tên địa điểm / thành phố / quốc gia, nếu không cung cấp thì mặc định là Đà Nẵng"
                }
            },
            "required": ["address"]
        },
        required=["address"],
        callable=get_traffic_data_from_address
    )

    return [search_web_func, search_weather_func, search_detail_info_by_url, search_information_about_traffic]

def get_task_tools() -> List[FunctionDefinition]:
    """
    Lấy danh sách công cụ thực hiện tác vụ
    
    Returns:
        List[FunctionDefinition]: Danh sách công cụ
    """

    send_message_func = FunctionDefinition(
        name="send_message",
        description="Gửi tin nhắn",
        parameters={
            "type": "object",
            "properties": {
                "message": {
                    "type": "string",
                    "description": "Tin nhắn"
                },
                "name": {
                    "type": "string",
                    "description": "Tên người nhận"
                }
            },
            "required": ["message", "name"]
        },
        required=["message", "name"],
        callable=send_message
    )

    create_contact_func = FunctionDefinition(
        name="create_contact",
        description="Tạo liên hệ mới",
        parameters={
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Tên người nhận"
                },
                "phone_number": {
                    "type": "string",
                    "description": "Số điện thoại"
                }
            },
            "required": ["name", "phone_number"]
        },
        required=["name", "phone_number"],
        callable=create_contact
    )

    
    return [send_message_func, create_contact_func]
