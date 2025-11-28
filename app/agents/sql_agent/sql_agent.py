import os
import logging
from langchain_openai import ChatOpenAI
from typing import Literal, TypedDict
from langchain.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from app.agents.sql_agent.agent_db_helper import get_db_connection
from langchain_community.utilities import SQLDatabase
from langchain_community.agent_toolkits.sql.base import create_sql_agent

load_dotenv()

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


model = ChatOpenAI(model=os.getenv("LLM_MODEL", "gpt-4.1-mini-2025-04-14"))


# Load database schemas
SCHEMA_FILE = os.path.join(
    os.path.dirname(__file__), "..", "..", "scripts", "database_schemas.txt"
)
with open(SCHEMA_FILE, "r") as f:
    DATABASE_SCHEMAS = f.read()


# State definition
class SQLAgentState(TypedDict):
    user_query: str
    user_id: int  # User ID for security checks
    generated_sql: str
    target_database: str  # The database to query (catalogue_db, auction_db, payment_db)
    validation_result: dict  # {"valid": bool, "reason": str, "corrected_sql": str}
    query_result: str
    error: str


def determine_database(user_query: str) -> str:
    """Determine which database to query based on the user's question."""
    prompt = f"""
        Based on the user's question, determine which database to query.
        Available databases:
        - catalogue_db: Contains items/products for sale
        - auction_db: Contains auctions and bids
        - payment_db: Contains payment and receipt information

        User question: {user_query}

        Return ONLY the database name (catalogue_db, auction_db, or payment_db).
        If the query spans multiple databases, return the primary one.
        """

    response = model.invoke([HumanMessage(content=prompt)])
    db_name = response.content.strip().lower()
    if db_name in ["catalogue_db", "auction_db", "payment_db"]:
        return db_name

    return None


class SQLGenerationResult(BaseModel):
    """Structured output for SQL generation."""

    sql_query: str = Field(description="The generated PostgreSQL SELECT query")
    target_database: str = Field(
        description="The target database (catalogue_db, auction_db, or payment_db)"
    )


def generate_sql(state: SQLAgentState) -> SQLAgentState:
    """Generate SQL query based on user request and database schemas."""

    user_query = state["user_query"]
    user_id = state.get("user_id", None)

    # Determine which database to use
    target_db = determine_database(user_query)

    system_prompt = f"""
        You are an expert PostgreSQL query generator. 
        Your task is to generate a syntactically correct PostgreSQL query.

        DATABASE SCHEMAS:
        {DATABASE_SCHEMAS}

        IMPORTANT RULES:
        1. Use ONLY PostgreSQL dialect (no MySQL or other dialects)
        2. Generate ONLY SELECT queries (NO INSERT, UPDATE, DELETE, DROP, etc.)
        3. Always use proper PostgreSQL syntax and functions
        4. Limit results to 10 rows unless specified otherwise (30 rows maximum)
        5. Use appropriate JOINs when needed across tables
        6. Always qualify column names with table names when using JOINs
        7. Use proper data type casting when needed (e.g., ::integer, ::timestamp)
        8. DO NOT prefix table names with database names (e.g., use 'items' not 'catalogue_db.items')
        9. Tables are in the 'public' schema, no need to specify schema unless required

        TARGET DATABASE: {target_db}

        User Query: {user_query}
        
        USER_ID (if applicable): {user_id}

        Generate the SQL query without markdown formatting or explanations.
        """

    structured_llm = model.with_structured_output(SQLGenerationResult)
    result = structured_llm.invoke(
        [
            SystemMessage(content=system_prompt),
            HumanMessage(content="Generate SQL query"),
        ]
    )

    logger.info("GENERATED SQL:")
    logger.info(f"\n{result.sql_query}")
    logger.info(f"Target Database: {result.target_database}")

    state["generated_sql"] = result.sql_query
    state["target_database"] = result.target_database
    return state


class SQLValidationResult(BaseModel):
    """Structured output for SQL validation."""

    valid: bool = Field(description="Whether the SQL query is valid and safe")
    reason: str = Field(description="Brief explanation of validation decision")
    corrected_sql: str = Field(
        description="Corrected SQL query if invalid, otherwise original SQL"
    )


def verify_sql(state: SQLAgentState) -> SQLAgentState:
    """Verify the SQL query for syntax correctness and security."""

    generated_sql = state["generated_sql"]
    target_db = state["target_database"]
    user_id = state.get("user_id", None)

    verification_prompt = f"""
        You are a SQL security and syntax validator. Analyze the following PostgreSQL query for:

        1. SYNTAX CORRECTNESS:
        - Valid PostgreSQL syntax
        - Proper table and column names (check against schemas)
        - Correct JOIN syntax
        - Proper data type usage
        - No syntax errors

        2. SECURITY CHECKS:
        - MUST be a SELECT query only (reject INSERT, UPDATE, DELETE, DROP, ALTER, etc.)
        - Should NOT expose other users' personal information (e.g., payment details, addresses, card numbers)
        - Queries about what users are selling or have sold are OK
        - Queries about public auction/bid information are OK
        - If user_id is provided, ensure the query filters appropriately for that user's data when accessing personal info

        DATABASE SCHEMAS:
        {DATABASE_SCHEMAS}
        
        TARGET DATABASE: {target_db}

        USER_ID (if applicable): {user_id}
        """

    structured_llm = model.with_structured_output(SQLValidationResult)
    validation_result = structured_llm.invoke(
        [
            SystemMessage(content=verification_prompt),
            HumanMessage(content=f"Validate this query: {generated_sql}"),
        ]
    )

    logger.info("VALIDATION RESULT:")
    logger.info(f"\nValid: {validation_result.valid}")
    logger.info(f"Reason: {validation_result.reason}")
    logger.info(f"Corrected SQL: {validation_result.corrected_sql}")

    state["validation_result"] = {
        "valid": validation_result.valid,
        "reason": validation_result.reason,
        "corrected_sql": validation_result.corrected_sql,
    }

    return state


def execute_sql(state: SQLAgentState) -> SQLAgentState:
    """Execute queries using LangChain SQL agent with multi-database support."""

    validation = state["validation_result"]
    if not validation["valid"]:
        state["error"] = f"Query validation failed: {validation['reason']}"
        state["query_result"] = ""
        return state

    user_query = state["user_query"]

    logger.info(f"EXECUTING MULTI-DATABASE QUERY")

    # Build database connection URIs
    db_host = os.getenv("POSTGRES_HOST", "localhost")
    db_port = os.getenv("POSTGRES_PORT", "5555")
    db_user = os.getenv("POSTGRES_USER", "dev")
    db_password = os.getenv("POSTGRES_PASSWORD", "dev")

    try:
        # Connect to all three databases
        catalogue_db = SQLDatabase.from_uri(
            f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/catalogue_db"
        )
        auction_db = SQLDatabase.from_uri(
            f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/auction_db"
        )
        payment_db = SQLDatabase.from_uri(
            f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/payment_db"
        )

        # Create agents for each database
        catalogue_agent = create_sql_agent(
            llm=model,
            db=catalogue_db,
            agent_type="openai-tools",
            verbose=True,
            handle_parsing_errors=True,
            max_iterations=5,
        )

        payment_agent = create_sql_agent(
            llm=model,
            db=payment_db,
            agent_type="openai-tools",
            verbose=True,
            handle_parsing_errors=True,
            max_iterations=5,
        )

        # Start with the primary database based on initial determination
        target_db = state.get("target_database", "catalogue_db")

        logger.info(f"Starting with primary database: {target_db}")

        # Step 1: Query the primary database
        if target_db == "payment_db":
            primary_prompt = f"""
Query the payment database to answer: {user_query}

Return the item_id values and any relevant metrics (counts, amounts, etc.).
Be specific with the numbers. For example: "item_id: 7 has 1 sale, item_id: 8 has 1 sale"
"""
            result = payment_agent.invoke({"input": primary_prompt})
            initial_output = result.get("output", "")
            logger.info(f"Primary query result: {initial_output}")

            # Step 2: Extract item IDs and query catalogue
            if "item_id" in initial_output.lower():
                logger.info("Detected item_ids, querying catalogue for details...")

                enrichment_prompt = f"""
The payment database query returned: {initial_output}

Now query the catalogue database (items table) to get the title and description 
for each item_id mentioned above. 

Then provide a COMPLETE answer that combines:
1. The sales data from payments
2. The item details (title, description) from catalogue

Format the final answer clearly for the user's question: {user_query}
"""
                enriched_result = catalogue_agent.invoke({"input": enrichment_prompt})
                final_output = enriched_result.get("output", initial_output)
            else:
                final_output = initial_output

        else:
            # For catalogue or auction queries, use the appropriate agent directly
            if target_db == "catalogue_db":
                primary_agent = catalogue_agent
            else:
                primary_agent = create_sql_agent(
                    llm=model,
                    db=auction_db,
                    agent_type="openai-tools",
                    verbose=True,
                    handle_parsing_errors=True,
                    max_iterations=5,
                )

            result = primary_agent.invoke({"input": user_query})
            final_output = result.get("output", "")

        state["query_result"] = final_output
        state["error"] = ""
        logger.info(f"Agent execution completed successfully")

    except Exception as e:
        error_msg = f"Query execution error: {str(e)}"
        state["error"] = error_msg
        state["query_result"] = ""
        logger.error(error_msg)

    return state


def should_execute(state: SQLAgentState) -> Literal["execute_sql", "__end__"]:
    """Decide whether to execute the query or end."""
    if state.get("validation_result", {}).get("valid", False):
        return "execute_sql"
    else:
        return END


# Build the graph
graph = StateGraph(SQLAgentState)
graph.add_node("generate_sql", generate_sql)
graph.add_node("verify_sql", verify_sql)
graph.add_node("execute_sql", execute_sql)
graph.add_edge(START, "generate_sql")
graph.add_edge("generate_sql", "verify_sql")
graph.add_conditional_edges(
    "verify_sql", should_execute, {"execute_sql": "execute_sql", "__end__": END}
)
graph.add_edge("execute_sql", END)

agent = graph.compile()


# # Run a query through the SQL agent.
# initial_state = {
#     "user_query": "List all items ever posted",
#     "user_id": 1,
#     "generated_sql": "",
#     "target_database": "",
#     "validation_result": {},
#     "query_result": "",
#     "error": "",
# }
# result = agent.invoke(initial_state)
# print(result.get("query_result", "No results"))
