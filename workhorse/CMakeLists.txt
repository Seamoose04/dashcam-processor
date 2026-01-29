cmake_minimum_required(VERSION 3.16)
set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

# Sources
file(GLOB_RECURSE WORKHORSE_SOURCES CONFIGURE_DEPENDS
	src/*.cpp
	src/*.h
)

# Workhorse library
add_executable(Workhorse ${WORKHORSE_SOURCES})

# Include
target_include_directories(Workhorse PUBLIC
	${CMAKE_CURRENT_SOURCE_DIR}/src
)
