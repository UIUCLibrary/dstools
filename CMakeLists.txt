cmake_minimum_required(VERSION 3.12)
project(Speedwagon
        LANGUAGES NONE
        )

include(FetchContent)
find_package(PythonInterp REQUIRED)

message(STATUS "Using Python ${PYTHON_VERSION_STRING} located at \"${PYTHON_EXECUTABLE}\".")
option(SPEEDWAGON_CACHE_PYTHON_WHEEL_DEPENDENCIES "Cache python whl dependencies to a folder for reuse" ON)
option(SPEEDWAGON_SYNC_PYTHON_BUILD_VENV "SYNC installed python packages in build virtual environment" ON)
option(SPEEDWAGON_TESTCI "For testing ci builds" OFF)


set(SPEEDWAGON_PYTHON_DEPENDENCY_CACHE ${CMAKE_CURRENT_BINARY_DIR}/_deps/python_wheels CACHE PATH "location to put Python deps")
set(SPEEDWAGON_VENV_PATH ${CMAKE_CURRENT_BINARY_DIR}/venv CACHE PATH "Location for Python virtual environment needed for building")
set(SPEEDWAGON_EXTRA_REQUIREMENTS_FILE "" CACHE FILEPATH "Extra requirements file to install to standalone build")
if(WIN32)
    include(cmake/standalone.cmake)
endif()

if(UNIX)
#   This needs the bind the docker socket to work which doesn't work on Windows to
#   my as far as I know
    if(SPEEDWAGON_TESTCI)
        include(cmake/jenkins.cmake)
    endif()
endif()