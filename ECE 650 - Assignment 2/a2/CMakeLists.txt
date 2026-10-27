cmake_minimum_required(VERSION 3.5...3.10)
project(ece650-a2)

## ECE650 Specific configuration start here
## Project specific configurations go here

# enable c++11 support
set (CMAKE_CXX_FLAGS "-std=c++11 -Wall ${CMAKE_CXX_FLAGS}")

option(WITH_ASAN "Enabled AddressSanitizer to detect memory faults" OFF)
if(WITH_ASAN)
  set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -fsanitize=address,undefined" )
endif()

# the program itself
add_executable(ece650-a2 ece650-a2.cpp)

# doctest unit tests (test.cpp pulls in ece650-a2.cpp without its main)
add_executable(tests test.cpp)
