from fastapi import APIRouter, Request

from app.schemas.echo import EchoRequest
from app.services.echo import echo_message

router = APIRouter(tags=["echo"])


@router.post("/echo")
async def echo(request_data: EchoRequest, request: Request):
    result = echo_message(request_data.message)
    request_id = getattr(request.state, "request_id", "")
    return {"data": result, "request_id": request_id}