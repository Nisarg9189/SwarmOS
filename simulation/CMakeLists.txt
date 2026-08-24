cmake_minimum_required(VERSION 3.16)
project(simulation)

find_package(ament_cmake REQUIRED)

# Install launch files
install(DIRECTORY launch/
  DESTINATION share/${PROJECT_NAME}/launch)

# Install world and config files
install(FILES warehouse.world warehouse_map.yaml warehouse_map.pgm nav2_params.yaml odom_to_tf.py
  DESTINATION share/${PROJECT_NAME})

ament_package()
