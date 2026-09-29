# experiment_cat

Nav2・SLAM・emcl2だけを担当します。機体、全センサ、URDF、停止制御はcat_robotの `cat_bringup` を利用します。

## ビルド

```bash
cd ~/ros2_ws
source /opt/ros/humble/setup.bash
colcon build --packages-select ddsm115_controller cat_bringup experiment_cat --symlink-install
source install/setup.bash
```

依存するemcl2は `dependencies.repos`、機体側の依存はcat_robotの `dependencies.repos` を参照してください。

## 起動

保存地図でのナビゲーション：

```bash
ros2 launch experiment_cat navigation.launch.py \
  slam:=false map:=/home/uedalab/ros2_ws/map/indoor_loop_map_vio.yaml
```

SLAMしながらナビゲーション：

```bash
ros2 launch experiment_cat navigation.launch.py slam:=true
```

手動操作で地図作成：

```bash
ros2 launch experiment_cat mapping.launch.py
ros2 run nav2_map_server map_saver_cli -f ~/ros2_ws/map/new_map
```

各入口がcat_bringupを起動するので、別途機体を二重起動しないでください。既定はZED VIO。車輪/IMU推定は `odom_source:=wheel`、GNSSも配信するなら `use_gnss:=true`。機体側の設定は[cat_robot](../cat_robot/README.md)を参照してください。

起動時は停止状態です。保存地図ではRVizの「2D Pose Estimate」で初期位置を設定します。センサ・自己位置推定が正常で停止した状態を2秒確認してから、Aボタンまたは次のサービスで走行を許可します。

```bash
ros2 service call /base_safety/arm std_srvs/srv/Trigger '{}'
```

Xは手動、Bは停止、Yは停止確認後フリー。ナビ以外へ切り替えた際はNav2のゴールをキャンセルします。故障から自動的には再許可しません。

## 構成

| ファイル | 担当 |
|---|---|
| `launch/navigation.launch.py` | 機体＋Nav2＋SLAMまたはemcl2 |
| `launch/waypoint_editor.launch.py` | ロボット不要の地図表示・waypoint編集 |
| `launch/mapping.launch.py` | 機体＋SLAM、手動走行 |
| `launch/localization.launch.py` | 内部部品：map_server＋emcl2 |
| `config/nav2_params.yaml` | Nav2、costmap、collision monitor |
| `config/slam_toolbox.yaml` | 地図作成 |
| `config/emcl2.yaml` | 保存地図上での自己位置推定 |
| `scripts/waypoint_editor` | 地点の追加・取消・YAML保存 |
| `scripts/waypoint_route` | 保存済みルートの表示・巡回 |
| `scripts/waypoint_io.py` | 共通のYAML形式・マーカー生成 |
| `scripts/navigation_guard` | scan・odom・TF・collision monitorの監視とゴール取消 |
| `rviz/navigation.rviz` | ナビゲーション表示 |

機体TFは `odom → base_link → laser`、SLAM/emcl2が `map → odom` を担当します。

```text
Nav2 → velocity_smoother → collision_monitor → /cmd_vel_external
                                                   ↓
手動操作 → 手動smoother → /cmd_vel_teleop → base_safety → /cmd_vel_safe → base_driver
```

`navigation_guard`は `/navigation/ready` を周期配信します。cat_bringupのbase_safetyは、自律走行中にこの許可が途切れた場合も停止します。機体の通信・実測停止判定はcat_robot内で行います。

## 障害物設定

local/global両方の `obstacle_layer.scan.max_obstacle_height` は `0.8 m`。Humbleではscan側が未指定だと0 mになり、高さ0.192 mのLiDAR点が除外されます。設定は必ず `scan:` 直下に置きます。DWB・inflationの調整値は今回の構成整理で変更していません。

## 移行

旧experiment_catの機体用launch、URDF、重複スクリプト、校正・記録専用launch、costmap表示デバッグは削除しました。保守GUIは `ros2 launch ddsm115_controller motor_test_gui.launch.py` で利用できます。停止・許可サービスは `/navigation_safety/*` から `/base_safety/*` に移動しました。

旧installに削除済みファイルが残る場合は対象パッケージのbuild/installを作り直してください。保存地図・bagはリポジトリ外で管理します。

## 自己位置推定とナビゲーションの地図を分ける

元の地図を自己位置推定に使い、通行禁止領域などを書き込んだコピーをNav2に使えます。

```bash
ros2 launch experiment_cat navigation.launch.py
```

- 既定の `map`: `/home/uedalab/ros2_ws/map/19F_260928.yaml`。自己位置推定用の元地図を`/localization/map`として配信。
- 既定の `navigation_map`: `/home/uedalab/ros2_ws/map/19F_260928_Nav_2.yaml`。編集済み画像`19F_260928_Nav_2.pgm`を`/map`として配信し、local/global両costmapが参照。
- `slam`の既定値は`false`。通常は引数なしでこの2枚の保存地図を使います。SLAMを行う場合は`slam:=true`を指定してください。
- 両地図・waypointは同じ`map`座標系で整合させます。Nav2地図YAMLは画像`19F_260928_Nav_2.pgm`を参照し、解像度・原点は元地図と揃えています。

RVizは既定でナビ用地図を表示します。比較する場合は「Localization map」を有効にします。
`slam:=true`を指定するとライブSLAMを開始し、SLAMの地図は`/localization/map`に配信されます。既定のNav2地図は保存済みの編集地図です。SLAM中の地図をNav2にも使う場合は`navigation_map:=`を空にしてください。

## waypointリスト

既定では `/home/uedalab/ros2_ws/map/19F_waypoint.yaml` を読み込みます。別のYAMLに切り替える場合は `waypoints_file:=/絶対パス/route.yaml` を指定してください。

```yaml
frame_id: map
waypoints:
  - {x: 0.0, y: 0.0, yaw: 0.0}
  - {x: 1.0, y: 0.0, yaw: 1.5707963267948966}
```

x/yはメートル、yawはラジアン（省略時0）。配列順に巡回します。

```bash
ros2 launch experiment_cat navigation.launch.py
```

読込時はRVizの「Loaded waypoint route」に番号・向きだけを表示し、走行は開始しません。自己位置を設定し走行を許可してから開始します。

```bash
ros2 service call /base_safety/arm std_srvs/srv/Trigger '{}'
ros2 service call /waypoint_route/start std_srvs/srv/Trigger '{}'
ros2 service call /waypoint_route/cancel std_srvs/srv/Trigger '{}'
```

進捗・完了・未到達点は `/waypoint_route/status`。再度startすると先頭から巡回します。Nav2が未準備、走行未許可、既に巡回中の場合は開始を拒否します。Bボタン・`/base_safety/brake`は従来どおり停止とゴール取消を行います。巡回はNav2のFollowWaypointsを使うため、待機時間・到達失敗時の継続は `nav2_params.yaml` の `waypoint_follower` 設定に従います。

## ロボットなしでwaypointを作成・保存

専用エディタは既定でナビ用地図`19F_260928_Nav_2.yaml`とwaypointファイル`19F_waypoint.yaml`を使います。既存の6地点を読み込むので、地点を追加・編集して保存できます。機体・自己位置推定・Nav2の走行サーバーは起動しません。地図・入出力先を変える場合だけlaunch引数を指定します。

```bash
ros2 launch experiment_cat waypoint_editor.launch.py
```

1. RVizの「2D Goal Pose」を選び、地図上でドラッグして地点と向きを指定します。
2. 地点ごとに同じ操作を繰り返します。配置した順に番号付き矢印が表示されます。
3. 別端末（ワークスペースをsource済み）で保存します。

```bash
ros2 service call /waypoint_editor/save std_srvs/srv/Trigger '{}'
```

成功時は保存した地点数と絶対パスが返ります。`x, y, yaw`のYAMLとして保存し、同名ファイルは上書きします。空のリストは保存できません。終了時の自動保存はありません。

最後の地点の取消・全消去：

```bash
ros2 service call /waypoint_editor/undo std_srvs/srv/Trigger '{}'
ros2 service call /waypoint_editor/clear std_srvs/srv/Trigger '{}'
```

取消・全消去だけでは保存済みファイルは変わりません。既定では既存ルートを読み込んで同じファイルに保存します。保存したwaypointは引数なしのナビゲーション起動で読み込まれます。ナビゲーション側の`waypoints_output`と`/waypoint_route/save`は廃止しました。

エディタの地図・入力・表示は `/waypoint_editor/*` にまとめています。ナビゲーションに使用する地図と同じ座標系の地図を指定してください。
