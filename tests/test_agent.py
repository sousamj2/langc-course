import sys
from pathlib import Path
import asyncio

# Add project root to python path
project_root = Path(__file__).resolve().parent.parent
sys.path.append(str(project_root))

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Disable LangSmith tracing for standalone test to prevent DNS timeouts in sandboxed environments
import os
os.environ["LANGCHAIN_TRACING_V2"] = "false"
os.environ["LANGSMITH_TRACING_V2"] = "false"

from app.agent import ProductionAgent

async def main():
    agent = ProductionAgent()

    print('=== PRODUCTION AGENT - STANDALONE TEST ===')
    print()

    queries = [
        'What is LangGraph in one sentence?',
        'What is 2 + 2?',
        'Explain the difference between RAG and fine-tuning in 2 sentences.',
    ]

    for query in queries:
        print(f"Question: {query}")
        result = await agent.invoke(query)
        if len(result['response']) > 150:
            print(f"Response: {result['response'][:150]}...\n")
        else:
            print(f"Response: {result['response']}\n")
        # print(result)
        print(f"Model used: {result['model_used']}")
        print(f"Error: {result['error']}")
        print(f"Is fallback: {result['is_fallback']}")
        print("------------------------------")
        print()

if __name__ == "__main__":
    asyncio.run(main())