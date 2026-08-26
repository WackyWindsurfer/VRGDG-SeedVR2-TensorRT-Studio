#include <NvInferRuntime.h>
#include <cuda_runtime_api.h>
#include <fstream>
#include <iostream>
#include <memory>
#include <vector>

class Logger final : public nvinfer1::ILogger {
 public: void log(Severity s, const char* m) noexcept override { if (s <= Severity::kWARNING) std::cerr << m << "\n"; }
};

struct Engine {
  std::unique_ptr<nvinfer1::ICudaEngine> engine;
  std::unique_ptr<nvinfer1::IExecutionContext> context;
  const char* input = nullptr; const char* output = nullptr;
  size_t input_bytes = 0, output_bytes = 0;
};

static Engine load(nvinfer1::IRuntime* runtime, const char* path) {
  std::ifstream f(path, std::ios::binary | std::ios::ate); if (!f) throw std::runtime_error(path);
  size_t n = static_cast<size_t>(f.tellg()); f.seekg(0); std::vector<char> b(n); f.read(b.data(), static_cast<std::streamsize>(n));
  Engine e; e.engine.reset(runtime->deserializeCudaEngine(b.data(), b.size())); if (!e.engine) throw std::runtime_error("deserialize");
  e.context.reset(e.engine->createExecutionContext());
  for (int i = 0; i < e.engine->getNbIOTensors(); ++i) { const char* name=e.engine->getIOTensorName(i); auto s=e.engine->getTensorShape(name); size_t el=1; for(int d=0;d<s.nbDims;++d) el*=static_cast<size_t>(s.d[d]); size_t bytes=el*2; if(e.engine->getTensorIOMode(name)==nvinfer1::TensorIOMode::kINPUT){e.input=name;e.input_bytes=bytes;}else{e.output=name;e.output_bytes=bytes;} }
  return e;
}

int main(int argc, char** argv) {
  if (argc != 3) return 2; Logger logger; auto runtime=std::unique_ptr<nvinfer1::IRuntime>(nvinfer1::createInferRuntime(logger));
  try {
    auto a=load(runtime.get(),argv[1]); auto b=load(runtime.get(),argv[2]); void* in=nullptr; void* mid=nullptr; void* out=nullptr;
    if(cudaMalloc(&in,a.input_bytes)!=cudaSuccess||cudaMalloc(&mid,a.output_bytes)!=cudaSuccess||cudaMalloc(&out,b.output_bytes)!=cudaSuccess)return 3;
    a.context->setTensorAddress(a.input,in); a.context->setTensorAddress(a.output,mid); b.context->setTensorAddress(b.input,mid); b.context->setTensorAddress(b.output,out);
    cudaStream_t stream{}; cudaStreamCreate(&stream); cudaEvent_t st{},en{}; cudaEventCreate(&st);cudaEventCreate(&en);
    for(int i=0;i<3;++i){a.context->enqueueV3(stream);b.context->enqueueV3(stream);} cudaStreamSynchronize(stream); cudaEventRecord(st,stream);
    for(int i=0;i<10;++i){a.context->enqueueV3(stream);b.context->enqueueV3(stream);} cudaEventRecord(en,stream);cudaEventSynchronize(en);float ms=0;cudaEventElapsedTime(&ms,st,en);
    std::cout<<"Native block2->block3 chain: "<<ms/10.0f<<" ms\n";cudaEventDestroy(st);cudaEventDestroy(en);cudaStreamDestroy(stream);cudaFree(in);cudaFree(mid);cudaFree(out);
  } catch (...) { return 4; } return 0;
}
