from configs.path_config import IMAGE_PATH
from utils.message_builder import image
from services.log import logger
from aiohttp.client_exceptions import ClientConnectorError
from utils.image_utils import get_img_hash, compressed_image
from asyncpg.exceptions import UniqueViolationError
from utils.utils import get_local_proxy
from asyncio.exceptions import TimeoutError
from typing import List, Optional
from configs.config import INITIAL_SETU_PROBABILITY, NICKNAME
from models.setu import Setu
import aiohttp
import aiofiles
import asyncio
import os
import random

try:
    import ujson as json
except ModuleNotFoundError:
    import json


url = "https://api.lolicon.app/setu/v2"
path = "_setu/"
r18_path = "_r18/"


# 获取url
async def get_setu_urls(
    tags: List[str], num: int = 1, r18: int = 0, command: str = ""
) -> "List[str], List[str], List[tuple], int":
    tags = tags[:3] if len(tags) > 3 else tags
    params = {
        "r18": r18,  # 添加r18参数 0为否，1为是，2为混合
        "tag": tags,  # 若指定tag
        "num": 100,  # 一次返回的结果数量
        "size": ["original"],
    }
    async with aiohttp.ClientSession() as session:
        for count in range(3):
            logger.info(f"get_setu_url: count --> {count}")
            try:
                async with session.get(
                    url, proxy=get_local_proxy(), timeout=2, params=params
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        if not data["error"]:
                            data = data["data"]
                            (
                                urls,
                                text_list,
                                add_databases_list,
                            ) = await asyncio.get_event_loop().run_in_executor(
                                None, _setu_data_process, data, command
                            )
                            num = num if num < len(data) else len(data)
                            random_idx = random.sample(range(len(data)), num)
                            x_urls = []
                            x_text_lst = []
                            for x in random_idx:
                                x_urls.append(urls[x])
                                x_text_lst.append(text_list[x])
                            if not x_urls:
                                return ["没找到符合条件的色图..."], [], [], 401
                            return x_urls, x_text_lst, add_databases_list, 200
                        else:
                            return ["没找到符合条件的色图..."], [], [], 401
            except (TimeoutError, ClientConnectorError):
                pass
    return ["我网线被人拔了..QAQ"], [], [], 999


headers = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.6;"
    " rv:2.0.1) Gecko/20100101 Firefox/4.0.1",
    "Referer": "https://www.pixiv.net",
}


async def search_online_setu(
    url_: str, id_: int = None, path_: str = None
) -> "MessageSegment, int":
    if "i.pixiv.cat" in url_:
        url_ = url_.replace("i.pixiv.cat", "i.pximg.net")
    async with aiohttp.ClientSession(headers=headers) as session:
        for i in range(3):
            logger.info(f"search_online_setu --> {i}")
            try:
                async with session.get(url_, proxy=get_local_proxy(), timeout=3) as res:
                    if res.status == 200:
                        index = random.randint(1, 100000) if id_ is None else id_
                        path_ = "temp" if not path_ else path_
                        file = f"{index}_temp_setu.jpg" if not path_ else f"{index}.jpg"
                        if not os.path.exists(f'{IMAGE_PATH}/{path_}'):
                            os.mkdir(f'{IMAGE_PATH}/{path_}')
                        async with aiofiles.open(
                            f"{IMAGE_PATH}/{path_}/{file}", "wb"
                        ) as f:
                            try:
                                await f.write(await res.read())
                            except TimeoutError:
                                continue
                        if id_ is not None:
                            if (
                                os.path.getsize(f"{IMAGE_PATH}/{path_}/{index}.jpg")
                                > 1024 * 1024 * 1.5
                            ):
                                compressed_image(
                                    f"{IMAGE_PATH}/{path_}/{index}.jpg",
                                )
                        logger.info(f"下载 lolicon图片 {url_} 成功， id：{index}")
                        return image(file, path_), index
                    else:
                        logger.warning(f"访问 lolicon图片 {url_} 失败 status：{res.status}")
                        # return '\n这图好难下载啊！QAQ', -1, False
            except (TimeoutError, ClientConnectorError):
                pass
        return "图片被小怪兽恰掉啦..!QAQ", -1


# 检测本地是否有id涩图，无的话则下载
async def check_local_exists_or_download(setu_image: Setu) -> "MessageSegment, int":
    if setu_image.is_r18:
        path_ = "_r18"
    else:
        path_ = path
    if os.path.exists(f"{IMAGE_PATH}/{path_}/{setu_image.local_id}.jpg"):
        return image(f"{setu_image.local_id}.jpg", path_), 200
    return await search_online_setu(setu_image.img_url, setu_image.local_id, path_)


# 添加涩图数据到数据库
async def add_data_to_database(lst: List[tuple]):
    tmp = []
    for x in lst:
        if x not in tmp:
            tmp.append(x)
    if tmp:
        for x in tmp:
            try:
                r18 = 1 if "R-18" in x[5] else 0
                idx = await Setu.get_image_count(r18)
                await Setu.add_setu_data(
                    idx,
                    x[0],
                    x[1],
                    x[2],
                    x[3],
                    x[4],
                    x[5],
                )
            except UniqueViolationError:
                pass


# 拿到本地色图列表
async def get_setu_list(
    index: Optional[int] = None, tags: Optional[List[str]] = None, r18: int = 0
) -> "list, int":
    if index:
        image_count = await Setu.get_image_count(r18) - 1
        if index < 0 or index > image_count:
            return [f"超过当前上下限！({image_count})"], 999
        image_list = [await Setu.query_image(index, r18=r18)]
    elif tags:
        image_list = await Setu.query_image(tags=tags, r18=r18)
    else:
        image_list = await Setu.query_image(r18=r18)
    if not image_list:
        return ["没找到符合条件的色图..."], 998
    return image_list, 200


# 初始化消息
def gen_message(setu_image: Setu, img_msg: bool = False):
    local_id = setu_image.local_id
    title = setu_image.title
    author = setu_image.author
    pid = setu_image.pid
    return (
        f"id：{local_id}\n"
        f"title：{title}\n"
        f"author：{author}\n"
        f"PID：{pid}\n"
        f"{image(f'{local_id}', f'{r18_path if setu_image.is_r18 else path}') if img_msg else ''}"
    )


# 罗翔老师！
def get_luoxiang(impression):
    probability = impression + INITIAL_SETU_PROBABILITY * 100
    if probability < random.randint(1, 101):
        return (
            "我为什么要给你发这个？"
            + image(random.choice(os.listdir(IMAGE_PATH + "luoxiang/")), "luoxiang")
            + f"\n(快向{NICKNAME}签到提升好感度吧！)"
        )
    return None


async def find_img_index(img_url, user_id):
    async with aiohttp.ClientSession() as session:
        async with session.get(img_url, proxy=get_local_proxy(), timeout=5) as res:
            async with aiofiles.open(
                IMAGE_PATH + f"temp/{user_id}_find_setu_index.jpg", "wb"
            ) as f:
                await f.write(await res.read())
    img_hash = str(get_img_hash(IMAGE_PATH + f"temp/{user_id}_find_setu_index.jpg"))
    setu_img = await Setu.get_image_in_hash(img_hash)
    if setu_img:
        return (
            f"id：{setu_img.local_id}\n"
            f"title：{setu_img.title}\n"
            f"author：{setu_img.author}\n"
            f"PID：{setu_img.pid}"
        )
    return "该图不在色图库中或色图库未更新！"


# 处理色图数据
def _setu_data_process(data: dict, command: str) -> "list, list, list":
    urls = []
    text_list = []
    add_databases_list = []
    for i in range(len(data)):
        img_url = data[i]["urls"]["original"]
        img_url = (
            img_url.replace("i.pixiv.cat", "i.pximg.net")
            if "i.pixiv.cat" in img_url
            else img_url
        )
        title = data[i]["title"]
        author = data[i]["author"]
        pid = data[i]["pid"]
        urls.append(img_url)
        text_list.append(f"title：{title}\nauthor：{author}\nPID：{pid}")
        tags = []
        for j in range(len(data[i]["tags"])):
            tags.append(data[i]["tags"][j])
        if command != "色图r":
            if "R-18" in tags:
                tags.remove("R-18")
        add_databases_list.append(
            (
                title,
                author,
                pid,
                "",
                img_url,
                ",".join(tags),
            )
        )
    return urls, text_list, add_databases_list
