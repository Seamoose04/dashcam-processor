cmake_minimum_required(VERSION 3.16)
set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

# Sources
file(GLOB_RECURSE ENGINE_SOURCES CONFIGURE_DEPENDS
	src/*.cpp
	src/*.h
)

# Add the 'include' directory recursively to the include paths for the target
target_include_directories(Workhorse PRIVATE
    "${CMAKE_CURRENT_SOURCE_DIR}/"
)

add_executable(Workhorse ${SOURCE_FILES})
