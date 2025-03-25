import os
from dotenv import load_dotenv
from sdk_codeassist.ingest import documentation_ingestion
from sdk_codeassist.retrieval import setup_retriever
from sdk_codeassist.planning import setup_planner 
from sdk_codeassist.generation import setup_generator

# Load environment variables
load_dotenv()

def main():
    # Example: Ingest documentation from a GitHub repository
    sdk_repo = "https://github.com/huggingface/transformers"
    dataset_path = "hub://yourusername/transformers-docs"
    
    # Uncomment to ingest documentation (only needed once)
    # documentation_ingestion.ingest_sdk_documentation(sdk_repo, dataset_path)
    
    # Setup components
    retriever = setup_retriever(dataset_path)
    planner = setup_planner()
    generator = setup_generator(retriever)
    
    # Example code generation request
    request = "Create a function that loads a pre-trained BERT model, tokenizes a list of input texts, and returns the embeddings"
    
    # Get context for planning
    context_docs = retriever.get_relevant_documents(request)
    context = "\n\n".join([doc.page_content for doc in context_docs])
    
    # Create plan
    plan = planner.create_plan(request, context)
    print(f"Generated plan with {len(plan.tasks)} tasks")
    
    # Generate code
    result = generator.generate_from_plan(plan)
    
    # Display results
    print("\n=== GENERATED CODE ===")
    print(result["code"])
    
    print(f"\n=== CONFIDENCE: {result['confidence']:.2f} ===")
    
    if result.get("missing_info"):
        print("\n=== MISSING INFORMATION ===")
        for info in result["missing_info"]:
            print(f"- {info}")
    
    if result.get("suggestions"):
        print("\n=== SUGGESTIONS ===")
        for suggestion in result["suggestions"]:
            print(f"- {suggestion}")

if __name__ == "__main__":
    main()
