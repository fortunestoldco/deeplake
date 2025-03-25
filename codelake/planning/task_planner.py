import json
import logging
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate
from codelake.config import settings

logger = logging.getLogger(__name__)

class CodeTask(BaseModel):
    """Structure for a single unit of work in code generation."""
    id: str = Field(description="Unique identifier for this task")
    description: str = Field(description="Description of the task")
    sdk_components: List[str] = Field(description="List of SDK components needed")
    dependencies: List[str] = Field(default_factory=list, description="IDs of tasks this depends on")

class CodePlan(BaseModel):
    """Complete plan for a coding task."""
    tasks: List[CodeTask] = Field(description="List of tasks to complete the code")
    context: Dict[str, Any] = Field(default_factory=dict, description="Additional context for generation")

class TaskPlanner:
    """Plans coding tasks by breaking them down into steps with component requirements."""
    
    def __init__(self, model_name: str = "gpt-4-turbo", temperature: float = 0.2):
        """
        Initialize the task planner.
        
        Args:
            model_name: Name of the model to use
            temperature: Temperature for generation
        """
        self.llm = ChatOpenAI(model=model_name, temperature=temperature)
        self.output_parser = PydanticOutputParser(pydantic_object=CodePlan)
        
        self.prompt = ChatPromptTemplate.from_template(
            """You are an expert SDK architect tasked with breaking down a coding request into logical steps.
            
            # CODE REQUEST
            {code_request}
            
            # SDK CONTEXT
            The following SDK context should inform your planning:
            {sdk_context}
            
            # INSTRUCTIONS
            1. Analyze the request and break it down into a sequence of coding tasks.
            2. For each task, identify the specific SDK components (classes, methods, etc.) that will be needed.
            3. Establish dependencies between tasks where necessary.
            4. Ensure the sequence of tasks will produce complete, functional code.
            
            {format_instructions}
            """
        )
    
    def create_plan(self, code_request: str, sdk_context: str = "") -> CodePlan:
        """
        Create a step-by-step plan for implementing the requested code.
        
        Args:
            code_request: The user's code generation request
            sdk_context: Context about the SDK from documentation
            
        Returns:
            Structured plan for code generation
        """
        try:
            # Prepare the prompt inputs
            inputs = {
                "code_request": code_request,
                "sdk_context": sdk_context,
                "format_instructions": self.output_parser.get_format_instructions()
            }
            
            # Get the response
            chain = self.prompt | self.llm | self.output_parser
            plan = chain.invoke(inputs)
            
            logger.info(f"Created plan with {len(plan.tasks)} tasks")
            return plan
            
        except Exception as e:
            logger.error(f"Error creating plan: {e}", exc_info=True)
            
            # Create a minimal fallback plan
            return CodePlan(tasks=[
                CodeTask(
                    id="fallback_task",
                    description=f"Implement code for: {code_request}",
                    sdk_components=[]
                )
            ])

def setup_planner() -> TaskPlanner:
    """Set up and return a task planner."""
    return TaskPlanner(
        model_name=settings.model_name,
        temperature=settings.temperature
    )
