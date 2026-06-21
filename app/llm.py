from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel,Field
from dotenv import load_dotenv

class LLMResponse(BaseModel):
    Engine:str  = Field(description="Always keep 'google'")
    Query:str = Field(description="The enriched response")
    Location:str = Field(description="location")
    GL:str = Field(description="gl")
    Num:str = Field(description="number of results (by default keep 10)")



def EnrichQuery(model:ChatGroq, query:str)->(dict,str):
    import os
    current_dir = os.path.dirname(os.path.abspath(__file__))
    prompt_path = os.path.join(current_dir, "..", "systemPrompt.txt")
    with open(prompt_path, "r", encoding="utf-8") as f:
        systemPrompt = f.read()

    prompt = ChatPromptTemplate([
        ("system",systemPrompt),
        ("human",query)
    ],
    kwargs={"input_variables":query}
    )

    jsonParser = JsonOutputParser(pydantic_object=LLMResponse)
    
    chain = prompt | model | jsonParser
    try:
        response = chain.invoke({"query":query})
    except Exception as e:
        return "",str(e)
    
    return response,""

