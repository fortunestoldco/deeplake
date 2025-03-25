# codelake

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

codelake is a powerful AI-powered tool that generates SDK-compliant code by leveraging Deep Lake vector database to store and retrieve SDK documentation. This system ensures accurate code generation that follows best practices and API specifications.

## 🌟 Features

- **Accurate SDK-Compliant Code Generation**: Generate code that precisely follows SDK requirements
- **Deep Lake Vector Storage**: Efficient semantic search to find the most relevant SDK documentation
- **Task Planning**: Break down complex requests into logical, sequential steps
- **Web Search Fallback**: Retrieve documentation from the web when local data is insufficient
- **Interactive Console Mode**: Developer-friendly interface with syntax highlighting
- **API Service**: RESTful API for integration with other tools
- **Auto-Updating Documentation**: Keep SDK documentation current with scheduled updates
- **Conversation Memory**: Maintain context across interactions for better results

## 📋 Requirements

- Python 3.8+
- OpenAI API key
- Activeloop token for Deep Lake

## 🚀 Installation

### Option 1: From Source

```bash
# Clone the repository
git clone https://github.com/yourusername/sdk-codeassist.git
cd sdk-codeassist

# Install dependencies
pip install -r requirements.txt

# Install in development mode
pip install -e .
```

### Option 2: Using Docker

```bash
# Build the Docker image
docker build -t sdk-codeassist .

# Run the container
docker run -p 8000:8000 --env-file .env sdk-codeassist
```

## ⚙️ Configuration

Create a `.env` file in the project root with your API keys and configuration:

```
# Required API Keys
OPENAI_API_KEY=your_openai_api_key_here
ACTIVELOOP_TOKEN=your_activeloop_token_here

# Deep Lake Configuration
DEEPLAKE_DATASET_PATH=hub://your_username/sdk-documentation

# Optional Web Search Configuration
GOOGLE_API_KEY=your_google_api_key_here
GOOGLE_CSE_ID=your_google_cse_id_here
```

See the [full configuration documentation](docs/configuration.md) for all available options.

## 📚 Usage

### Step 1: Ingest SDK Documentation

Before generating code, you need to ingest the SDK documentation:

```bash
python -m codelake.main --ingest --sdk-repo="https://github.com/organization/sdk-repo" --dataset-path="hub://username/sdk-docs"
```

### Step 2: Generate Code

#### Interactive Mode

```bash
python -m codelake.main --interactive
```

This launches an interactive console session where you can ask questions and request code generation.

#### API Mode

```bash
python -m codelake.main --api
```

This starts a FastAPI server on port 8000. You can then make requests:

```bash
curl -X POST "http://localhost:8000/generate" \
  -H "Content-Type: application/json" \
  -d '{"message": "Generate a function to authenticate with the SDK and list available resources"}'
```

### Python API

```python
from codelake.retrieval import setup_retriever
from codelake.planning import setup_planner
from codelake.generation import setup_generator

# Setup components
dataset_path = "hub://yourusername/sdk-docs"
retriever = setup_retriever(dataset_path)
planner = setup_planner()
generator = setup_generator(retriever)

# Generate code
request = "Create a function that uploads a file to cloud storage using the SDK"
context_docs = retriever.get_relevant_documents(request)
context = "\n\n".join([doc.page_content for doc in context_docs])
plan = planner.create_plan(request, context)
result = generator.generate_from_plan(plan)

print(result["code"])
```

## 📐 Architecture

codelake uses a modular architecture consisting of several key components:

1. **Documentation Ingestion**: Processes SDK documentation into searchable chunks
2. **Vector Store**: Deep Lake-powered semantic search for documentation retrieval
3. **Task Planner**: Breaks down complex requests into manageable steps
4. **Code Generator**: Creates code based on retrieved documentation and plan
5. **Web Search Fallback**: Retrieves information not found in the stored documentation
6. **Service Layer**: Provides interactive console and REST API interfaces

![Architecture Diagram](docs/architecture.png)

## 🔍 Example

### User Request:
"Generate code to authenticate with AWS S3 and list all buckets"

### Generated Code:
```python
import boto3
from botocore.exceptions import ClientError

def list_s3_buckets(aws_access_key_id=None, aws_secret_access_key=None, region_name='us-east-1'):
    """
    Authenticate with AWS S3 and list all buckets.
    
    Args:
        aws_access_key_id (str, optional): AWS access key ID. Defaults to None (uses environment variables or AWS configuration file).
        aws_secret_access_key (str, optional): AWS secret access key. Defaults to None (uses environment variables or AWS configuration file).
        region_name (str, optional): AWS region name. Defaults to 'us-east-1'.
        
    Returns:
        list: List of bucket names, or empty list on error.
        
    Raises:
        ClientError: If there's an error connecting to AWS S3.
    """
    try:
        # Initialize S3 client
        s3_client = boto3.client(
            's3',
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
            region_name=region_name
        )
        
        # Get list of buckets
        response = s3_client.list_buckets()
        
        # Extract bucket names
        buckets = [bucket['Name'] for bucket in response['Buckets']]
        
        print(f"Found {len(buckets)} buckets:")
        for bucket in buckets:
            print(f"  - {bucket}")
            
        return buckets
        
    except ClientError as e:
        print(f"Error connecting to AWS S3: {e}")
        return []

# Example usage
if __name__ == "__main__":
    # Option 1: Use environment variables (AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY)
    buckets = list_s3_buckets()
    
    # Option 2: Provide credentials directly (not recommended for production)
    # buckets = list_s3_buckets('YOUR_ACCESS_KEY', 'YOUR_SECRET_KEY', 'us-west-2')
```

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📜 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- [LangChain](https://github.com/langchain-ai/langchain) - The foundation for the retrieval and generation pipeline
- [Deep Lake](https://github.com/activeloopai/deeplake) - The vector database powering documentation retrieval
- [OpenAI](https://openai.com/) - For the embeddings and language models

---

Built with ❤️ for developers who want SDK-compliant code generation.
