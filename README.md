## 特徴

*   **ギャラリー情報の取得:** 指定されたギャラリーIDから作品情報（タイトル、タグ、ファイル情報など）を取得・解析します 。
*   **画像URLの生成:** ギャラリーに含まれる各画像のダウンロードURLを生成します。このプロセスは、特定のJavaScriptファイル (`gg.js`) の解析により実現されています。
*   **画像データのダウンロード:** 生成されたURLを使用して、画像データをダウンロードします 。
*   **ヘッダーの偽装:** HTTPリクエスト時に、リファラーやユーザーエージェントなどのヘッダーを偽装する機能を含んでいます 。ユーザーエージェントは、ランダムなデバイス、プラットフォーム、ブラウザを組み合わせて生成されます。
*   **並行ダウンロード:** ギャラリー内の複数の画像を効率的にダウンロードするために、スレッドプールエグゼキュータ (`concurrent.futures.ThreadPoolExecutor`) を使用した並行処理をサポートしています。
*   **情報の期限管理:** 取得したギャラリー情報 (`{gallery_id}.js` から) およびURL生成に必要な情報 (`gg.js` から) がサーバーによって提示された期限 (`Expires` ヘッダー) を過ぎていないかチェックする機能を含んでいます。
*   **JSONでの情報保存:** ダウンロード時に、取得したギャラリー情報をJSON形式で保存するオプションがあります。


## 使用方法

`hitomi_util.py` の `save_all_image_data_from_id` 関数を使用することで、特定のギャラリーIDの画像をすべてダウンロードできます。

```python
# hitomi_util.py をインポート
from hitomi_util import save_all_image_data_from_id

# ダウンロードしたいギャラリーのIDを指定
gallery_id_to_download = 3062749 # 例としてテスト用のIDを使用 [29]

# 画像を保存するディレクトリを指定 (省略可能、指定しない場合はカレントディレクトリに保存) [18]
save_directory = 'downloaded_galleries' # 例

# 画像のダウンロードと保存を実行
try:
    save_all_image_data_from_id(gallery_id=gallery_id_to_download, save_dir=save_directory)
    print(f"Gallery {gallery_id_to_download} のダウンロードが完了しました。")
except Exception as e:
    print(f"ダウンロード中にエラーが発生しました: {e}")
