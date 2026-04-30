cmake_minimum_required(VERSION 3.16)
project(competitive_programming)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Auto-discover all solution.cpp files across platform/problem folders.
# Each becomes its own executable target named "<platform>_<problem>".
# NOTE: Re-run CMake (Tools > CMake > Reload CMake Project in CLion) after adding new problems.
file(GLOB_RECURSE SOLUTION_FILES "*/solution.cpp")

foreach(SOLUTION_FILE ${SOLUTION_FILES})
    get_filename_component(PROBLEM_DIR "${SOLUTION_FILE}" DIRECTORY)
    get_filename_component(PROBLEM_NAME "${PROBLEM_DIR}" NAME)
    get_filename_component(PLATFORM_DIR "${PROBLEM_DIR}" DIRECTORY)
    get_filename_component(PLATFORM_NAME "${PLATFORM_DIR}" NAME)
    set(TARGET_NAME "${PLATFORM_NAME}_${PROBLEM_NAME}")
    add_executable("${TARGET_NAME}" "${SOLUTION_FILE}")
    target_compile_options("${TARGET_NAME}" PRIVATE -Wall -Wextra)
endforeach()
