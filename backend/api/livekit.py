import os
from datetime import timedelta
from fastapi import HTTPException

def credentials(call_id):
    from livekit import api
    names = ("LIVEKIT_URL","LIVEKIT_API_KEY","LIVEKIT_API_SECRET","GROQ_API_KEY")
    if missing := [name for name in names if not os.getenv(name)]:
        raise HTTPException(503,"Missing live settings: " + ", ".join(missing))
    room = "flowcrm-" + call_id
    token = (api.AccessToken(os.environ["LIVEKIT_API_KEY"],os.environ["LIVEKIT_API_SECRET"])
        .with_identity("customer-" + call_id)
        .with_ttl(timedelta(minutes=10))
        .with_grants(api.VideoGrants(room_join=True,room=room,can_publish=True,
                                    can_subscribe=True,can_publish_data=False))
        .with_room_config(api.RoomConfiguration(agents=[api.RoomAgentDispatch(agent_name="flowcrm")])))
    return {"url":os.environ["LIVEKIT_URL"],"token":token.to_jwt()}
