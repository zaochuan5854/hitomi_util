import json
import warnings
import requests
from dateutil.parser import parse
from dateutil.tz import tzutc
from dataclasses import dataclass, asdict
from typing import Callable, Any

class GalleryJsIsExpire(Exception):
    def __init__(self, gallery_id: int) -> None:
        super().__init__(self)
        self.gallery_id = gallery_id
    
    def __str__(self):
        return f'{self.gallery_id}.js is Expired'

@dataclass
class ArtistInfo:
    artist: str
    url: str

@dataclass
class GroupInfo:
    group: str
    url: str

@dataclass
class ParodyInfo:
    parody: str
    url: str

@dataclass
class CharacterInfo:
    character: str
    url: str

@dataclass
class TagInfo:
    tag: str
    url: str
    male: bool|None = None
    female: bool|None = None

    def __init__(self, **kwargs: str|None):
        for key, value in kwargs.items():
            try:
                if value is None:
                    continue
                else:
                    match key:
                        case 'tag':
                            self.tag = value
                        case 'url':
                            self.url = value
                        case 'male':
                            self.male = True if value == '1' else False
                        case 'female':
                            self.female = True if value == '1' else False
                        case _:
                            warnings.warn(f'Ignored tag: {str({key: value})}')
            except TypeError as e:
                print(f'Failed to init TagInfo\nInput: {kwargs}\nLast validated data: {str({key: value})}')
                raise e

@dataclass
class FileInfo:
    name: str
    hash: str
    width: int
    height: int
    has_avif: bool = False
    has_webp: bool = False
    has_jxl: bool = False
    def __init__(self, **kwargs: str|int|None):
        for key, value in kwargs.items():
            try:
                if value is None:
                    continue
                elif isinstance(value, str):
                    match key:
                        case 'name':
                            self.name = value
                        case 'hash':
                            self.hash = value
                        case _:
                            warnings.warn(f'Ignored file_info: {str({key: value})}')
                else:
                    match key:
                        case 'width':
                            self.width = value
                        case 'height':
                            self.height = value
                        case 'hasavif':
                            self.has_avif = True if value==1 else False
                        case 'haswebp':
                            self.has_webp = True if value==1 else False
                        case 'hasjxl':
                            self.has_jxl = True if value==1 else False
                        case _:
                            warnings.warn(f'Ignored file_info: {str({key: value})}')
            except TypeError as e:
                print(f'Failed to init FileInfo\nInput: {kwargs}\nLast validated data: {str({key: value})}')
                raise e
        
@dataclass
class GalleryInfo:
    gallery_id: int
    title: str
    japanese_title: str
    artists: list[ArtistInfo]
    groups: list[GroupInfo]
    type: str
    language: str
    language_local_name: str
    parodies: list[ParodyInfo]
    characters: list[CharacterInfo]
    tags: list[TagInfo]
    files_info: list[FileInfo]
    related: list[int]
    is_expire: Callable[[float], None]|None
    
    def __init__(self, id: int, title: str, japanese_title: str, artists: list[dict[str, str]], groups: list[dict[str, str]], type: str, language: str, language_localname: str, parodys: list[dict[str, str]], characters: list[dict[str, str]], tags: list[dict[str, str]], files: list[dict[str, str|int|bool]], related: list[int], is_expire: Callable[[float], None]|None=None, **kwargs: Any):
        self.gallery_id = id
        self.title = title or ''
        self.japanese_title = japanese_title or ''
        self.artists = [ArtistInfo(**artist) for artist in artists] if artists else []
        self.groups = [GroupInfo(**group) for group in groups] if groups else []
        self.type = type or ''
        self.language = language or ''
        self.language_local_name = language_localname or ''
        self.parodies = [ParodyInfo(**parody) for parody in parodys] if parodys else []
        self.characters = [CharacterInfo(**character) for character in characters] if characters else []
        self.tags = [TagInfo(**tag) for tag in tags] if tags else []
        self.files_info = [FileInfo(**file) for file in files] if files else []
        self.related = related or []
        self.is_expire = is_expire
        
    def to_json(self) -> str:
        gallery_info_dict = asdict(self)
        gallery_info_dict['is_expire'] = None
        return json.dumps(gallery_info_dict, ensure_ascii=False, indent=4)

#作品情報が記述された生のjsを取得してGalleryInfoにパース(is_expireはここでは定義しない)
def extract_gallery_info_from_gallery_js(js_text: str):
    json_string = js_text.replace('var galleryinfo = ', '').strip("'")
    gallery_info_json = json.loads(json_string)
    gallery_info = GalleryInfo(**gallery_info_json)
    return gallery_info

#作品idから作品情報を取得(is_expireを設定)
def gallery_info_from_id(gallery_id: int, test_js_text: str|None=None) -> GalleryInfo:
    """作品idから作品情報を取得する

    Args:
        gallery_id (int): 作品id
        test_js_text (str | None, optional): 特定のjsを文字列として渡しテストを行う. Defaults to None.

    Raises:
        e: 作品情報の取得に失敗
        e: gg.jsから期限切れとなるタイムスタンプのparseに失敗
        GalleryJsIsExpire: 作品情報GalleryInfoの期限切れ

    Returns:
        GalleryInfo: 作品情報をまとめたdataclass
    """
    if test_js_text is None:
        gallery_url = f"https://ltn.gold-usergeneratedcontent.net/galleries/{int(gallery_id)}.js"
        try:
            response = requests.get(gallery_url)
            response.raise_for_status()
        except requests.HTTPError as e:
            print(f'Failed to fetch {str(gallery_id)}.js')
            raise e
        js_text = response.text
    else:
        js_text = test_js_text
    
    def is_expire(current_unix_time: float) -> None:
        nonlocal response
        try:
            time_str_may_be_gmt = response.headers['Expires']
            parsed_datetime = parse(time_str_may_be_gmt)
            utc_datetime = parsed_datetime.astimezone(tzutc())
            expire_unix_time = utc_datetime.timestamp()
        except Exception as e:
            print('Failed to parse expire timestamp of gg.js')
            raise e
        if current_unix_time >= expire_unix_time:
            raise GalleryJsIsExpire(gallery_id=gallery_id)
    
    gallery_info = extract_gallery_info_from_gallery_js(js_text)
    gallery_info.is_expire = is_expire
    return gallery_info

def test(test_id: int=2312974):
    test_js_text = 'var galleryinfo = {"languages":[{"language_localname":"English","galleryid":2576988,"name":"english","url":"/galleries/2576988.html"},{"language_localname":"中文","url":"/galleries/2315413.html","galleryid":2315413,"name":"chinese"},{"language_localname":"日本語","galleryid":2312974,"name":"japanese","url":"/galleries/2312974.html"}],"files":[{"hasavif":1,"haswebp":1,"hasjxl":0,"hash":"ce52befd53c3f95d70109ca03780a73f3ea754f6d8a921842bf902c9d50f58b1","name":"01.png","width":2132,"height":3023},{"name":"02.png","haswebp":1,"hasjxl":0,"hash":"75ebdf52f1a01fe179dd7bc1a14489c966dbf327ed071cf9e743e3afc0847e42","hasavif":1,"width":2053,"single":1,"height":3028},{"haswebp":1,"hasjxl":0,"hash":"7c09615510373b2eb66d29402cb7ccd9499fab6456311419f161174e742a5f32","hasavif":1,"width":2034,"height":3031,"name":"03.png"},{"hasavif":1,"hasjxl":0,"hash":"8c0001b31e1182d39d436f5f87bcd8fbaad425c973e49a7b9ccb4afab4914f49","haswebp":1,"name":"04.png","height":3024,"width":2099},{"name":"05.png","width":2058,"height":3034,"hasavif":1,"haswebp":1,"hash":"643fb741de95b3b1415187b948f77c7cbfc09c602544932caab5485926cc8cfb","hasjxl":0},{"hasavif":1,"haswebp":1,"hash":"0342db2ec998fd717650f891ad7356eac599d3e8f405f7a468252216f157c232","hasjxl":0,"name":"06.png","width":2047,"height":3034},{"hasavif":1,"hash":"4a459a927630c3634ceeaeb26c4f2efb1af36a4afc103a098831b72e055bc618","hasjxl":0,"haswebp":1,"name":"07.png","height":3031,"width":2064},{"name":"08.png","height":3028,"width":2091,"hasavif":1,"hash":"6c12257da4eb7b7d27fb35f29f9ebb062576674c7aee2ecc69ddc7ba150b0f10","hasjxl":0,"haswebp":1},{"height":3028,"width":2050,"name":"09.png","hash":"f52a966c161a43d3f773cca9eee9223111b3d2110b80f7c189876e31e60118e1","hasjxl":0,"haswebp":1,"hasavif":1},{"name":"10.png","height":3031,"width":2072,"hasavif":1,"hasjxl":0,"hash":"0abbe0c893cbd2557217941873675e83bd10f4d3a99fe664d0b49c5ec6648cde","haswebp":1},{"hasjxl":0,"hash":"099aabe51dc362709bf881266b3d3ab46b640c20ff26d16627952408ca70294f","haswebp":1,"hasavif":1,"height":3031,"width":2034,"name":"11.png"},{"width":2067,"height":3026,"name":"12.png","haswebp":1,"hasjxl":0,"hash":"924b0e7f49d4a0cd70119855c34ededf3c218760de034a4dde31e7915939fc2f","hasavif":1},{"name":"13.png","width":2045,"height":3031,"hasavif":1,"haswebp":1,"hash":"e7b5697b6357993bb5265ce0a7a455f34868735331853ae4f44583b538c71723","hasjxl":0},{"height":3025,"width":2067,"name":"14.png","hasjxl":0,"hash":"06294d287d3792ede837b77651d114f19f360f19ef4ee2f53b243ab921b5911c","haswebp":1,"hasavif":1},{"height":3029,"width":2018,"name":"15.png","hash":"64a32919fd17f43a2614314961cc3dd3e564fadf7e776ec36c7ace0a1d1dfc07","hasjxl":0,"haswebp":1,"hasavif":1},{"hasavif":1,"hasjxl":0,"hash":"198fb64595b031c1cfd27c584bf299c4e1a866be9493c20fa602d04984757023","haswebp":1,"name":"16.png","height":3031,"width":2070},{"width":2031,"height":3030,"name":"17.png","haswebp":1,"hasjxl":0,"hash":"13d3f699fb353844dde92aa8ddb50b1da4158411763b9bbb953a8c5d17565f3c","hasavif":1},{"name":"18.png","width":2056,"height":3023,"hasavif":1,"haswebp":1,"hasjxl":0,"hash":"a21ab639472566215f3738a2b152c4a4ac95b15056d210005be7e9deee02aac6"},{"name":"19.png","height":3028,"width":2053,"hasavif":1,"hash":"068df9299d1cdadaaf412b43d12c95020406b9816542178a412a7916f16340ee","hasjxl":0,"haswebp":1},{"hasavif":1,"haswebp":1,"hasjxl":0,"hash":"96c919ab79aac7a420ec40571dcdbd0922285d74dfd264203a83fec5d7df52b6","name":"20.png","width":2064,"height":3031},{"hasjxl":0,"hash":"a7aac7d306daa35d36d6626648d1bb3e41e5d009cc5e9c6e4d52774c25176109","haswebp":1,"hasavif":1,"height":3036,"width":2039,"name":"21.png"},{"name":"22.png","height":3023,"width":2020,"hasavif":1,"hasjxl":0,"hash":"cade3cea3445a180513c24563bb022fb96ce4c153332b8a8cfeaf0d27c972de1","haswebp":1},{"width":2040,"height":3028,"name":"23.png","haswebp":1,"hasjxl":0,"hash":"f0bf44f45cbba1fc00c0c419b44a6995846b170021a18bcff85e82c516dbff36","hasavif":1},{"width":2037,"height":3028,"name":"24.png","haswebp":1,"hasjxl":0,"hash":"8047e65f9c3aa8f0f6b9c315c42931a4b8a34d025015ba354ca0feb9487b7c75","hasavif":1},{"name":"25.png","width":2036,"height":3023,"hasavif":1,"haswebp":1,"hash":"49c6404cf5a5a322ce013669261097e4521f9eff85e0e20f8fb55476e24d199e","hasjxl":0},{"hasavif":1,"haswebp":1,"hasjxl":0,"hash":"d1926a2ed30097668f4c062d3d0fefeab75b7a3e46a287b75baf21da6d0164c0","name":"26.png","width":2025,"height":3028},{"hasjxl":0,"hash":"7f156776db191f0368479230d9b017b34812eaad7f68c356286ec9ddb8fe2e4e","haswebp":1,"hasavif":1,"height":3031,"width":2040,"name":"27.png"},{"height":3018,"width":2023,"name":"28.png","hasjxl":0,"hash":"7d6616f23f56c356b056911bd995409bb928e340ceee48e02f07fe1deba0c41a","haswebp":1,"hasavif":1},{"hasavif":1,"haswebp":1,"hash":"6edef606d525d4e2df3ede317916f7899dfe44191995d4520ef5bf8f1a1d267b","hasjxl":0,"name":"29.png","width":2009,"height":3034},{"hash":"7bb4eba683e881558856766262dba7435a4cd1b37647ecb72d33c76c9d11b160","hasjxl":0,"haswebp":1,"hasavif":1,"height":3022,"width":2037,"name":"30.png"},{"height":3025,"width":2007,"name":"31.png","hash":"323d95db330fec9f7080156b1c39ca57b353023795be2c9f02b9c15e63207aa7","hasjxl":0,"haswebp":1,"hasavif":1},{"name":"32.png","width":2021,"height":3031,"hasavif":1,"haswebp":1,"hasjxl":0,"hash":"21a6bf51d6858d8122def5369a4765de3a15ccbc86fcdd30ea680fb712f0e7b6"},{"name":"33.png","height":3034,"width":2015,"hasavif":1,"hash":"a86b6bfcbc675d0c001bb4d0175726ff58c02ce64011fab8e9e51985a1100b29","hasjxl":0,"haswebp":1},{"hash":"815b870e9b94bfacc37d2223ef49fc3b72c024d0deee23972df742d5f995a3ff","hasjxl":0,"haswebp":1,"hasavif":1,"height":3029,"width":2029,"name":"34.png"},{"name":"35.png","height":3031,"width":2028,"hasavif":1,"hash":"cfa9706d49c692e5c05c9a56ce77e16c727e517d94314d95c18ae269bfcd9f53","hasjxl":0,"haswebp":1},{"name":"36.png","height":3028,"width":2040,"hasavif":1,"hasjxl":0,"hash":"e732edf85acd72f18425f9636d78494d12d8b073bbf7e2474f6438df3cb44df0","haswebp":1},{"name":"37.png","width":2017,"height":3025,"hasavif":1,"haswebp":1,"hasjxl":0,"hash":"49b9dd3778e66496202569485d491cf857f78159076da613de8cd4f00a6a4f8b"},{"haswebp":1,"hash":"e5c08a727584be39e77983b22414a106b66f3062a47ef51ad16ec5aa105fd22f","hasjxl":0,"hasavif":1,"width":2037,"height":3026,"name":"38.png"},{"hasavif":1,"haswebp":1,"hash":"8298bbde376356e1fb60d2d09dfbf7c6e90d4cfe24f8ad459535c0903b5335bf","hasjxl":0,"name":"39.png","width":2051,"height":3031},{"hasavif":1,"haswebp":1,"hash":"9b6c90275865613096a495389a85122cc0659c1fd714c57ab44079fcb75f6f8b","hasjxl":0,"name":"40.png","width":2045,"height":3001},{"haswebp":1,"hasjxl":0,"hash":"2ac0b09a24184408e5533ef69495c6e2313385a671407bc54586bd3f308b558d","hasavif":1,"width":1976,"height":2993,"name":"41.png"},{"haswebp":1,"hash":"9933ea69eaaf99783ab68af0611b8b6ddbaed3971dae510b71447bcb7b9217f6","hasjxl":0,"hasavif":1,"width":2112,"height":2997,"name":"42.png"}],"date":"2022-08-29 19:17:00-05","language":"japanese","videofilename":null,"artists":[{"url":"/artist/fue-all.html","artist":"fue"},{"url":"/artist/kizuka%20kazuki-all.html","artist":"kizuka kazuki"}],"japanese_title":"秩序バケーション","id":"2312974","scene_indexes":[],"title":"Chitsujo Vacation","groups":[{"url":"/group/ikkizuka-all.html","group":"ikkizuka"}],"type":"doujinshi","blocked":0,"characters":[{"url":"/character/gran-all.html","character":"gran"},{"character":"heles","url":"/character/heles-all.html"},{"character":"monika","url":"/character/monika-all.html"},{"url":"/character/monika%20weisswind-all.html","character":"monika weisswind"}],"galleryurl":"/doujinshi/秩序バケーション-日本語-417750-2312974.html","language_localname":"日本語","language_url":"/index-japanese.html","video":null,"related":[1553483,1552028,1592227,1450678,1425868],"tags":[{"url":"/tag/female%3Ablowjob-all.html","tag":"blowjob","male":"","female":"1"},{"tag":"c100","url":"/tag/c100-all.html"},{"female":"1","tag":"deepthroat","male":"","url":"/tag/female%3Adeepthroat-all.html"},{"male":"","tag":"fingering","url":"/tag/female%3Afingering-all.html","female":"1"},{"male":"","tag":"nakadashi","url":"/tag/female%3Anakadashi-all.html","female":"1"},{"male":"","tag":"paizuri","url":"/tag/female%3Apaizuri-all.html","female":"1"},{"url":"/tag/female%3Atwintails-all.html","male":"","tag":"twintails","female":"1"}],"parodys":[{"parody":"granblue fantasy","url":"/series/granblue%20fantasy-all.html"}],"datepublished":"2022-08-13"}'
    files_info = gallery_info_from_id(test_id, test_js_text)
    print(files_info)
    
if __name__ == '__main__':
        test()