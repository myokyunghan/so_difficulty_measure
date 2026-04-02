vllm_setting = {
                'vl' :  {
                        'models--kosbu--Llama-3.3-70B-Instruct-AWQ': {
                                                'model'                 : '/mnt/hdd/mghan/hf_model/models--kosbu--Llama-3.3-70B-Instruct-AWQ/snapshots/ee59475f940b222132f7445947375973f3820483',
                                                'tensor_parallel_size'  : 4,
                                                'dtype'                 : "auto",
                                                'gpu_memory_utilization': 0.5,
                                                # 'max_model_len'         : 16384,
                                                'max_model_len'         : 16384,
                                                'enforce_eager'         : True,
                                                'params'                : {
                                                                            'temperature'   : 0.01,
                                                                            'top_p'         : 0.9,
                                                                            'max_tokens'    : 10 
                                                                        }
                                            },
                        'Llama-3.2-3B-Instruct': {
                                    'model'                 : '/mnt/hdd/mghan/hf_model/Llama-3.2-3B-Instruct',
                                    'tensor_parallel_size'  : 4,
                                    'dtype'                 : "auto",
                                    'gpu_memory_utilization': 0.6,
                                    'params'                : {
                                                                'temperature'   : 0.01,
                                                                'top_p'         : 0.9,
                                                                'max_tokens'    : 10 
                                                            }
                                },
                },
  
                'vq' : {
                # 'model'                 : '/usr/share/d_ollama/.ollama/models/hf_model/models--Qwen--Qwen3-4B-Thinking-2507/snapshots/768f209d9ea81521153ed38c47d515654e938aea',
                # 'model'                 : '/usr/share/d_ollama/.ollama/models/hf_model/models--Qwen--Qwen3-4B-Instruct-2507/snapshots/cdbee75f17c01a7cc42f958dc650907174af0554',
                # 'model'                 : '/usr/share/d_ollama/.ollama/models/hf_model/models--Qwen--Qwen3-14B-AWQ/snapshots/31c69efc29464b6bb0aee1398b5a7b50a99340c3', # 말이많음 
                # 'model'                 : '/usr/share/d_ollama/.ollama/models/hf_model/models--cyankiwi--Qwen3-30B-A3B-Instruct-2507-AWQ-4bit/snapshots/2d3819dc1b75631b5255c25d2ff4d4824324d199', # 못돌림
                        'models--cyankiwi--Qwen3-30B-A3B-Instruct-2507-AWQ-4bit': {
            
                            'model'                 : '/mnt/hdd/mghan/hf_model/models--cyankiwi--Qwen3-30B-A3B-Instruct-2507-AWQ-4bit/snapshots/2d3819dc1b75631b5255c25d2ff4d4824324d199',
                            # 'tensor_parallel_size'  : 4,
                            'tensor_parallel_size'  : 2,
                            'dtype'                 : "auto",
                            # 'max_model_len'         : 16384,
                            # 'max_model_len'         : 27000,
                            'max_model_len'           : None,
                            # 'gpu_memory_utilization': 0.5,
                            'gpu_memory_utilization': 0.9,
                            'params'                : {
                                                        'temperature'   : 0.01,
                                                        'top_p'         : 0.9,
                                                        'max_tokens'    : 10
                                                    }
                        }

                }
} 

ollama_setting = {'version' : 'llama-3.1-70b-instruct-lorablated.Q4_K_M:latest'}