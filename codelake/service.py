import logging
import json
from typing import Dict, List, Any, Optional
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import HumanMessage, AIMessage
from langchain.memory import ConversationBufferWindowMemory
from langchain_openai import ChatOpenAI
from rich.console import Console
from rich.syntax import Syntax
from rich.markdown import Markdown
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
from codelake.retrieval import setup_retriever
from codelake.planning import setup_planner
from codelake.generation import setup_generator
from codelake.config import settings

logger = logging.getLogger(__name__)

# Console for rich output in interactive mode
console = Console()

class CodeSession:
    """Manages a coding session with memory and SDK documentation access."""
    
    def __init__(self, dataset_path: str):
        """
        Initialize a code session.
        
        Args:
            dataset_path: Path to the Deep Lake dataset
        """
        # Set up components
        self.retriever = setup_retriever(dataset_path)
        self.planner = setup_planner()
        self.generator = setup_generator(self.retriever)
        
        # Initialize memory
        self.memory = ConversationBufferWindowMemory(
            k=10,
            memory_key="chat_history",
            return_messages=True
        )
        
        # Initialize language model for conversations
        self.llm = ChatOpenAI(
            model=settings.model_name, 
            temperature=settings.temperature
        )
        
        self.conversation_prompt = ChatPromptTemplate.from_template(
            """You are an expert SDK coding assistant. You help generate and explain code using the SDK documentation.
            
            # Conversation History
            {chat_history}
            
            # User Request
            {user_input}
            
            Respond conversationally while maintaining technical accuracy. If you need to generate code, 
            make sure it follows the SDK documentation precisely. If you're unsure about anything, 
            acknowledge the limitations and suggest what information you'd need.
            """
        )
    
    def generate_code(self, request: str) -> Dict[str, Any]:
        """
        Generate code based on user request.
        
        Args:
            request: User's code generation request
            
        Returns:
            Dictionary with generated code and metadata
        """
        logger.info(f"Generating code for request: {request}")
        
        # Retrieve context for planning
        context_docs = self.retriever.get_relevant_documents(request)
        context = "\n\n".join([doc.page_content for doc in context_docs])
        
        # Create plan
        plan = self.planner.create_plan(request, context)
        
        # Generate code from plan
        result = self.generator.generate_from_plan(plan)
        
        # Add plan for reference
        result['plan'] = plan.dict()
        
        return result
    
    def process_message(self, message: str) -> Dict[str, Any]:
        """
        Process a user message and determine appropriate action.
        
        Args:
            message: User's message
            
        Returns:
            Response including text and any generated code
        """
        # Check if this looks like a code generation request
        code_request_indicators = [
            "generate", "create", "write", "implement", "code for", 
            "function", "class", "script", "program"
        ]
        
        is_code_request = any(indicator in message.lower() for indicator in code_request_indicators)
        
        # Get chat history
        chat_history = self.memory.load_memory_variables({})["chat_history"]
        
        if is_code_request:
            # Generate code
            code_result = self.generate_code(message)
            
            # Create response
            response = {
                "type": "code",
                "message": f"Here's the code for your request:\n\n```python\n{code_result['code']}\n```\n\n",
                "code": code_result["code"],
                "confidence": code_result["confidence"],
                "suggestions": code_result.get("suggestions", []),
                "missing_info": code_result.get("missing_info", [])
            }
            
            # Add explanation if confidence is high
            if code_result["confidence"] > 0.7:
                explanation = "\n".join([output.explanation for output in code_result["task_outputs"].values()])
                response["message"] += f"\n**Explanation:**\n{explanation}"
            
            # Add missing information requests
            if code_result.get("missing_info"):
                response["message"] += "\n\n**Additional information needed:**\n"
                for info in code_result["missing_info"]:
                    response["message"] += f"- {info}\n"
            
            # Add improvement suggestions
            if code_result.get("suggestions"):
                response["message"] += "\n\n**Suggestions for improvement:**\n"
                for suggestion in code_result["suggestions"]:
                    response["message"] += f"- {suggestion}\n"
                    
        else:
            # Regular conversation
            chain = self.conversation_prompt | self.llm
            chat_response = chain.invoke({
                "chat_history": chat_history,
                "user_input": message
            })
            
            response = {
                "type": "text",
                "message": chat_response.content
            }
        
        # Update memory
        self.memory.save_context(
            {"input": message},
            {"output": response["message"]}
        )
        
        return response

# FastAPI service for the API mode
app = FastAPI(title="codelake API")

class CodeRequest(BaseModel):
    message: str
    session_id: Optional[str] = None

class CodeResponse(BaseModel):
    message: str
    code: Optional[str] = None
    type: str
    confidence: Optional[float] = None
    suggestions: Optional[List[str]] = None
    missing_info: Optional[List[str]] = None
    session_id: str

# Store active sessions
sessions: Dict[str, CodeSession] = {}

@app.post("/generate", response_model=CodeResponse)
async def generate_code(request: CodeRequest):
    """Handle code generation requests."""
    try:
        # Get or create session
        session_id = request.session_id or "default"
        if session_id not in sessions:
            sessions[session_id] = CodeSession(settings.deeplake_dataset_path)
        
        # Process the message
        result = sessions[session_id].process_message(request.message)
        
        # Return the response
        return CodeResponse(
            message=result["message"],
            code=result.get("code"),
            type=result["type"],
            confidence=result.get("confidence"),
            suggestions=result.get("suggestions"),
            missing_info=result.get("missing_info"),
            session_id=session_id
        )
    except Exception as e:
        logger.error(f"Error generating code: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

def run_service(dataset_path: str):
    """Run the codelake as an API service."""
    import uvicorn
    logger.info(f"Starting codelake API on {settings.api_host}:{settings.api_port}")
    uvicorn.run(app, host=settings.api_host, port=settings.api_port)

def run_interactive_session(dataset_path: str):
    """Run an interactive session in the terminal."""
    console.print("[bold green]codelake Interactive Session[/bold green]")
    console.print("Type your code generation requests or questions. Type 'exit' to quit.")
    
    # Create session
    session = CodeSession(dataset_path)
    
    while True:
        # Get user input
        user_input = console.input("\n[bold blue]> [/bold blue]")
        
        if user_input.lower() in ["exit", "quit", "q"]:
            break
            
        try:
            # Process message
            result = session.process_message(user_input)
            
            # Display response
            if result["type"] == "code":
                # Display code with syntax highlighting
                console.print("\n[bold green]Generated Code:[/bold green]")
                syntax = Syntax(result["code"], "python", theme="monokai", line_numbers=True)
                console.print(syntax)
                
                # Display additional information
                if result.get("confidence") is not None:
                    confidence_color = "green" if result["confidence"] > 0.8 else "yellow" if result["confidence"] > 0.5 else "red"
                    console.print(f"\n[bold {confidence_color}]Confidence: {result['confidence']:.2f}[/bold {confidence_color}]")
                
                if result.get("missing_info"):
                    console.print("\n[bold yellow]Additional Information Needed:[/bold yellow]")
                    for info in result["missing_info"]:
                        console.print(f"• {info}")
                
                if result.get("suggestions"):
                    console.print("\n[bold blue]Suggestions for Improvement:[/bold blue]")
                    for suggestion in result["suggestions"]:
                        console.print(f"• {suggestion}")
            else:
                # Display text response as markdown
                console.print(Markdown(result["message"]))
                
        except Exception as e:
            console.print(f"[bold red]Error: {str(e)}[/bold red]")
