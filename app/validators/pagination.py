"""Contract bounds shared by list and explain routes."""
from typing import Annotated
from fastapi import Query

Page = Annotated[int, Query(ge=1)]
PageSize = Annotated[int, Query(ge=1, le=100)]
Limit = Annotated[int, Query(ge=1, le=50)]
