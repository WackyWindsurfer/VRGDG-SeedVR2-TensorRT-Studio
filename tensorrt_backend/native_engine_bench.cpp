#include <NvInferRuntime.h>
#include <cuda_runtime_api.h>
#include <fstream>
#include <iostream>
#include <memory>
#include <vector>

class Logger final : public nvinfer1::ILogger {
 public:
  void log(Severity severity, const char* message) noexcept override {
    if (severity <= Severity::kWARNING) std::cerr << message << "\n";
  }
};

int main(int argc, char** argv) {
  if (argc != 2) return 2;
  std::ifstream file(argv[1], std::ios::binary | std::ios::ate);
  if (!file) return 3;
  const size_t size = static_cast<size_t>(file.tellg()); file.seekg(0);
  std::vector<char> blob(size); file.read(blob.data(), static_cast<std::streamsize>(size));
  Logger logger;
  auto runtime = std::unique_ptr<nvinfer1::IRuntime>(nvinfer1::createInferRuntime(logger));
  auto engine = std::unique_ptr<nvinfer1::ICudaEngine>(runtime->deserializeCudaEngine(blob.data(), blob.size()));
  if (!engine) return 4;
  auto context = std::unique_ptr<nvinfer1::IExecutionContext>(engine->createExecutionContext());
  if (!context || engine->getNbIOTensors() != 2) return 5;
  void* input = nullptr; void* output = nullptr; size_t input_bytes = 0, output_bytes = 0;
  const char* input_name = nullptr; const char* output_name = nullptr;
  for (int i = 0; i < engine->getNbIOTensors(); ++i) {
    const char* name = engine->getIOTensorName(i); auto shape = engine->getTensorShape(name);
    size_t elements = 1; for (int d = 0; d < shape.nbDims; ++d) elements *= static_cast<size_t>(shape.d[d]);
    const size_t bytes = elements * sizeof(uint16_t);
    if (engine->getTensorIOMode(name) == nvinfer1::TensorIOMode::kINPUT) { input_name = name; input_bytes = bytes; }
    else { output_name = name; output_bytes = bytes; }
  }
  if (cudaMalloc(&input, input_bytes) != cudaSuccess || cudaMalloc(&output, output_bytes) != cudaSuccess) return 6;
  context->setTensorAddress(input_name, input); context->setTensorAddress(output_name, output);
  cudaStream_t stream{}; cudaStreamCreate(&stream); cudaEvent_t start{}, stop{};
  cudaEventCreate(&start); cudaEventCreate(&stop);
  for (int i = 0; i < 3; ++i) context->enqueueV3(stream); cudaStreamSynchronize(stream);
  cudaEventRecord(start, stream); for (int i = 0; i < 10; ++i) context->enqueueV3(stream);
  cudaEventRecord(stop, stream); cudaEventSynchronize(stop); float ms = 0.0f; cudaEventElapsedTime(&ms, start, stop);
  std::cout << "Native TensorRT-RTX: " << ms / 10.0f << " ms\n";
  cudaEventDestroy(start); cudaEventDestroy(stop); cudaStreamDestroy(stream); cudaFree(input); cudaFree(output);
  return 0;
}
