# CATロボット ナビゲーション運用マニュアル

`experiment_cat` はNav2、SLAM、emcl2による自己位置推定、地図、waypoint巡回を管理する。機体、センサ、手動操作、安全停止は [cat_robot](https://github.com/shimpeisasaki/cat_robot) が管理する。`navigation.launch.py` と `mapping.launch.py` は機体も起動するため、`cat_bringup` を別途起動しない。

## 導入とビルド

ROS 2 Humbleを使用する。リポジトリの取得、依存ソースの導入、デバイス設定は [cat_robotの導入手順](https://github.com/shimpeisasaki/cat_robot) を参照する。`experiment_cat/dependencies.repos` に定義されたemcl2も同じワークスペースの `src/` に配置する。

```bash
cd ~/ros2_ws
source /opt/ros/humble/setup.bash
colcon build --symlink-install --packages-up-to experiment_cat
source install/setup.bash
```

新しい端末ではROS 2とワークスペースの `setup.bash` を再度読み込む。地図YAML、対応する画像、waypoint YAMLは `map/` 内で一緒に管理し、別PCへ展開するときも同じリポジトリの変更として共有する。`map/` に新しい地図を追加した後はビルドを実施し、パッケージ共有ディレクトリへ反映する。

## RGB-Dパノラマ撮影

`cat_panorama` を同じワークスペースの `src/` に配置して上記のビルドを行い、以下を1回起動する。
機体bringup、ZED Mini、ジョイスティックもこのlaunchが起動する。

```bash
ros2 launch experiment_cat panorama.launch.py
```

Aを一度離してから押すと、走行許可とRGB-D/TFの準備を待ち、30度ごとに停止・撮影しながら反時計回りに1周する。撮影枚数は0度から330度の12枚。360度に戻って終了する。
終了後はブレーキをかけ、`~/ros2_ws/data/panorama/<日時>_<ID>/` にRGB・距離・有効画素マスク・撮影フレームを保存する。
各撮影後、ブレーキと2秒以上の停止確認を経て走行許可を取り直す。`/base/drive_enabled` がドライバの実際の走行可能状態を示し、trueを確認してから次の旋回を開始する。ドライバ側の許可が失われた場合は撮影を中止する。
パノラマの位置・旋回角・画像時刻TFは既定で車輪＋IMUのオドメトリを使用する。静止中のZED VIOの位置ずれで撮影を中止しないための設定。`odom_source:=vio` でVIOへ戻せる。車輪の空転は姿勢誤差になるため、実際の撮影は床に接地した状態で行う。撮影中にAを押し直しても走行許可を解除しない。
保存成功は `/panorama_rotate/status` の `done`、または保存先の `metadata.json` の `state: complete` で確認する。
Bで中止・停止。完了後に再度Aを押すと、新しいフォルダへ次の撮影を行う。

```bash
ros2 topic echo /panorama_rotate/status --qos-durability transient_local
```

距離は撮影開始位置の共通視点からのメートル値で、`depth_m.npy` にfloat32で保存する。無効画素はNaN。
上下の未観測領域は無効のまま残す。詳細と投影規則は `cat_panorama/README.md` を参照。
画質・深度設定は `config/zed_panorama.yaml`、保存先は `output_dir:=...`、旋回速度の上限は `angular_speed:=0.18` で指定できる。24ステップの実機撮影が成功した速度上限を使用する。`minimum_angular_speed` の既定値は0とする。旋回タイムアウト時は指令、安全制御後の指令、車輪と選択したオドメトリの角速度を表示する。

## 保存地図を使ったナビゲーション

```bash
ros2 launch experiment_cat navigation.launch.py
```

通常起動、マッピング、FlowNavのROSノードは既定で警告・エラーのみを表示する。調査時は `log_level:=info` を付けるとINFOログを表示できる。例: `ros2 launch experiment_cat navigation.launch.py log_level:=info`。ZEDだけを詳しく見る場合は `zed_log_level:=info` を指定する。安全停止の状態は `/base_safety/status`、waypointの状態は `/waypoint_route/status` でも確認できる。

既定では `slam:=false` とし、以下のファイルをパッケージ内の `map/` から読み込む。

| 用途 | 既定ファイル | ROSトピック |
|---|---|---|
| emcl2の自己位置推定 | `map/19F_260928.yaml` と同名のPGM | `/localization/map` |
| Nav2の計画・costmap | `map/19F_260928_Nav.yaml` と同名のPGM | `/map` |
| 巡回ルート | `map/19F_waypoint.yaml` | `/waypoint_route/markers` |

地図を変更する場合は `map:=/path/localization.yaml`、`navigation_map:=/path/navigation.yaml`、`waypoints_file:=/path/route.yaml` を指定する。`localization_map` は `map` の別名である。両地図とwaypointは同じ `map` 座標系、解像度、原点に揃える。地図YAMLの `image` には対応する画像ファイルを指定する。

保存地図での起動後、RVizの「2D Pose Estimate」で実際の機体位置と向きを設定する。`/navigation/ready`、`/base_safety/status` とRViz表示を確認し、機体が停止している状態を2秒以上維持してから走行を許可する。

```bash
ros2 service call /base_safety/arm std_srvs/srv/Trigger '{}'
```

`arm` は走行許可のみを行う。Nav2のゴール送信やwaypoint巡回の開始は別操作である。停止にはジョイスティックのBボタンまたは `/base_safety/brake` を使用する。

```bash
ros2 service call /base_safety/brake std_srvs/srv/Trigger '{}'
```

## waypoint巡回

ナビゲーション起動時にYAMLを読み込み、RVizの「Loaded waypoint route」に番号と向きを表示する。読込だけでは走行を開始しない。走行を許可した後、次の順序で開始する。

```bash
ros2 service call /base_safety/arm std_srvs/srv/Trigger '{}'
ros2 service call /waypoint_route/start std_srvs/srv/Trigger '{}'
```

既に走行許可済みの場合、`arm` の再実行は不要である。`/waypoint_route/start` の応答を確認する。状態と進捗は次で表示する。

```bash
ros2 topic echo /waypoint_route/status --qos-durability transient_local
```

巡回の取り消しと機体の停止は、それぞれ次の操作で行う。

```bash
ros2 service call /waypoint_route/cancel std_srvs/srv/Trigger '{}'
ros2 service call /base_safety/brake std_srvs/srv/Trigger '{}'
```

YAMLの形式は次のとおりである。`x` と `y` の単位はm、`yaw` はradとし、配列順に巡回する。ファイルを書き換えた場合はナビゲーションを再起動して読み込み直す。

```yaml
frame_id: map
waypoints:
  - {x: 0.0, y: 0.0, yaw: 0.0}
  - {x: 1.0, y: 0.0, yaw: 1.5708}
```

waypointを使用しない場合は `waypoints_file:=` を空にする。

## ロボットを使わないwaypoint編集

```bash
ros2 launch experiment_cat waypoint_editor.launch.py
```

既定ではナビゲーション用地図と `map/19F_waypoint.yaml` を開く。既存の地点も読み込まれる。RVizの「2D Goal Pose」で地点を順番に指定し、ドラッグ方向で向きを設定する。操作用サービスは別端末で呼び出す。

```bash
ros2 service call /waypoint_editor/undo std_srvs/srv/Trigger '{}'
ros2 service call /waypoint_editor/clear std_srvs/srv/Trigger '{}'
ros2 service call /waypoint_editor/save std_srvs/srv/Trigger '{}'
```

`undo` は最後の地点を取り消し、`clear` は編集中のリストを消去する。ファイルへの反映は `save` 実行時のみである。保存時は同名YAMLを上書きする。別ファイルを編集する場合は `map:=... input:=... output:=...` を指定する。`input:=` を空にすると空のリストから開始する。

## SLAMと地図の保存

手動操作で地図を作る場合は次を起動する。

```bash
ros2 launch experiment_cat mapping.launch.py
```

地図の保存は、ワークスペースを読み込んだ別端末で実行する。

```bash
cd ~/ros2_ws
ros2 run nav2_map_server map_saver_cli -f src/experiment_cat/map/new_map
```

この操作で `new_map.yaml` と地図画像が `src/experiment_cat/map/` に作成される。新しい地図をlaunchの既定値にする場合は、地図YAMLの `image`、launchのファイル名、地図間の座標を確認してからパッケージを再ビルドする。

SLAMしながらNav2を使用する場合は次を起動する。`navigation_map:=` を空にするとNav2もライブSLAM地図を使用する。既定の保存済みNav2地図を併用する場合は、SLAM地図と同じ座標であることを確認する。

```bash
ros2 launch experiment_cat navigation.launch.py slam:=true navigation_map:= waypoints_file:=
```

## 設定と障害時の確認

| ファイル | 主な設定 |
|---|---|
| `config/nav2_params.yaml` | Nav2、local/global costmap、衝突監視 |
| `config/slam_toolbox.yaml` | SLAMのスキャン処理と地図更新 |
| `config/emcl2.yaml` | 保存地図上の自己位置推定 |
| `map/` | 地図YAML・画像、waypoint YAML |

costmapのLiDAR障害物高さ上限はlocal/globalともに0.8 m、スキャン更新監視は0.2秒に設定している。`navigation_guard` は `/scan`、`/odom`、TF、衝突監視を確認し、結果を `/navigation/ready` に配信する。異常時は `base_safety` が停止し、ゴールを取り消す。復旧後の自動再許可は行わない。

| 状態 | 確認箇所 |
|---|---|
| 地図が表示されない | 地図YAMLの `image` と画像ファイル、`map/` のインストール状態 |
| RVizが起動しない | `navigation_rviz` 引数、起動ログ、画面表示環境 |
| 巡回が始まらない | `/waypoint_route/start` の応答、`/waypoint_route/status`、`/base_safety/status` |
| `/scan` の更新警告 | LiDARの接続、`/scan_raw` と `/scan` の配信状態 |
| 走行許可が解除される | `/navigation/ready`、`/base_safety/status`、モーター診断 |

機体側の通信と停止制御は [cat_robotのREADME](https://github.com/shimpeisasaki/cat_robot) を参照する。

## ライセンス

本リポジトリは [Apache License, Version 2.0](LICENSE)（SPDX識別子: `Apache-2.0`）で提供する。外部依存パッケージには、それぞれのライセンスが適用される。
