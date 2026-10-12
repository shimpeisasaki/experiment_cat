# d1地面分類のrosbag比較実験

ZEDの画像の下半分をd1-3Bへ送る実験ノードです。１枚モードでは下半分全体を１回で送って左右中央を３問で分類します。３枚モードでは下半分から同じ大きさで重なりのある左・中央・右を作り、それぞれ１回ずつ送ります。推論中の画像はためず、次の推論にはその時点の最新画像を使います。画像はメモリ上でJPEG化し、切り出し画像のトピックやファイルは作りません。

質問は屋内床、歩道などの歩行者用舗装、芝生・土、車道、不明の５択です。結果は画像の観察に過ぎず、走行許可や停止指令には接続しません。LiDARの安全機能にも接続しません。境界をまたぐ場合は不明を選ぶよう質問していますが、モデルの回答の正しさを保証するものではありません。

## 起動

別端末でd1対応のllama.cppサーバーを起動し、ROS 2 Humbleとワークスペースを読み込んでください。

```bash
colcon build --symlink-install --packages-select experiment_cat
source install/setup.bash
ros2 launch experiment_cat d1_ground_eval.launch.py use_sim_time:=true
```

rosbagをクロック付きで再生します。袋には画像トピックが13,338件あります。

```bash
ros2 bag play data/manual_test_1011_1404 --clock
```

再生中、別端末から開始と停止を指示します。

```bash
# 下半分１枚
ros2 service call /d1_ground_eval/start std_srvs/srv/SetBool '{data: false}'
# 下半分を重複する３枚に分割
ros2 service call /d1_ground_eval/start std_srvs/srv/SetBool '{data: true}'
# 停止
ros2 service call /d1_ground_eval/stop std_srvs/srv/Trigger '{}'
ros2 topic echo /d1_ground_eval/result
```

結果はJSON文字列です。`answers`に各領域の選択肢と確率、`preprocess_ms`、`inference_ms`、`total_ms`、`image_age_at_result_ms`に時間を出します。エラーも`status: error`で配信します。停止時には進行中のHTTPリクエストを取り消せませんが、その結果は破棄します。比較時は同じrosbag区間を各モードで再生して、結果の正しさと時間を見てください。終了時の画像が古い場合、その結果を走行判断に利用しないでください。

既定の画像トピックは`/zed/zed_node/rgb/color/rect/image`です。`server:=...`、`image_topic:=...`で変更できます。ノードのROSパラメータには`max_edge_one`（768）、`max_edge_three`（384）、`jpeg_quality`（80）、`timeout`（30秒）、`max_image_age`（2秒）があります。両モードで地面の画素密度がほぼ揃うように画像幅を設定しています。
