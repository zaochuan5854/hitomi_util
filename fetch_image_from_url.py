import random
import requests
import ua_generator # type: ignore
from urllib3.util import Retry
from requests.adapters import HTTPAdapter
from enum import Enum

class Device(Enum):
    DESKTOP = "desktop"
    MOBILE = "mobile"

class Platform(Enum):
    WINDOWS = "windows"
    ANDROID = "android"
    IOS = "ios"

class Browser(Enum):
    CHROME = 'chrome'
    EDGE = 'edge'
    FIREFOX = 'firefox'
    SAFARI = 'safari'

#作品idと画像urlから作品を取得
def fetch_image_from_url(gallery_id: int, url: str, retry_num: int=5) -> bytes:
    
    #例のヘッダ
    headers = {
        'accept': 'image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8',
        'accept-encoding': 'gzip, deflate, br, zstd',
        'accept-language': 'ja',
        'cache-control': 'no-cache',
        'dnt': '1',
        'pragma': 'no-cache',
        'priority': 'i',
        'referer': f'https://hitomi.la/reader/{gallery_id}.html',
        'sec-ch-ua': '"Chromium";v="136", "Google Chrome";v="136", "Not.A/Brand";v="99"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"',
        'sec-fetch-dest': 'image',
        'sec-fetch-mode': 'no-cors',
        'sec-fetch-site': 'cross-site',
        'sec-fetch-storage-access': 'none',
        'sec-gpc': '1',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36'
    }
    
    #ヘッダの偽装
    platform = random.choice([Platform.WINDOWS, Platform.ANDROID, Platform.IOS])
    match platform:
        case Platform.WINDOWS:
            device = Device.DESKTOP
            browser = random.choice([Browser.CHROME, Browser.EDGE,Browser.FIREFOX])
        case Platform.ANDROID:
            device = Device.MOBILE
            browser = random.choice([Browser.CHROME, Browser.FIREFOX])
        case Platform.IOS:
            device = Device.MOBILE
            browser = Browser.SAFARI
    ua = ua_generator.generate(device=device.value, platform=platform.value, browser=browser.value) # type: ignore

    ua_dict = ua.headers.get() # type: ignore
    #例のヘッダを上書きして偽装
    headers_to_update = ['user-agent', 'sec-ch-ua', 'sec-ch-ua-mobile', 'sec-ch-ua-platform']
    for header_key in headers_to_update:
        if header_key in ua_dict:
            headers[header_key] = ua_dict[header_key]
    #print(headers)

    try:
        session = requests.Session()
        retry = Retry(total=retry_num, backoff_factor=1, status_forcelist=[502, 503, 504])
        adapter = HTTPAdapter(max_retries=retry)
        session.mount('https://', adapter)
        response = session.get(url, headers=headers, timeout=(10, 30))
        response.raise_for_status()
        return response.content
    
    except requests.HTTPError as e:
        print('Failed to fetch image data')
        raise e

def test():
    pass


if __name__ == '__main__':
    test()