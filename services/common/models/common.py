from typing_extensions import Annotated

from sqlalchemy.orm import mapped_column


CASCADE_ALL_DELETE = 'save-update, merge, expunge, delete'
CASCADE_ALL_DELETE_ORPHAN = 'save-update, merge, expunge, delete, delete-orphan'


intpk = Annotated[int, mapped_column(primary_key=True)]
