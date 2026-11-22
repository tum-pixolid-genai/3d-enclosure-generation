
def mock_ai_agent(prompt: str) -> dict:
    return {
        "mode": "mock",
        "original_prompt": prompt,
        "shape": "box",
        "length": 100,
        "width": 60,
        "height": 40,
        "unit": "mm",
        "lid_type": "removable"
    }
