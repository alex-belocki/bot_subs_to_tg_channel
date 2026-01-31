from pydantic import BaseModel
from typing import List


class SendCampaignEvent(BaseModel):
    campaign_id: int
    user_ids: List[int]
    text: str
    # можно добавить другие поля (например, files, menu и т.д.)
