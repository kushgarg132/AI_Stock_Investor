
import sys
import os

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.llm import MultiKeyChain

def test_instantiation():
    try:
        # We just need a dummy LLM object
        class DummyLLM:
            def bind_tools(self, *args, **kwargs): return self
            
        print("Attempting to instantiate MultiKeyChain...")
        chain = MultiKeyChain([DummyLLM()])
        print("SUCCESS: Instantiated MultiKeyChain.")
    except TypeError as e:
        print(f"FAILURE: TypeError during instantiation: {e}")
    except Exception as e:
        print(f"FAILURE: Unexpected error: {e}")

if __name__ == "__main__":
    test_instantiation()
