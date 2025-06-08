# mishka_ai/utils.py
import logging

logger = logging.getLogger(__name__)

def get_user_details_string(users_data_dict: dict) -> str:
    """
    Формирует строку с описанием известных пользователей для системного промпта.
    Args:
        users_data_dict: Словарь с данными пользователей.
    """
    if not users_data_dict:
        return "Пока я никого не знаю в этой группе."
        
    details = []
    for user_id, info in users_data_dict.items():
        name = info.get('name', 'Неизвестный')
        # Получаем список прозвищ, или пустой список, если ключ отсутствует или None
        nicknames_list = info.get('nicknames', []) 
        if isinstance(nicknames_list, str): # Обратная совместимость, если где-то остался старый формат
            nicknames_list = [nicknames_list] if nicknames_list else []
        
        known = info.get('known_info', 'нет особой информации')
        detail_str = f"{name}"
        
        # Формируем строку с прозвищами
        if nicknames_list:
            # Убираем дубликаты с основным именем, если они есть (без учета регистра)
            nicknames_to_show = [n for n in nicknames_list if n.lower() != name.lower()]
            if nicknames_to_show:
                if len(nicknames_to_show) == 1:
                    detail_str += f" (можно звать {nicknames_to_show[0]})"
                else:
                    # " (можно звать Серый, Серёга или Рыбак)"
                    nicknames_joined = ", ".join(nicknames_to_show[:-1]) + (f" или {nicknames_to_show[-1]}" if len(nicknames_to_show) > 1 else "")
                    detail_str += f" (можно звать {nicknames_joined})"
        
        detail_str += f" (ID: {user_id}): {known}."
        details.append(detail_str)
    return "\n".join(details) if details else "Пока я никого не знаю в этой группе."