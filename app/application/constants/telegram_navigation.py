BACK_TO_MENU_CALLBACK_DATA = "nav:menu"
BACK_TO_MENU_TEXT = "« Back to Menu"


def back_to_menu_row() -> list[dict]:
    return [{"text": BACK_TO_MENU_TEXT, "callback_data": BACK_TO_MENU_CALLBACK_DATA}]


def back_to_menu_markup() -> dict:
    return {"inline_keyboard": [back_to_menu_row()]}
