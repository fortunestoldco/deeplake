import logging
import json
from typing import List, Dict, Any, Optional, Union
from pydantic import BaseModel, Field
from langchain_core.retrievers import BaseRetriever
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from sdk_codeassist.planning.task_planner import CodePlan, CodeTask
from sdk_codeassist.config import settings

logger = logging.getLogger(__name__)

class CodeOutput(BaseModel):
    """Structured output for generated code."""
    code: str = Field(description="The generated code")
    explanation: str = Field(description="Explanation of how the code works")
    confidence: float = Field(description="Confidence score between 0-1")
    missing_info: Optional[List[str]] = Field(default=None, description="Any missing information needed")
    suggestions: Optional[List[str]] = Field(default=None, description="Suggestions for improvements")

class SDKCodeGenerator:
    """Generates SDK-compliant code based on retrieved documentation and plans."""
    
    def __init__(
        self,
        retriever: BaseRetriever,
        model_name: str = "gpt-4-turbo",
        temperature: float = 0.2
    ):
        """
        Initialize the code generator.
        
        Args:
            retriever: Retriever for SDK documentation
            model_name: Name of the model to use
            temperature: Temperature for generation
        """
        self.retriever = retriever
        self.llm = ChatOpenAI(model=model_name, temperature=temperature)
        self.output_parser = PydanticOutputParser(pydantic_object=CodeOutput)
        
        # Create prompts
        self.code_generation_prompt = ChatPromptTemplate.from_template(
            """You are an expert SDK code generator that writes clean, efficient, and compliant code.
            
            # TASK DESCRIPTION
            {task_description}
            
            # SDK COMPONENTS REQUIRED
            {sdk_components}
            
            # SDK DOCUMENTATION
            {sdk_documentation}
            
            # PREVIOUS CODE CONTEXT (if applicable)
            {previous_code}
            
            # INSTRUCTIONS
            1. Write complete, production-ready code that accomplishes the described task.
            2. Follow ALL best practices and conventions from the SDK documentation.
            3. Include proper error handling and comments.
            4. Ensure the code is optimized and follows modern patterns.
            5. Pay special attention to parameter types, return values, and method signatures.
            
            {format_instructions}
            """
        )
    
    def retrieve_documentation(self, components: List[str]) -> str:
        """
        Retrieve relevant documentation for the specified components.
        
        Args:
            components: List of SDK components to look up
            
        Returns:
            String containing the relevant documentation
        """
        all_docs = []
        
        # Handle empty components list
        if not components:
            return ""
            
        # Retrieve documentation for each component
        for component in components:
            try:
                docs = self.retriever.get_relevant_documents(component)
                all_docs.extend(docs)
                
                # If no direct match, try broader search
                if not docs:
                    broader_query = component.split('.')[-1] if '.' in component else component
                    docs = self.retriever.get_relevant_documents(broader_query)
                    all_docs.extend(docs)
            except Exception as e:
                logger.warning(f"Error retrieving documentation for {component}: {e}")
        
        # Deduplicate docs
        seen_content = set()
        unique_docs = []
        
        for doc in all_docs:
            if doc.page_content not in seen_content:
                seen_content.add(doc.page_content)
                unique_docs.append(doc)
        
        # Format documentation
        documentation = ""
        for doc in unique_docs:
            source = doc.metadata.get('source', 'Unknown')
            documentation += f"--- From {source} ---\n{doc.page_content}\n\n"
            
        return documentation
    
    def generate_code_for_task(
        self,
        task: CodeTask,
        previous_code: str = ""
    ) -> CodeOutput:
        """
        Generate code for a specific task.
        
        Args:
            task: The task to generate code for
            previous_code: Code from previous tasks to provide context
            
        Returns:
            Structured code output
        """
        try:
            # Retrieve SDK documentation
            documentation = self.retrieve_documentation(task.sdk_components)
            
            # Prepare inputs
            inputs = {
                "task_description": task.description,
                "sdk_components": ", ".join(task.sdk_components),
                "sdk_documentation": documentation,
                "previous_code": previous_code,
                "format_instructions": self.output_parser.get_format_instructions()
            }
            
            # Generate code
            chain = self.code_generation_prompt | self.llm | self.output_parser
            result = chain.invoke(inputs)
            
            logger.info(f"Generated code for task '{task.id}' with confidence {result.confidence:.2f}")
            return result
            
        except Exception as e:
            logger.error(f"Error generating code for task {task.id}: {e}", exc_info=True)
            
            # Return fallback output
            return CodeOutput(
                code=f"# Error generating code for: {task.description}\n# {str(e)}\n\n# Please try again with more specific instructions",
                explanation="An error occurred during code generation.",
                confidence=0.0,
                missing_info=["Error occurred during generation. Please try again with more detail."]
            )
    
    def generate_from_plan(self, plan: CodePlan) -> Dict[str, Any]:
        """
        Generate complete code based on the provided plan.
        
        Args:
            plan: The code generation plan
            
        Returns:
            Dictionary with complete code and metadata
        """
        results = {}
        all_code = ""
        task_outputs = {}
        
        # Process tasks in dependency order
        completed_tasks = set()
        remaining_tasks = plan.tasks.copy()
        
        while remaining_tasks:
            # Find tasks with satisfied dependencies
            ready_tasks = [
                task for task in remaining_tasks
                if all(dep in completed_tasks for dep in task.dependencies)
            ]
            
            if not ready_tasks:
                # If no ready tasks but tasks remain, there might be a cycle
                # Just take the first remaining task
                ready_tasks = [remaining_tasks[0]]
            
            # Generate code for each ready task
            for task in ready_tasks:
                result = self.generate_code_for_task(task, all_code)
                task_outputs[task.id] = result
                
                # Add to all code
                all_code += f"\n# Task: {task.description}\n"
                all_code += result.code + "\n\n"
                
                # Mark as completed
                completed_tasks.add(task.id)
                remaining_tasks.remove(task)
        
        # Calculate overall confidence
        overall_confidence = sum(output.confidence for output in task_outputs.values()) / len(task_outputs) if task_outputs else 0
        
        return {
            "code": all_code,
            "task_outputs": task_outputs,
            "confidence": overall_confidence,
            "missing_info": [item for output in task_outputs.values() 
                           for item in (output.missing_info or [])],
            "suggestions": [item for output in task_outputs.values() 
                          for item in (output.suggestions or [])]
        }

def setup_generator(retriever: BaseRetriever) -> SDKCodeGenerator:
    """Set up and return a code generator."""
    return SDKCodeGenerator(
        retriever=retriever,
        model_name=settings.model_name,
        temperature=settings.temperature
    )
