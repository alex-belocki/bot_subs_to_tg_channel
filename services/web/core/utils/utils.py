from sqlalchemy import and_

from core.database.database import db
from common.models.interface_models import Button, Menu



def get_menus_without_variable_buttons():
    """Отбираем меню без переменных"""
    subquery = (
        db.session.query(Menu.id)
        .join(Menu.buttons_list)
        .filter(
            and_(
                Button.callback_data.contains('{'),
                Button.callback_data.contains('}')
            )
        )
        .subquery()
    )

    # Main query to find menus without buttons containing variables
    query = (
        db.session.query(Menu)
        .filter(~Menu.id.in_(subquery))
    )

    return query.all()
