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
    with open("C:\\Users\\Nukal\\Projects\\PythonLeadAgent\\systemPrompt.txt","r") as f:
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

