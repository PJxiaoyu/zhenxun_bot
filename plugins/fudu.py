from nonebot.adapters.cqhttp.permission import GROUP
from configs.path_config import IMAGE_PATH
from utils.image_utils import get_img_hash
import random
from utils.message_builder import image
from nonebot import on_message
from utils.utils import get_message_text, get_message_imgs, get_local_proxy
from nonebot.typing import T_State
from nonebot.adapters.cqhttp import Bot, GroupMessageEvent
import aiohttp
import aiofiles
from asyncio.exceptions import TimeoutError
from configs.config import FUDU_PROBABILITY


class Fudu:
    def __init__(self):
        self.data = {}

    def append(self, key, content):
        self._create(key)
        self.data[key]["data"].append(content)

    def clear(self, key):
        self._create(key)
        self.data[key]["data"] = []
        self.data[key]["is_repeater"] = False

    def size(self, key) -> int:
        self._create(key)
        return len(self.data[key]["data"])

    def check(self, key, content) -> bool:
        self._create(key)
        return self.data[key]["data"][0] == content

    def get(self, key):
        self._create(key)
        return self.data[key]["data"][0]

    def is_repeater(self, key):
        self._create(key)
        return self.data[key]["is_repeater"]

    def set_repeater(self, key):
        self._create(key)
        self.data[key]["is_repeater"] = True

    def _create(self, key):
        if self.data.get(key) is None:
            self.data[key] = {"is_repeater": False, "data": []}


_fudu_list = Fudu()


fudu = on_message(permission=GROUP, priority=9)


@fudu.handle()
async def _(bot: Bot, event: GroupMessageEvent, state: T_State):
    if event.is_tome() or state["_prefix"]["raw_command"]:
        return
    if get_message_text(event.json()):
        if get_message_text(event.json()).find("@可爱的小真寻") != -1:
            await fudu.finish("复制粘贴的虚空艾特？", at_sender=True)
    imgs = get_message_imgs(event.json())
    msg = get_message_text(event.json())
    if not imgs and not msg:
        return
    if imgs:
        img_hash = await get_fudu_img_hash(imgs[0], event.group_id)
    else:
        img_hash = ""
    add_msg = msg + "|-|" + img_hash
    if _fudu_list.size(event.group_id) == 0:
        _fudu_list.append(event.group_id, add_msg)
    elif _fudu_list.check(event.group_id, add_msg):
        _fudu_list.append(event.group_id, add_msg)
    else:
        _fudu_list.clear(event.group_id)
        _fudu_list.append(event.group_id, add_msg)
    if _fudu_list.size(event.group_id) > 2:
        if random.random() < FUDU_PROBABILITY and not _fudu_list.is_repeater(
            event.group_id
        ):
            if random.random() < 0.2:
                await fudu.finish("打断施法！")
            _fudu_list.set_repeater(event.group_id)
            if imgs and msg:
                rst = msg + image(f"compare_{event.group_id}_img.jpg", "temp")
            elif imgs:
                rst = image(f"compare_{event.group_id}_img.jpg", "temp")
            elif msg:
                rst = msg
            else:
                rst = ""
            if rst:
                await fudu.send(rst)


async def get_fudu_img_hash(url, group_id):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, proxy=get_local_proxy(), timeout=5) as response:
                async with aiofiles.open(
                    IMAGE_PATH + f"temp/compare_{group_id}_img.jpg", "wb"
                ) as f:
                    await f.write(await response.read())
        img_hash = get_img_hash(IMAGE_PATH + f"temp/compare_{group_id}_img.jpg")
        return str(img_hash)
    except TimeoutError:
        return ""
