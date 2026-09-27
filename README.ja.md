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
| `launch/mapping.launch.py` | 機体＋SLAM、手動走行 |
| `launch/localization.launch.py` | 内部部品：map_server＋emcl2 |
| `config/nav2_params.yaml` | Nav2、costmap、collision monitor |
| `config/slam_toolbox.yaml` | 地図作成 |
| `config/emcl2.yaml` | 保存地図上での自己位置推定 |
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
