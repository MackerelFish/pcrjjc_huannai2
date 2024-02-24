from msgpack import packb, unpackb
from random import randint
from hashlib import md5, sha1
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad, pad
from base64 import b64encode, b64decode
from random import choice
from bs4 import BeautifulSoup
import requests
import os
import json
from hoshino.aiorequests import post
import re

# 读取代理配置
with open(os.path.join(os.path.dirname(__file__), "proxy.json")) as fp:
    pinfo = json.load(fp)


# 获取headers
def get_headers():
    app_ver = get_ver()
    default_headers = {
        "Accept-Encoding": "gzip",
        "User-Agent": "Dalvik/2.1.0 (Linux, U, Android 5.1.1, PCRT00 Build/LMY48Z)",
        "Content-Type": "application/octet-stream",
        "Expect": "100-continue",
        "X-Unity-Version": "2018.4.21f1",
        "APP-VER": app_ver,
        "BATTLE-LOGIC-VERSION": "4",
        "BUNDLE-VER": "",
        "DEVICE": "2",
        "DEVICE-ID": "7b1703a5d9b394e24051d7a5d4818f17",
        "DEVICE-NAME": "OPPO PCRT00",
        "GRAPHICS-DEVICE-NAME": "Adreno (TM) 640",
        "IP-ADDRESS": "10.0.2.15",
        "KEYCHAIN": "",
        "LOCALE": "Jpn",
        "PLATFORM-OS-VERSION": "Android OS 5.1.1 / API-22 (LMY48Z/rel.se.infra.20200612.100533)",
        "REGION-CODE": "",
        "RES-VER": "00017004",
    }
    return default_headers


def get_ver():
    headers = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,"
        "application/signed-exchange;v=b3;q=0.7",
        "Accept-Encoding": "gzip, deflate, br",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
        "Cache-Control": "max-age=0",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/115.0.0.0 Safari/537.36 Edg/115.0.1901.183",
        "Upgrade-Insecure-Requests": "1",
        "Pragma": "no-cache",
    }
    app_url = "https://play.google.com/store/apps/details?id=tw.sonet.princessconnect"
    # print(f'url = {app_url}')
    app_res = requests.get(app_url, headers=headers, timeout=15, proxies=pinfo["proxy"])
    soup = BeautifulSoup(app_res.text, "lxml")
    ver_tmp_list = soup.findAll(
        "script", text=re.compile(r".+超異域公主連結！Re:Dive.+")
    )
    ver_str = str(ver_tmp_list[-1])
    ver_group = re.search(r'"数据无法删除".+\[\[\["(.+?)"]]', ver_str)
    return ver_group.group(1)


class ApiException(Exception):
    def __init__(self, message, code):
        super().__init__(message)
        self.code = code


class pcrclient:
    @staticmethod
    def _makemd5(str) -> str:
        return md5((str + "r!I@nt8e5i=").encode("utf8")).hexdigest()

    def __init__(self, udid, short_udid, viewer_id, platform):
        platform = str(platform)
        self.viewer_id = viewer_id
        self.short_udid = short_udid
        self.udid = udid
        self.proxy = pinfo["proxy"]
        self.token = pcrclient.createkey()
        self.headers = get_headers().copy()

        self.headers["SID"] = pcrclient._makemd5(viewer_id + udid)
        if platform == "1":
            self.apiroot = f"https://api-pc.so-net.tw"
        else:
            self.apiroot = f"https://api5-pc.so-net.tw"
        self.headers["platform"] = "2"
        self.platform = platform
        self.shouldLogin = False

    @staticmethod
    def createkey() -> bytes:
        return bytes([ord("0123456789abcdef"[randint(0, 15)]) for _ in range(32)])

    def _getiv(self) -> bytes:
        return self.udid.replace("-", "")[:16].encode("utf8")

    def pack(self, data: object, key: bytes) -> tuple:
        aes = AES.new(key, AES.MODE_CBC, self._getiv())
        packed = packb(data, use_bin_type=False)
        return packed, aes.encrypt(pad(packed, 16)) + key

    def encrypt(self, data: str, key: bytes) -> bytes:
        aes = AES.new(key, AES.MODE_CBC, self._getiv())
        return aes.encrypt(pad(data.encode("utf8"), 16)) + key

    def decrypt(self, data: bytes):
        data = b64decode(data.decode("utf8"))
        aes = AES.new(data[-32:], AES.MODE_CBC, self._getiv())
        return aes.decrypt(data[:-32]), data[-32:]

    def unpack(self, data: bytes):
        data = b64decode(data.decode("utf8"))
        aes = AES.new(data[-32:], AES.MODE_CBC, self._getiv())
        dec = unpad(aes.decrypt(data[:-32]), 16)
        return unpackb(dec, strict_map_key=False), data[-32:]

    alphabet = "0123456789"

    @staticmethod
    def _encode(dat: str) -> str:
        return (
            f"{len(dat):0>4x}"
            + "".join(
                [
                    (
                        chr(ord(dat[int(i / 4)]) + 10)
                        if i % 4 == 2
                        else choice(pcrclient.alphabet)
                    )
                    for i in range(0, len(dat) * 4)
                ]
            )
            + pcrclient._ivstring()
        )

    @staticmethod
    def _ivstring() -> str:
        return "".join([choice(pcrclient.alphabet) for _ in range(32)])

    async def callapi(self, apiurl: str, request: dict, noerr: bool = False):
        key = pcrclient.createkey()
        try:
            if self.viewer_id is not None:
                request["viewer_id"] = b64encode(self.encrypt(str(self.viewer_id), key))
                request["tw_server_id"] = str(self.platform)
            packed, crypted = self.pack(request, key)
            self.headers["PARAM"] = sha1(
                (
                    self.udid
                    + apiurl
                    + b64encode(packed).decode("utf8")
                    + str(self.viewer_id)
                ).encode("utf8")
            ).hexdigest()
            self.headers["SHORT-UDID"] = pcrclient._encode(self.short_udid)
            resp = await post(
                self.apiroot + apiurl,
                data=crypted,
                headers=self.headers,
                timeout=5,
                proxies=self.proxy,
                verify=False,
            )
            response = await resp.content

            response = self.unpack(response)[0]
            data_headers = response["data_headers"]
            if "viewer_id" in data_headers:
                self.viewer_id = data_headers["viewer_id"]
            if "required_res_ver" in data_headers:
                self.headers["RES-VER"] = data_headers["required_res_ver"]

            data = response["data"]
            if not noerr and "server_error" in data:
                data = data["server_error"]
                code = data_headers["result_code"]
                print(f"pcrclient: {apiurl} api failed code = {code}, {data}")
                raise ApiException(data["message"], data["status"])
            # print(f'pcrclient: {apiurl} api called')
            # 生成角色信息json文件，用于调试
            # json_data = json.dumps(data, indent=4, ensure_ascii=False)
            # data_path =  Path(__file__).parent / 'res_data.json'
            # data_path.write_text(json_data, encoding="utf-8")
            return data
        except:
            self.shouldLogin = True
            raise

    async def login(self):

        await self.callapi("/check/check_agreement", {})
        await self.callapi("/check/game_start", {})
        await self.callapi("/load/index", {"carrier": "Android"})
        self.shouldLogin = False
