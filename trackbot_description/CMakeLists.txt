cmake_minimum_required(VERSION 3.8)
project(trackbot_description)

find_package(ament_cmake REQUIRED)

install(
  DIRECTORY config meshes third_party urdf
  DESTINATION share/${PROJECT_NAME}
)

ament_package()
