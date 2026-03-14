from vllm import LLM, SamplingParams

class VLLM:

    _instances = {}
    def __new__(cls, llm_model, model_name):
        key = (llm_model, model_name)

        if key not in cls._instances:
            instance = super().__new__(cls)
            cls._instances[key] = instance
        return cls._instances[key]

    def __init__(self, llm_model, model_name):
        
        if hasattr(self, "_initialized"):
            return
        self._initialized = True

        conf_for_llm = conf.VLLM_CONF[llm_model][model_name]

        llm_kwargs = {
            'model': conf_for_llm['model'],
            'tensor_parallel_size': conf_for_llm['tensor_parallel_size'],
            'dtype': conf_for_llm['dtype'],
            'gpu_memory_utilization': conf_for_llm['gpu_memory_utilization'],
        }

        if 'max_model_len' in conf_for_llm:
            llm_kwargs['max_model_len'] = conf_for_llm['max_model_len']
        if 'enforce_eager' in conf_for_llm:
            llm_kwargs['enforce_eager'] = conf_for_llm['enforce_eager']

        sampling_kwargs = {
            'temperature': conf_for_llm['params']['temperature'],
            'top_p': conf_for_llm['params']['top_p'],
            'max_tokens': conf_for_llm['params']['max_tokens'],
            'stop': ["</Difficulty Level>"],
        }

        if 'top_k' in conf_for_llm['params']:
            sampling_kwargs['top_k'] = conf_for_llm['params']['top_k']

        self.llm = LLM(**llm_kwargs)
        self.params = SamplingParams(**sampling_kwargs)



               
                
