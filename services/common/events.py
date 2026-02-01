from pydantic import BaseModel
from typing import List
import datetime as dt


class SendCampaignEvent(BaseModel):
    campaign_id: int
    user_ids: List[int]
    text: str
    # можно добавить другие поля (например, files, menu и т.д.)


class PaymentSucceededEvent(BaseModel):
    payment_id: int
    user_id: int
    provider: str
    amount: str
    currency: str
    paid_at: dt.datetime
