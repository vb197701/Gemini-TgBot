from config import conf
from google.genai.chats import AsyncChat
from google import genai
from asyncio import Lock
from typing import Tuple

chat_dict: dict[int, list[AsyncChat, Lock]] = {}
client: genai.Client | None = None

def init_client(api_key: str) -> None:
    """Initialize the Gemini client once during application startup."""
    global client
    client = genai.Client(api_key=api_key)

def get_client() -> genai.Client:
    if client is None:
        raise RuntimeError("Gemini client is not initialized")
    return client

async def init_user(user_id: int) -> Tuple[AsyncChat, Lock]:
    """if user not exist in chat_dict, create one
    
    Args:
        user_id: (int): user's id

    Returns:
        AsyncChat: user's chat session
        Lock:      user's chat lock
    """
    if user_id not in chat_dict:#if not find user's chat
        chat = get_client().aio.chats.create(model=conf["model_1"])
        lock = Lock()
        chat_dict[user_id] = [chat, lock]
    else:
        chat, lock = chat_dict[user_id]
    return chat, lock

async def switch_model(user_id: int) -> str:
    """Update user's chat session, keep the history
    
    Args:
        user_id (int): user's id

    Returns:
        str: chat's current model
    """
    old_chat, lock = await init_user(user_id)

    async with lock:
        if(old_chat._model == conf["model_1"]):
            new_model = conf["model_2"]
        else:
            new_model = conf["model_1"]
        history = old_chat.get_history()
        new_chat = get_client().aio.chats.create(model=new_model, history = history)
        chat_dict[user_id] = [new_chat, lock]

        return new_model

async def clear_history(user_id: int) -> None:
    """clear user's history
    
    Args:
        user_id (int): user's id

    Returns:
        None
    """
    old_chat, lock = await init_user(user_id)

    async with lock:
        model = old_chat._model
        new_chat = get_client().aio.chats.create(model=model)
        chat_dict[user_id] = [new_chat, lock]
