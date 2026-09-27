from fastapi import APIRouter, Request

from inferscale.common.config import Settings
from inferscale.common.schemas import ModelCard, ModelList

router = APIRouter()


@router.get("/v1/models")
async def list_models(request: Request) -> ModelList:
    settings: Settings = request.app.state.settings
    return ModelList(data=[ModelCard(id=m.id, owned_by=m.owned_by) for m in settings.models])
