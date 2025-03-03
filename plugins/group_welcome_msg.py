from nonebot import on_command
from nonebot.typing import T_State
from nonebot.adapters.cqhttp import Bot, GroupMessageEvent
from nonebot.adapters.cqhttp.permission import GROUP
from configs.path_config import DATA_PATH
from utils.message_builder import image
import os
from pathlib import Path

try:
    import ujson as json
except ModuleNotFoundError:
    import json

__plugin_name__ = "查看群欢迎消息"

__plugin_usage__ = "无"

view_custom_welcome = on_command(
    "群欢迎消息", aliases={"查看群欢迎消息", "查看当前群欢迎消息"}, permission=GROUP, priority=5, block=True
)


@view_custom_welcome.handle()
async def _(bot: Bot, event: GroupMessageEvent, state: T_State):
    img = ""
    msg = ""
    if os.path.exists(DATA_PATH + f"custom_welcome_msg/{event.group_id}.jpg"):
        img = image(abspath=DATA_PATH + f"custom_welcome_msg/{event.group_id}.jpg")
    custom_welcome_msg_json = (
        Path() / "data" / "custom_welcome_msg" / "custom_welcome_msg.json"
    )
    if custom_welcome_msg_json.exists():
        data = json.load(open(custom_welcome_msg_json, "r"))
        if data.get(str(event.group_id)):
            msg = data[str(event.group_id)]
            if msg.find("[at]") != -1:
                msg = msg.replace("[at]", "")
    if img or msg:
        await view_custom_welcome.finish(msg + img, at_sender=True)
    else:
        await view_custom_welcome.finish("当前还没有自定义群欢迎消息哦", at_sender=True)
