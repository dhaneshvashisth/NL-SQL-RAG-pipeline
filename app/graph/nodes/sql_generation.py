
from openai import AsyncOpenAI
from app.graph.state import GraphState
from app.utils.config import config
from app.utils.prompt_templates import build_sql_generation_prompt
from app.utils.logger import get_logger

logger = get_logger(__name__)

_client = AsyncOpenAI(api_key=config.OPENAI_API_KEY)
MAX_RETRIES = 3


async def sql_generation_node(state: GraphState) -> GraphState:
    """ Generates SQL from natural language using GPT-4o-mini.
    On first call: clean generation
    On retry: self-correcting generation with error context  """
    question         = state["question"]
    schemas          = state["retrieved_schemas"] or []
    retry_count      = state["retry_count"]
    previous_sql     = state.get("generated_sql")
    validation_error = state.get("validation_error")
    role             = state["token_data"].role.value

    logger.info(
        "Node 2 — SQL Generation | attempt=%d/%d | question='%s'",
        retry_count + 1, MAX_RETRIES, question[:60]
    )

    if retry_count >= MAX_RETRIES:
        logger.error("Node 2 — Max retries reached | giving up")
        return {
            **state,
            "error_message": f"Failed to generate valid SQL after {MAX_RETRIES} attempts. "
                           f"Last error: {validation_error}"
        }

    prompt = build_sql_generation_prompt(
        question=question,
        schemas=schemas,
        role=role,
        retry_count=retry_count,
        previous_sql=previous_sql,
        validation_error=validation_error
    )

    try:
        response = await _client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user",   "content": question}
            ],
            temperature=0,     
                               
            max_tokens=500,
        )

        raw_sql = response.choices[0].message.content.strip()

        raw_sql = raw_sql.replace("```sql", "").replace("```", "").strip()

        logger.info(
            "Node 2 complete | sql_length=%d | sql_preview='%s'",
            len(raw_sql), raw_sql[:80]
        )

        return {
            **state,
            "generated_sql": raw_sql,
            "retry_count":   retry_count + 1,
            "is_valid":      None,   
            "validation_error": None
        }

    except Exception as e:
        logger.error("Node 2 failed | error=%s", str(e))
        return {
            **state,
            "error_message": f"SQL generation failed: {str(e)}"
        }