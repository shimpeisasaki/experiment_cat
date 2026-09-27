cmake_minimum_required(VERSION 3.8)
project(experiment_cat)

find_package(ament_cmake REQUIRED)

install(DIRECTORY config launch rviz examples
  DESTINATION share/${PROJECT_NAME}
)

install(PROGRAMS scripts/navigation_guard scripts/waypoint_route DESTINATION lib/${PROJECT_NAME})
ament_package()
