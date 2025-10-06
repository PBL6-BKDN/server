from log import setup_logger
from mqtt.utils.contacts import Contact
from container import container

logger = setup_logger(__name__)

async def create_contact(name: str, phone_number: str):
    """
    Tạo liên hệ mới
    """
    logger.debug(f"Tạo liên hệ mới: {name} - {phone_number}")
    contact = Contact(name=name, phone_number=phone_number)
    contact.save()
    return {"status": "success", "message": "Liên hệ đã được tạo thành công"}

async def send_message(message: str, name: str):
    """
    Gửi tin nhắn SMS (Clean API - không cần truyền dependencies)
    
    Args:
        message: Nội dung tin nhắn
        name: Tên người nhận
        device_id: ID thiết bị (optional)
    
    Returns:
        dict: Kết quả gửi tin nhắn
    """
    logger.debug(f"Sending message: {message} to {name}")
    
    try:
        # Lấy dependencies từ container
        mqtt_client = container.get("mqtt_client")
        device_handler = container.get("device_handler")
        device_id = container.get("device_id")
        
        # Tra cứu số điện thoại
        phone_number = Contact.get_phone_by_name(name)
        
        if not phone_number:
            error_msg = f"Không tìm thấy số điện thoại cho liên hệ '{name}' trong danh bạ"
            logger.error(error_msg)
            return {"status": "error", "message": error_msg}
        
        # Gửi lệnh SMS
        device_handler.send_command(
            mqtt_client=mqtt_client,
            device_id=device_id,
            command="send_sms",
            params={
                "name": name,
                "message": message
            }
        )
        
        success_msg = f"Đã gửi tin nhắn đến {name} ({phone_number}): {message}"
        logger.info(success_msg)
        return {"status": "success", "message": success_msg, "phone_number": phone_number}
        
    except Exception as e:
        error_msg = f"Lỗi khi gửi tin nhắn: {str(e)}"
        logger.error(error_msg)
        return {"status": "error", "message": error_msg}