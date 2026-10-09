cmake_minimum_required(VERSION 3.8)
project(experiment_cat)

find_package(ament_cmake REQUIRED)

install(DIRECTORY config launch rviz map
  DESTINATION share/${PROJECT_NAME}
)
install(FILES FLOWNAV.md DESTINATION share/${PROJECT_NAME})

install(PROGRAMS scripts/navigation_guard scripts/waypoint_route scripts/waypoint_editor scripts/flownav_follow_path scripts/panorama_rotate DESTINATION lib/${PROJECT_NAME})
install(FILES scripts/waypoint_io.py DESTINATION lib/${PROJECT_NAME})
if(BUILD_TESTING)
  find_package(ament_cmake_pytest REQUIRED)
  ament_add_pytest_test(panorama_rotation test/test_panorama_rotation.py
    APPEND_ENV PYTHONNOUSERSITE=1)
  ament_add_pytest_test(panorama_integration test/test_panorama_integration.py
    TIMEOUT 120 APPEND_ENV PYTHONNOUSERSITE=1)
endif()
ament_package()
