# Initial local inference experiments

Hardware: Ryzen 7 9700X, RX 9070 XT 16 GB, 32 GB RAM
Runtime: Ollama 0.40.11, ROCm backend

## Qwen3 14B
- Q4_K_M quantization
- Fully GPU-offloaded at 4,096 context
- Approximately 54 tokens/sec on one Python explanation task

## GPT-OSS 20B
- MXFP4 quantization
- Fully GPU-offloaded at context settings through 32,768
- Approximately 102 tokens/sec on one short Python explanation task
- Retrieved three codes and identified one absent record correctly
  in a 26,919-token synthetic prompt
- An earlier, slightly differently worded long-input run returned
  two incorrect codes

## Limitations
- Small sample; results do not establish general model quality
- Different reasoning settings and tokenizers between models
- Repeated prompts may benefit from caching
- Configured context capacity differs from actual input length
