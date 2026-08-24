cmake_minimum_required(VERSION 3.8)
project(simulation)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

find_package(ament_cmake REQUIRED)
find_package(gazebo_ros REQUIRED)

# Install world and config files
install(
  DIRECTORY
  worlds/
  DESTINATION share/${PROJECT_NAME}/worlds
)

install(
  FILES
  warehouse.world
  DESTINATION share/${PROJECT_NAME}
)

install(
  FILES
  nav2_params.yaml
  warehouse.launch.py
  DESTINATION share/${PROJECT_NAME}/launch
)

ament_package()
