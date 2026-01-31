from typing import List

from sqlalchemy import select

from core.database.base_repo import BaseRepository
from common.models.interface_models import Button


class ButtonRepository(BaseRepository):
    model = Button

    def get_buttons(self, slug_list: list[str]) -> List[Button]:
        query = (
            select(self.model)
            .filter(self.model.slug.in_(slug_list))
        )
        result = self.session.execute(query)
        buttons = result.scalars().all()

        # Сортируем кнопки в соответствии с порядком в slug_list
        slug_to_button = {button.slug: button for button in buttons}
        sorted_buttons = [slug_to_button[slug] for slug in slug_list if slug in slug_to_button]

        return sorted_buttons
