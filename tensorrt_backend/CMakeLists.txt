cmake_minimum_required(VERSION 3.25)
project(seedvr2_tensorrt_native LANGUAGES CXX)

find_package(CUDAToolkit REQUIRED)

if(NOT TENSORRT_RTX_ROOT)
    message(FATAL_ERROR "Pass -DTENSORRT_RTX_ROOT=<TensorRT-RTX SDK directory>")
endif()

set(TRT_INCLUDE "${TENSORRT_RTX_ROOT}/include")
set(TRT_LIB "${TENSORRT_RTX_ROOT}/lib")
set(TRT_BIN "${TENSORRT_RTX_ROOT}/bin")

add_library(tensorrt_rtx SHARED IMPORTED)
set_target_properties(tensorrt_rtx PROPERTIES
    IMPORTED_IMPLIB "${TRT_LIB}/tensorrt_rtx_1_6.lib"
    IMPORTED_LOCATION "${TRT_BIN}/tensorrt_rtx_1_6.dll"
)

add_executable(seedvr2_tensorrt_native native_smoke.cpp)
add_executable(seedvr2_tensorrt_bench native_engine_bench.cpp)
add_executable(seedvr2_tensorrt_chain_bench native_chain_bench.cpp)
target_compile_features(seedvr2_tensorrt_native PRIVATE cxx_std_17)
target_include_directories(seedvr2_tensorrt_native PRIVATE "${TRT_INCLUDE}" ${CUDAToolkit_INCLUDE_DIRS})
target_link_libraries(seedvr2_tensorrt_native PRIVATE tensorrt_rtx CUDA::cudart)
target_compile_features(seedvr2_tensorrt_bench PRIVATE cxx_std_17)
target_include_directories(seedvr2_tensorrt_bench PRIVATE "${TRT_INCLUDE}" ${CUDAToolkit_INCLUDE_DIRS})
target_link_libraries(seedvr2_tensorrt_bench PRIVATE tensorrt_rtx CUDA::cudart)
target_compile_features(seedvr2_tensorrt_chain_bench PRIVATE cxx_std_17)
target_include_directories(seedvr2_tensorrt_chain_bench PRIVATE "${TRT_INCLUDE}" ${CUDAToolkit_INCLUDE_DIRS})
target_link_libraries(seedvr2_tensorrt_chain_bench PRIVATE tensorrt_rtx CUDA::cudart)

add_custom_command(TARGET seedvr2_tensorrt_native POST_BUILD
    COMMAND ${CMAKE_COMMAND} -E copy_if_different
        "${TRT_BIN}/tensorrt_rtx_1_6.dll"
        "$<TARGET_FILE_DIR:seedvr2_tensorrt_native>/tensorrt_rtx_1_6.dll"
)
add_custom_command(TARGET seedvr2_tensorrt_bench POST_BUILD
    COMMAND ${CMAKE_COMMAND} -E copy_if_different
        "${TRT_BIN}/tensorrt_rtx_1_6.dll"
        "$<TARGET_FILE_DIR:seedvr2_tensorrt_bench>/tensorrt_rtx_1_6.dll"
)
add_custom_command(TARGET seedvr2_tensorrt_chain_bench POST_BUILD
    COMMAND ${CMAKE_COMMAND} -E copy_if_different
        "${TRT_BIN}/tensorrt_rtx_1_6.dll"
        "$<TARGET_FILE_DIR:seedvr2_tensorrt_chain_bench>/tensorrt_rtx_1_6.dll"
)
