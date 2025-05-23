import re
import time
import requests
from typing import Callable
from dateutil.parser import parse
from dateutil.tz import tzutc
from gallery_info_from_id import FileInfo

class GGJsIsExpire(Exception):
    def __str__(self):
        return 'gg.js is expired'    

class GGJs():
    """
    画像データのurl取得に必要なgg.jsをparseしたもの。
    取得したgg.jsはサーバーから提示されたExpireで期限切れとなる
    """
    def __init__(self, b_value: str, s_func: Callable[[str], str], m_func: Callable[[int], int], is_expire: Callable[[float], None]) -> None:
        self.b_value = b_value
        self.s_func = s_func
        self.m_func = m_func
        self.is_expire = is_expire

# gg.jsオブジェクトのパース関数
def parse_gg() -> GGJs:
    """
    画像データのurl取得に必要なgg.jsをparseする関数。
    取得したgg.jsはサーバーから提示されたExpireで期限切れとなる
    """
    gg_url = 'https://ltn.gold-usergeneratedcontent.net/gg.js'
    try:
        response = requests.get(gg_url)
        response.raise_for_status() #<---- ここで止まる
    except requests.HTTPError as e:
        print(f'Failed to fetch gg.js\n{e}')
        raise e
    js_code = response.text
    
    # b の抽出
    b_match = re.search(r"b:\s*'([^']+)'", js_code)
    if not b_match:
        raise ValueError("b value not found in gg.js")
    b_value = b_match.group(1)
    
    # s 関数の定義
    def gg_s(h: str) -> str:
        m = re.search(r'(..)(.)$', h)
        if m:
            return str(int(m.group(2) + m.group(1), 16))
        else:
            raise ValueError("Invalid hash format")    
    
    # m 関数の定義
    def gg_m(g: int) -> int:
        # m のケースの抽出
        m_cases = re.findall(r"case (\d+):", js_code)
        m_cases = [int(case) for case in m_cases]
        
        # m関数に必要なoの抽出
        initial_o_match = re.search(r"var o = (\d+);", js_code)
        initial_o_value = int(initial_o_match.group(1)) if initial_o_match else None
        if initial_o_value is None:
            raise ValueError('initial o value not found in gg.js')
        
        assigned_o_match = re.search(r"case \d+:\s*(?:case \d+:\s*)*o = (\d+);", js_code)
        assigned_o_value = int(assigned_o_match.group(1)) if assigned_o_match else None
        if assigned_o_value is None:
            raise ValueError('assigned o value not found in gg.js')
        o = initial_o_value
        if (g in m_cases):
            o = assigned_o_value
        return o
    
    # gg オブジェクトの期限unix時間を取得、比較
    def is_expire(current_unix_time: float) -> None:
        """
        期限切れならエラーをraise 
        """
        try:
            time_str_may_be_gmt = response.headers['Expires']
            parsed_datetime = parse(time_str_may_be_gmt)
            utc_datetime = parsed_datetime.astimezone(tzutc())
            expire_unix_time = utc_datetime.timestamp()
        except Exception as e:
            print('Failed to parse expire timestamp of gg.js')
            raise e
        if current_unix_time >= expire_unix_time:
            raise GGJsIsExpire()
    
    # gg オブジェクトの作成
    gg_js = GGJs(b_value=b_value, s_func=gg_s, m_func=gg_m, is_expire=is_expire)
    
    return gg_js

# 定数の定義
domain2 = 'gold-usergeneratedcontent.net'

# 関数定義
def full_path_from_hash(hash: str, gg: GGJs) -> str:
    return gg.b_value + gg.s_func(hash) + '/' + hash

def url_from_hash(gallery_id: int, file_info: FileInfo, gg: GGJs, dir: str, ext: str|None=None):
    if ext is None:
        ext = dir if dir else file_info.name.split('.')[-1]
    if dir in ['webp', 'avif']:
        dir = ''
    else:
        dir += '/'
    
    return f'https://a.{domain2}/{dir}{full_path_from_hash(file_info.hash, gg)}.{ext}'

def subdomain_from_url(url: str, gg: GGJs, dir:str|None=None, base: str|None=None) -> str:
    retval = ''
    if not base:
        if dir == 'webp':
            retval = 'w'
        elif dir == 'avif':
            retval = 'a'
    
    b = 16
    r = re.compile(r'/[0-9a-f]{61}([0-9a-f]{2})([0-9a-f])')
    m = r.search(url)
    if not m:
        return retval
    
    g = int(m.group(2) + m.group(1), b)

    if base:
        retval = chr(97 + gg.m_func(g)) + base
    else:
        retval += str(1 + gg.m_func(g))
        
    return retval

def url_from_url(url: str, gg: GGJs, dir: str, base: str|None) -> str:
    subdomain = subdomain_from_url(url, gg, dir, base)
    return re.sub(r'//..?\.(?:gold-usergeneratedcontent\.net|hitomi\.la)/', f'//{subdomain}.{domain2}/', url)

def url_from_file_info(gallery_id: int, file_info: FileInfo, gg: GGJs|None=None,  dir: str|None=None, ext: str|None=None, base: str|None=None) -> str:
    if gg is None:
        gg = parse_gg()
    if dir is None:
        dir = "avif" if file_info.has_avif else "webp"

    if base == 'tn':
        url_by_url_from_url = url_from_url(f'https://a.{domain2}/{dir}/{full_path_from_hash(file_info.hash, gg)}.{ext}', gg, base, dir)
        #gg.js の期限確認
        gg.is_expire(time.time())
        return url_by_url_from_url
    
    url_by_url_from_url = url_from_url(url=url_from_hash(gallery_id=gallery_id, file_info=file_info, gg=gg, dir=dir, ext=ext), gg=gg, base=base, dir=dir)
    #gg.js の期限確認
    gg.is_expire(time.time())
    return url_by_url_from_url