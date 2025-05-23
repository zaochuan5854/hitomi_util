import os
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor, as_completed, Future
from gallery_info_from_id import gallery_info_from_id, GalleryInfo
from url_from_file_info import url_from_file_info, parse_gg, GGJs
from fetch_image_from_url import fetch_image_from_url
#作品情報を取得
def get_gallery_info(gallery_id: int) -> GalleryInfo:
    return gallery_info_from_id(gallery_id)

#作品に含まれる画像urlのリストを取得
def urls_form_id(gallery_id: int, gallery_info: GalleryInfo|None=None, gg: GGJs|None=None) -> list[str]:
    if gallery_info is None:
        gallery_info = get_gallery_info(gallery_id)
    if gg is None:
        gg = parse_gg()
    urls: list[str] = []
    for file_info in gallery_info.files_info:
        urls.append(url_from_file_info(gallery_id, file_info, gg))
    return urls

#作品に含まれる画像をすべてダウンロード
def save_all_image_data_from_id(gallery_id: int, gallery_info: GalleryInfo|None=None, gg: GGJs|None=None, save_dir: str|None=None, save_json: bool=True) -> None:
    """作品に含まれる画像バイト列をすべてダウンロードする関数
    Args:
        gallery_id (int): 作品id
        gallery_info (GalleryInfo|None): {gallery_id}.jsをparseしたGalleryInfo。固定すれば高速化できるが、期限切れになる可能性がある Defaults to None.
        gg (GGJs|None): gg.jsをparseしたオブジェクト。固定すれば高速化できるが、期限切れになる可能性がある Defaults to None.
        save_dir (str|None): 保存先ディレクトリ。指定しない場合はカレントディレクトリに保存される Defaults to None.
    """
    if gallery_info is None:
        gallery_info = get_gallery_info(gallery_id)
    if gg is None:
        gg = parse_gg()
    urls = urls_form_id(gallery_id, gallery_info, gg)
    if save_dir is None:
        save_dir = os.getcwd()
    gallery_id_str_format = f'{gallery_id:08}'
    
    save_dir = os.path.join(save_dir, f'{gallery_id_str_format}_{gallery_info.japanese_title.replace(' ', '') or gallery_info.title.replace(' ', '_')}')
    os.makedirs(save_dir, exist_ok=True)
    
    if save_json:
        json_path = os.path.join(save_dir, f'{gallery_id_str_format}.json')
        with open(json_path, 'w', encoding='utf-8') as f:
            f.write(gallery_info.to_json())
    
    def write_image_data(image_data: bytes, file_path: str) -> str:
        with open(file_path, 'wb') as f:
            f.write(image_data)
        return file_path
            
    max_worker = 5
    with ThreadPoolExecutor(max_workers=max_worker) as executor:
        futures: list[Future[bytes]] = []
        for url in urls:
            futures.append(executor.submit(fetch_image_from_url, gallery_id, url))
        for future in tqdm(as_completed(futures), total=len(futures), desc=f'ダウンロード中: {gallery_id}({gallery_info.japanese_title or gallery_info.title})'):
            index = futures.index(future)
            save_path = os.path.join(save_dir, f'{gallery_id_str_format}_{index:05}{os.path.splitext(urls[index])[-1]}')
            if os.path.exists(save_path):
                #print(f'File already exists: {save_path}')
                future.cancel()
                continue
            image_data = future.result()
            write_image_data(image_data, save_path)


def test(test_gallery_id: int=3062749):
    save_all_image_data_from_id(gallery_id=test_gallery_id, save_dir='hitomi.la')

if __name__ == "__main__":
    test()