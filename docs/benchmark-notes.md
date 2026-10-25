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

## Terminal foundation acceptance checks

- 15 offline behavioral tests passed.
- Verified help, status, unknown-command handling, history, clear, and exit.
- Verified turn and character limits.
- Verified service-outage recovery without restarting the client.
- Failed requests were excluded from history.
- Verified selected-model unloading and repeated off commands.

### Structured-output retrieval probes

Model: gpt-oss:20b
Configured context: 32,768 tokens
Placement: 100% GPU

| Records | Seed | Input tokens | Exact checks | Generation tokens/sec | Total seconds |
|---|---|---|---|---|---|
| 600 | 42 | 9,058 | 4/4 | 102.7 | 6.11 |
| 1,800 | 43 | 26,886 | 4/4 | 90.9 | 11.13 |

These are individual synthetic runs, not general accuracy guarantees.
Prompt caching may affect timings. Hardware limits were not established.
