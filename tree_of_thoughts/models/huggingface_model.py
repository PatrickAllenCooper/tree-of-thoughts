from transformers import AutoModelForCausalLM, AutoTokenizer, logging
from transformers import pipeline
import torch
from tree_of_thoughts.models.abstract_language_model import AbstractLanguageModel


class HuggingLanguageModel(AbstractLanguageModel):
    def __init__(self, model_name, model_tokenizer=None, verbose=False):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForCausalLM.from_pretrained(model_name, torch_dtype=torch.float16, device_map="auto").to(self.device)
        self.verbose = verbose
    
    def generate_thoughts(self, state, k, max_length=100):
        state_text = ' '.join(state)
        prompt = f"Write down your observations in format 'Observation:xxxx', then write down your thoughts in format 'Thoughts:xxxx Given the current state of reasoning: '{state_text}', generate a coherent solutions to achieve {state_text}"

        if self.verbose:
            print(f"Generating thoughts for state: {state_text}")

        try:
            thoughts = []
            for i in range(k):
                input_ids = self.tokenizer.encode(prompt, return_tensors="pt").to(self.device)
                output = self.model.generate(input_ids, max_length=5000)
                decoded_output = self.tokenizer.decode(output[0], skip_special_tokens=True)
                thoughts += [decoded_output]
        except Exception as e:
            if self.verbose:
                print(f"Error generating thoughts for state: {state_text}")
                print(f"Error: {e}")
            thoughts = []

        return thoughts
        

    def generate_solution(self, initial_prompt, state, rejected_solutions=None):
        try:
            if isinstance(state, list):
                state_text = ' '.join(state)
            else:
                state_text = state
        
            rejected_solutions_text = ' '.join(rejected_solutions) if rejected_solutions else "No rejected solutions."
        
            prompt = (f"You are an advanced AI tasked with generating solutions. "
                      f"Given the current state: '{state_text}', "
                      f"and considering the following rejected solutions: '{rejected_solutions_text}', "
                      f"generate a solution for the task: {initial_prompt}. "
                      f"Be concise and direct, providing intuitive solutions quickly.")
        
            if self.verbose:
                print(f"Generating solution for state: {state_text}")
        except Exception as e:
            logger.error(f"Error in prompt creation: {e}")
            return None
            
        try:
            input_ids = self.tokenizer.encode(prompt, return_tensors="pt").to(self.device)
            output = self.model.generate(input_ids, max_length=5000)
            decoded_output = self.tokenizer.decode(output[0], skip_special_tokens=True)
            solution = decoded_output
        except Exception as e:
            if self.verbose:
                print(f"Error generating solution for state: {state_text}")
                print(f"Error: {e}")
            solution = ""
    
        return solution


    def evaluate_states(self, states, initial_prompt, max_length=10):
        state_values = {}
        for state in states:
            state_text = ' '.join(state)
            prompt = f"Given the current state of reasoning: '{state_text}', pessimistically evaluate its value as a float between 0 and 1 based on its potential to achieve {initial_prompt}"
    
            if self.verbose:
                print(f"Evaluating state: {state_text}")
    
            value_obtained = False
            while not value_obtained:
                try:
                    input_ids = self.tokenizer.encode(prompt, return_tensors="pt").to(self.device)
                    output = self.model.generate(input_ids, max_length=5000)
                    decoded_output = self.tokenizer.decode(output[0], skip_special_tokens=True)
                    value = float(decoded_output)
                    if self.verbose:
                        print(f"Value obtained: {value}")
                    value_obtained = True
                except ValueError:
                    if self.verbose:
                        print(f"Error converting value to float for state: {state_text}. Retrying...")
                    # The loop will continue until a valid float is obtained
                except Exception as e:
                    if self.verbose:
                        print(f"Error evaluating state: {state_text}")
                        print(f"Error: {e}")
                    value = 0  # Assign a default value if there's an exception other than ValueError
                    break  # Exit the loop in case of non-ValueError exceptions
    
            state_values[state] = value
    
        return state_values

@staticmethod
class HFPipelineModel(AbstractLanguageModel):
    def __init__(self, model_name, verbose=False):
        self.model_name = model_name
        self.pipeline = pipeline("text-generation", model=model_name)
        self.verbose = verbose

    def generate_thoughts(self, state, k, max_length=100):
        state_text = ' '.join(state)
        prompt = f"Write down your observations in format 'Observation:xxxx', then write down your thoughts in format 'Thoughts:xxxx Given the current state of reasoning: '{state_text}', generate {k} coherent solutions to achieve"


        if self.verbose:
            print(f"Generating thoughts for state: {state_text}")

        try:
            inputs = self.tokenizer(prompt, return_tensors="pt")
            outputs = self.model.generate(input_ids=inputs["input_ids"], max_length=max_length, num_return_sequences=k)
            thoughts = [self.tokenizer.decode(output, skip_special_tokens=True) for output in outputs]
        except Exception as e:
            if self.verbose:
                print(f"Error generating thoughts for state: {state_text}")
                print(f"Error: {e}")
            thoughts = []

        return thoughts

    def evaluate_states(self, states, initial_prompt, max_length=10):
        state_values = {}
        for state in states:
            state_text = ' '.join(state)
            prompt = f"Given the current state of reasoning: '{state_text}', pessimistically evaluate its value as a float between 0 and 1 based on its potential to achieve {initial_prompt}"

            if self.verbose:
                print(f"Evaluating state: {state_text}")

            try:
                generated_outputs = self.pipeline(prompt, max_length=max_length, num_return_sequences=1)
                value_text = generated_outputs[0]["generated_text"]
                value = float(value_text)
                print(f'value {value}')
            except ValueError:
                if self.verbose:
                    print(f"Error converting value to float for state: {state_text}")
                value = 0  # Assign a default value if the conversion fails
            except Exception as e:
                if self.verbose:
                    print(f"Error evaluating state: {state_text}")
                    print(f"Error: {e}")
                value = 0

            state_values[state] = value

        return state_values
    
    @staticmethod
    def load(model_name, verbose=False):
        return HFPipelineModel(model_name, verbose)
    
        
