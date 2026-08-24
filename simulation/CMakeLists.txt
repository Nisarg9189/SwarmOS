cmake_minimum_required(VERSION 3.8)
project(simulation)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

find_package(ament_cmake REQUIRED)

# Install world and config files
install(
  FILES
  warehouse.world
  warehouse.launch.py
  nav2_params.yaml
  warehouse_map.yaml
  warehouse_map.pgm
  DESTINATION share/${PROJECT_NAME}
)

ament_package()
