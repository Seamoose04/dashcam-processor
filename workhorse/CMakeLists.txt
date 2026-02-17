cmake_minimum_required(VERSION 3.16)
set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

if(NOT UNIX)
    message(FATAL_ERROR "This project can only be built on a Unix-like system (Linux, macOS, etc.). Windows is not supported.")
endif()

include(FetchContent)

# Packages
find_package(Threads REQUIRED)
find_package(OpenCV	REQUIRED)
find_package(PkgConfig REQUIRED)
find_library(DARKHELP darkhelp)
find_library(DARKNET darknet)

pkg_check_modules(TESSERACT REQUIRED tesseract)

FetchContent_Declare(ftxui
	GIT_REPOSITORY https://github.com/ArthurSonzogni/FTXUI
  	GIT_TAG v6.1.9
)
FetchContent_MakeAvailable(ftxui)

include_directories(${OpenCV_INCLUDE_DIRS})

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
	${TESSERACT_INCLUDE_DIRS}
)

# Libraries
target_link_libraries(Workhorse
	PRIVATE ftxui::screen
	PRIVATE ftxui::dom
	PRIVATE ftxui::component
	Threads::Threads
	${DARKHELP}
	${DARKNET}
	${OpenCV_LIBS}
	${TESSERACT_LIBRARIES}
)