import io
import time
import struct
import hashlib
import requests
import numpy as np
from typing import Any
import numpy.typing as npt
from dataclasses import dataclass
from hitomi_util import get_gallery_info

def get_index_version() -> str:
    js_epoch_time: int = int(time.time() * 1000)
    url = f'https://ltn.gold-usergeneratedcontent.net/galleriesindex/version?_={js_epoch_time}'
    try:
        response = requests.get(url)
        response.raise_for_status()
        index_version = response.text
    except Exception as e:
        print(f'Failed to parse index_version. error: {e}')
        raise e
    return index_version


def get_url_at_range(url: str, range: tuple[int, int]) -> npt.NDArray[np.uint8]:
    """サーバーからアドレス範囲を指定したindexファイルを取得する関数

    Args:
        url (str): おそらくhttps://ltn.gold-usergeneratedcontent.net/galleriesindex/galleries.{indexversion}.index
        range (tuple[int, int]): 取得する.indexのアドレス範囲

    Raises:
        e: httpエラーもしくはunit8ではないレスポンスをparseしようとしたエラー

    Returns:
        uint8_array (npt.NDArray[np.uint8]): uint8_array化されたレスポンス
    """
    headers: dict[str, str] = {'Range': f'bytes={range[0]}-{range[1]}'}
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()

        content_bytes = response.content
        unit8_array = np.frombuffer(content_bytes, dtype=np.uint8)
    except Exception as e:
        print(f'Failed to parse uint8_array. error: {e}')
        raise e
    return unit8_array


@dataclass
class NodeData:
    offset: np.uint64
    length: np.int32


@dataclass
class Node:
    """subnode_addressesの流さばおそらく17になる(https://ltn.gold-usergeneratedcontent.net/searchlib.js のconst Bより)
    """
    keys: list[npt.NDArray[np.uint8]]
    datas: list[NodeData]
    subnode_addresses: list[np.uint64]


def read_int_or_uint_N_big_endian_from_adarray8(data: npt.NDArray[np.uint8], dtype: type, position: int) -> Any:
    dtype_str = str(dtype)  # 例: <class 'numpy.uint8'>
    if 'uint' in dtype_str:
        signed = False
    elif 'int' in dtype_str:
        signed = True
    else:
        raise ValueError(f'Invalid dtype: {dtype_str}')
    buffer = io.BytesIO(data.tobytes())
    read_byte = np.dtype(dtype).itemsize
    if read_byte == 1:
        format_suffix = 'b' if signed else 'B'
    elif read_byte == 2:
        format_suffix = 'h' if signed else 'H'
    elif read_byte == 4:
        format_suffix = 'i' if signed else 'I'
    elif read_byte == 8:
        format_suffix = 'q' if signed else 'Q'
    else:
        raise ValueError(f'Unsupported byte length: {read_byte}')
    buffer.seek(position)
    result = struct.unpack(
        '>'+format_suffix, buffer.read(read_byte))  # type: ignore
    return dtype(result[0])


def decode_node(data: npt.NDArray[np.uint8]) -> Node:
    pos: int = 0

    keys: list[npt.NDArray[np.uint8]] = []
    number_of_keys = read_int_or_uint_N_big_endian_from_adarray8(
        data, np.int32, pos)
    pos += 32//8
    for _ in range(number_of_keys):
        key_size = read_int_or_uint_N_big_endian_from_adarray8(
            data, np.int32, pos)
        if (not key_size) or (key_size > 32):
            raise ValueError(
                'Failed to parse key_size\nkey_size must be 32 or less')
        pos += 32//8
        keys.append(data[pos: pos+key_size])
        pos += key_size

    datas: list[NodeData] = []
    number_of_datas = read_int_or_uint_N_big_endian_from_adarray8(
        data, np.int32, pos)
    pos += 32//8
    for _ in range(number_of_datas):
        offset = read_int_or_uint_N_big_endian_from_adarray8(
            data, np.uint64, pos)
        pos += 64//8
        length = read_int_or_uint_N_big_endian_from_adarray8(
            data, np.int32, pos)
        pos += 32//8
        node_data = NodeData(offset, length)
        datas.append(node_data)

    subnode_addresses: list[np.uint64] = []
    # https://ltn.gold-usergeneratedcontent.net/searchlib.js の const B = 16から
    number_of_subnode_addresses = 17
    for _ in range(number_of_subnode_addresses):
        subnode_addresse = read_int_or_uint_N_big_endian_from_adarray8(
            data, np.uint64, pos)
        pos += 64//8
        subnode_addresses.append(subnode_addresse)

    return Node(keys, datas, subnode_addresses)


def get_node_at_address(field: str, address: np.uint64, galleries_index_version: str, serial: bool | None = None) -> Node:
    # url = '//'+'ltn.gold-usergeneratedcontent.net'+'/'+'tagindex'+'/'+field+'.'+tag_index_version+'.index'
    if (field == 'galleries'):
        url = 'https://'+'ltn.gold-usergeneratedcontent.net'+'/' + \
            'galleriesindex'+'/galleries.'+galleries_index_version+'.index'
    else:
        raise ValueError('開発途中です')
    # https://ltn.gold-usergeneratedcontent.net/searchlib.js の const max_node_size = 464から
    max_node_size = 464
    address_int = int(address)
    node_unit8 = get_url_at_range(
        url, (address_int, address_int+max_node_size-1))
    node = decode_node(node_unit8)
    return node


def b_search(field: str, key: npt.NDArray[np.uint8], node: Node, galleries_index_version: str, serial: str | None = None) -> NodeData | bool:

    def _compare_arraybuffers(dv1: npt.NDArray[np.uint8], dv2: npt.NDArray[np.uint8]):
        top: int = min(len(dv1), len(dv2))
        for i in range(top):
            if (dv1[i] < dv2[i]):
                return -1
            elif (dv1[i] > dv2[i]):
                return 1
        return 0

    def _locate_key(key: npt.NDArray[np.uint8], node: Node) -> tuple[bool, int]:
        comp_result_int = -1
        i = 0
        for _ in range(len(node.keys)):
            comp_result_int = _compare_arraybuffers(key, node.keys[i])
            if (comp_result_int <= 0):
                break
            i += 1
        if (comp_result_int == 0):
            comp_result = False
        else:
            comp_result = True
        return (not comp_result, i)

    def _is_leaf(node: Node):
        for node_subaddress in node.subnode_addresses:
            if (node_subaddress):
                return False
        return True

    if not (len(node.keys)):
        return False

    there, where = _locate_key(key, node)

    if (there):
        return node.datas[where]  # このreturnで終わらない下のb_serchが実行される
    elif (_is_leaf(node)):
        return False

    if (node.subnode_addresses[where] == 0):
        raise Exception('non-root node address 0')

    return b_search(field, key, get_node_at_address(field, node.subnode_addresses[where], galleries_index_version), galleries_index_version)


# 基本的にはlist[np.int32]
def get_galleryids_from_data(data: NodeData, galleries_index_version: str) -> list[Any]:
    url = f'https://ltn.gold-usergeneratedcontent.net/galleriesindex/galleries.{galleries_index_version}.data'
    offset, length = data.offset, data.length
    if ((length > 1e8) or (length <= 0)):
        print(f'length: {length} is too long')
        return []
    inbuf = get_url_at_range(url, (int(offset), int(offset+length-1)))
    if not (inbuf.any()):
        return []
    galleries: list[Any] = []

    pos = 0
    number_of_galleries = read_int_or_uint_N_big_endian_from_adarray8(
        inbuf, np.int32, pos)
    pos += 32//8

    expected_length = 4 + number_of_galleries * 4
    if ((number_of_galleries > 1e7) or number_of_galleries <= 0):
        print(f'number_of_galleries: {number_of_galleries} is too long')
        return []
    elif (len(inbuf) != expected_length):
        print(
            f'len(inbuf): {len(inbuf)} != expected_length: {expected_length}')
        return []

    for _ in range(number_of_galleries):
        galleries.append(
            read_int_or_uint_N_big_endian_from_adarray8(inbuf, np.int32, pos))
        pos += 32//8

    return galleries


def get_galleryids_for_query(query: str) -> list[Any]:
    query_hashed = hashlib.sha256(query.encode()).digest()
    key = np.frombuffer(query_hashed[:4], dtype=np.uint8)
    field = 'galleries'
    index_version: str = get_index_version()

    initinal_node = get_node_at_address(field, np.uint64(0), index_version)

    data = b_search(field, key, initinal_node, index_version)
    if (isinstance(data, bool) and not data):
        print(f'No data found for query: {query}')
        return []
    elif (isinstance(data, bool) and data):
        raise Exception('Unexpected boolean return value from b_search')

    return get_galleryids_from_data(data, index_version)


def test():
    ids = get_galleryids_for_query('aaaa')
    for id in ids:
        gallery_info = get_gallery_info(id)
        artsist_names = ''
        for artist in gallery_info.artists:
            if (artsist_names == ''):
                artsist_names = artist.artist.capitalize()
            else:
                artsist_names += f', {artist.artist.capitalize()}'
        title = gallery_info.japanese_title or gallery_info.title
        print(f'{id=}, {artsist_names}「{title}」')


if __name__ == '__main__':
    test()
