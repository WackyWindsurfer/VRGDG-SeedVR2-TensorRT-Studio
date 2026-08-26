#include <NvInferRuntime.h>

#include <iostream>

int main()
{
    std::cout << "TensorRT-RTX runtime version: " << getInferLibVersion() << "\n";
    std::cout << "TensorRT-RTX build version: " << getInferLibBuildVersion() << "\n";
    return 0;
}
