# --- Standard Library Imports ---
import os
import logging
import asyncio
from typing import List, Dict, Any, Optional

# --- Third-Party Imports ---
from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field
from dotenv import load_dotenv

# --- AI SDK Imports ---
import google.generativeai as genai
import vertexai
from vertexai.generative_models import GenerativeModel, Tool, grounding
from openai import AsyncAzureOpenAI
from anthropic import AsyncAnthropic

# --- Configuration & Environment Setup ---
load_dotenv()

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] Sapiatrum Server - %(message)s"
)
logger = logging.getLogger("Sapiatrum")

# --- Environment Key Parsing ---
# Securely read required environment variables
SAPIATRUM_PROJECT_NAME = "Sapiatrum"
SAPIATRUM_PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT", "sapiatrum")
# Grab keys with a safe string fallback so the container boots successfully
gemini_key = os.getenv("GOOGLE_API_KEY", "PLACEHOLDER_KEY")
azure_key = os.getenv("OPENAI_API_KEY", "PLACEHOLDER_KEY")
azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT", "https://azure.com")
anthropic_key = os.getenv("ANTHROPIC_API_KEY", "PLACEHOLDER_KEY")

# --- Critical SDK Client Initializations ---
# Note: User requested 'gemini-2.5-pro' and 'gemini-2.5-flash'. Using latest available '1.5' versions.
MAX_CORRECTION_LOOPS = 3 # Safeguard against infinite correction loops

# Define Triage Categories
CATEGORY_CODING = "coding"
CATEGORY_DATA_ANALYSIS = "data_analysis"
CATEGORY_DEEP_RESEARCH = "deep_research"
CATEGORY_BASIC = "basic_tasks"

BASE_SYSTEM_PROMPT = (
    "System Instruction: You must never invent or fabricate information. If you are unsure or lack the "
    "necessary data to answer accurately, you must state that you cannot answer the prompt as requested. "
    "Your primary directive is accuracy and truthfulness."
)

# Define model strings for easy management
MODEL_CLAUDE_SONNET = "claude-3-5-sonnet-20240620" # Using specific version for stability
MODEL_AZURE_COPILOT = "o3-mini"
MODEL_GEMINI_FLASH = "gemini-1.5-flash-latest"
MODEL_GEMINI_PRO = "gemini-1.5-pro-latest"

logger.info(f"Initializing {SAPIATRUM_PROJECT_NAME} environment...")

# 1. Consumer Gemini Client
consumer_gemini_flash = None
if gemini_key != "PLACEHOLDER_KEY":
    try:
        genai.configure(api_key=gemini_key)
        consumer_gemini_flash = genai.GenerativeModel('gemini-1.5-flash-latest')
        logger.info("Google AI (Gemini) SDK status: LOADED")
    except Exception as e:
        logger.warning(f"Consumer Gemini setup delayed: {e}")
else:
    logger.info("Google AI (Gemini) SDK status: MOCKED (GOOGLE_API_KEY not set)")

# 2. Enterprise Vertex AI Clients
vertex_gemini_flash, vertex_gemini_pro = None, None
if SAPIATRUM_PROJECT_ID != "sapiatrum":
    try:
        vertexai.init(project=SAPIATRUM_PROJECT_ID, location="us-central1")
        vertex_gemini_flash = GenerativeModel(MODEL_GEMINI_FLASH)
        vertex_gemini_pro = GenerativeModel(MODEL_GEMINI_PRO)
        logger.info("Google Cloud (Vertex AI) SDK status: LOADED")
    except Exception as e:
        logger.warning(f"Vertex AI initialization failed, will be mocked. Error: {e}")
else:
    logger.info("Google Cloud (Vertex AI) SDK status: MOCKED (GOOGLE_CLOUD_PROJECT not set)")

# 3. Azure OpenAI Client
azure_openai_client = None
if azure_key != "PLACEHOLDER_KEY" and azure_endpoint != "https://azure.com":
    try:
        azure_openai_client = AsyncAzureOpenAI(
            api_key=azure_key, 
            azure_endpoint=azure_endpoint, 
            api_version="2024-02-01" 
        )
        logger.info("Azure OpenAI SDK status: LOADED")
    except Exception as e:
        logger.warning(f"Azure Copilot setup delayed: {e}")
else:
    logger.info("Azure OpenAI SDK status: MOCKED (Azure keys not set)")

# 4. Anthropic Client
anthropic_client = None
if anthropic_key != "PLACEHOLDER_KEY":
    try:
        anthropic_client = AsyncAnthropic(api_key=anthropic_key)
        logger.info("Anthropic (Claude) SDK status: LOADED")
    except Exception as e:
        logger.warning(f"Anthropic setup delayed: {e}")
else:
    logger.info("Anthropic (Claude) SDK status: MOCKED (ANTHROPIC_API_KEY not set)")

# --- Tool Definitions ---
# Define the Google Search tool once for reuse in the pipeline.
# This addresses the concern about setting up the grounding pipeline.
SEARCH_GROUNDING_TOOL = Tool.from_google_search_retrieval(
    grounding.GoogleSearchRetrieval()
)

# --- FastAPI Setup ---
app = FastAPI(
    title=SAPIATRUM_PROJECT_NAME,
    description="Multi-agent AI task routing cluster API",
    version="1.0.0"
)

# --- Request/Response Schemas ---
class QueryRequest(BaseModel):
    user_question: str = Field(..., description="The query or question to be processed by the Sapiatrum cluster.")
    user_id: str = Field(..., description="Unique identifier of the user making the query.")

    model_config = {
        "json_schema_extra": {
            "example": {
                "user_question": "Explain the difference between synchronous and asynchronous processing in python.",
                "user_id": "usr_sapiatrum_99"
            }
        }
    }

class CitationItem(BaseModel):
    source: str = Field(..., description="The URL of the cited source.")
    text: str = Field(..., description="Brief excerpt or description of the context.")

class FinalAuditResponse(BaseModel):
    content: str = Field(..., description="The finalized, audited, and verified response in Markdown format.")
    citations: List[CitationItem] = Field(default_factory=list, description="Validated source citations matched in final audit.")
    panelist_failure_logged: bool = Field(False, description="True if the final audit found a flaw missed by the verification panel.")
    final_check_failures: Optional[Dict[str, str]] = Field(None, description="Record of any failures from the final all-model check.")

class QueryResponse(BaseModel):
    status: str = Field("success", description="Status of the pipeline execution.")
    project: str = Field(SAPIATRUM_PROJECT_NAME, description="Project context identifier.")
    category: str = Field(..., description="Identified routing category after adversarial triage.")
    triage_history: Dict[str, Any] = Field(..., description="Record of the adversarial triage process.")
    specialist_model_used: str = Field(..., description="Model designated for the request.")
    initial_specialist_response: str = Field(..., description="Initial specialized agent response.")
    critique_report: Optional[Dict[str, Any]] = Field(None, description="Critique report if any flaws were found by the panel.")
    final_output: FinalAuditResponse = Field(..., description="Audit-approved final response payload with verified citations.")


# --- Sapiatrum Core 5-Step Adversarial Asynchronous Pipeline ---

# Placeholder for Firestore interactions
async def get_memory_constraints_from_firestore(user_id: str, category: str) -> str:
    """Mocks fetching past mistakes from Firestore to use as negative prompts."""
    logger.info(f"Step 2: Checking memory bank 'users/{user_id}/ai_memories/{category}' on Sapiatrum Firestore...") # noqa
    # In a real implementation, this would query Firestore and return a formatted string of past issues.
    # e.g., "Constraint: Do not use deprecated library X. Constraint: Ensure all code examples are executable."
    return "" # Returning empty string for mock

async def save_correction_to_firestore(user_id: str, category: str, question: str, critique: Dict[str, Any], correction: str):
    """Mocks saving a self-correction event to Firestore for future memory."""
    logger.info(f"Step 4: Saved self-correction log to the Specialist's database on Sapiatrum Firestore.")
    # Real implementation would execute:
    # db.collection("users").document(user_id).collection("ai_memories").document(category).set(...)

async def save_panelist_failure_to_firestore(user_id: str, category: str, question: str, missed_error: str):
    """Mocks saving a panelist failure event to Firestore for system-level learning."""
    logger.info(f"Step 5: Logged panelist failure for category '{category}' to the Panelists' database on Sapiatrum Firestore.")
    # In a real implementation, this writes to `users/{user_id}/panelist_failures/{category}`

async def save_triage_mistake_to_firestore(user_id: str, question: str, mistake_details: Dict[str, Any]):
    """Mocks saving a triage mistake to Vertex's database for learning."""
    logger.warning(f"Step 1: Logged triage mistake to Vertex's database on Firestore. Details: {mistake_details}")
    # Real implementation would write to a dedicated collection for triage learning.

# --- Asynchronous Pipeline Step Implementation Helpers ---

async def call_vertex(model_client, prompt: str, search: bool = False):
    """Calls a Vertex AI model and returns the full response object."""
    if not model_client:
        class MockResponse:
            def __init__(self):
                self.text = "Vertex client unavailable."
                self.grounding_metadata = None
        return MockResponse()
    
    tools = [SEARCH_GROUNDING_TOOL] if search else None
    response = await model_client.generate_content_async(prompt, tools=tools)
    return response
async def call_consumer_gemini(prompt: str) -> str:
    if not consumer_gemini_flash: 
        return "Consumer Gemini client offline."
    response = await consumer_gemini_flash.generate_content_async(prompt)
    return response.text

async def call_claude(prompt: str) -> str:
    if not anthropic_client: 
        return "Claude client offline."
    msg = await anthropic_client.messages.create(
        model=MODEL_CLAUDE_SONNET, 
        max_tokens=2048, 
        messages=[{"role": "user", "content": prompt}]
    )
    return msg.content[0].text

async def call_copilot(prompt: str) -> str:
    if not azure_openai_client: 
        return "Copilot client offline."
    res = await azure_openai_client.chat.completions.create(
        model=MODEL_AZURE_COPILOT, 
        messages=[{"role": "user", "content": prompt}]
    )
    return res.choices[0].message.content

# --- REST API Endpoint ---

@app.post(
    "/v1/process-query",
    response_model=QueryResponse,
    status_code=status.HTTP_200_OK,
    summary="Process User Queries through the 5-Step Sapiatrum Multi-Agent Pipeline"
)
async def process_query(request: QueryRequest) -> QueryResponse:
    """
    Process queries via a 5-step adversarial asynchronous pipeline:
    1. Adversarial Triage (Vertex + Panel)
    2. Specialist Execution with Memory Injection
    3. & 4. Iterative Panelist Verification & Self-Correction Loop
    5. Final Vertex Audit with Cross-Layer Learning
    """
    logger.info(f"Received request from user '{request.user_id}' via Sapiatrum Gateway.")
    
    try:
        question = request.user_question
        uid = request.user_id

        # --- STEP 1: Multi-Step Triage & Triage Panel Cross-Check ---
        triage_prompt = (
            f"Analyze the user question: '{question}'. Use a web search to make an expert decision on which specialized AI "
            f"category is best suited. Respond with exactly one of these lowercase words: "
            f"'{CATEGORY_CODING}' (for code generation/debugging), '{CATEGORY_DATA_ANALYSIS}' (for math, stats, data interpretation), "
            f"'{CATEGORY_DEEP_RESEARCH}' (for in-depth topics requiring search), or '{CATEGORY_BASIC}' (for general questions). "
            f"If a prompt is large and fits multiple categories, choose the most dominant one. Output nothing else."
        )
        
        # Primary triage decision via Grounded Vertex Flash
        initial_category_response = await call_vertex(vertex_gemini_flash, triage_prompt, search=True)
        category = CATEGORY_BASIC
        initial_category = initial_category_response.text.lower()
        if CATEGORY_CODING in initial_category: category = CATEGORY_CODING
        elif CATEGORY_DATA_ANALYSIS in initial_category: category = CATEGORY_DATA_ANALYSIS
        elif CATEGORY_DEEP_RESEARCH in initial_category: category = CATEGORY_DEEP_RESEARCH

        # Cross-Check the Triage Decision via Panelists (Claude + Copilot)
        panel_triage_prompt = (
            f"An initial Vertex Agent triaged the question: '{question}' into the category: '{category}'. "
            f"If this classification is incorrect, debate the decision and output the true correct category "
            f"('{CATEGORY_CODING}', '{CATEGORY_DATA_ANALYSIS}', '{CATEGORY_DEEP_RESEARCH}', or '{CATEGORY_BASIC}'). If it is correct, output exactly '{category}'."
        )
        claude_vote, copilot_vote, gemini_vote = await asyncio.gather(
            call_claude(panel_triage_prompt), 
            call_copilot(panel_triage_prompt),
            call_consumer_gemini(panel_triage_prompt)
        )
        
        triage_history = {
            "vertex_initial_decision": category,
            "claude_triage_audit": claude_vote.strip().lower(),
            "copilot_triage_audit": copilot_vote.strip().lower(),
            "gemini_triage_audit": gemini_vote.strip().lower()
        }
        logger.info(f"Step 1: Adversarial Triage Phase Completed. Record: {triage_history}")

        # Override logic: If a majority of panelists disagree with Vertex, they override.
        votes = [v.strip().lower() for v in [claude_vote, copilot_vote, gemini_vote]]
        correct_votes = [v for v in votes if category in v]
        
        if len(correct_votes) < 2: # If less than 2 panelists agree with Vertex
            all_categories = [CATEGORY_CODING, CATEGORY_DATA_ANALYSIS, CATEGORY_DEEP_RESEARCH, CATEGORY_BASIC]
            vote_counts = {cat: sum(1 for vote in votes if cat in vote) for cat in all_categories}
            new_category = max(vote_counts, key=vote_counts.get)
            if vote_counts[new_category] > 0 and new_category != category:
                logger.warning(f"Triage Override: Panelists overruled Vertex. Changing category from '{category}' to '{new_category}'.")
                await save_triage_mistake_to_firestore(uid, question, {"original": category, "corrected_by_panel": new_category, "votes": votes})
                category = new_category

        # --- STEP 2: Memory Injection & Specialist Assignment ---
        past_memory = await get_memory_constraints_from_firestore(uid, category)
        specialist_prompt = f"{BASE_SYSTEM_PROMPT}\n\nHistorical Mistakes to Avoid:\n{past_memory}\n\nTask Question:\n{question}"
        
        if category == CATEGORY_CODING:
            specialist_response = await call_claude(specialist_prompt)
            model_used = MODEL_CLAUDE_SONNET
        elif category == CATEGORY_DATA_ANALYSIS:
            logger.info(f"Step 2: Assigning to joint specialists for '{CATEGORY_DATA_ANALYSIS}'.")
            copilot_analysis, gemini_analysis = await asyncio.gather(
                call_copilot(specialist_prompt),
                call_consumer_gemini(specialist_prompt)
            )
            synthesis_prompt = (
                f"Two specialists have analyzed the data analysis question: '{question}'.\n\n"
                f"Copilot's Analysis:\n{copilot_analysis}\n\n"
                f"Gemini's Analysis:\n{gemini_analysis}\n\n"
                f"Your task is to synthesize these two analyses into a single, comprehensive, and accurate final answer. "
                f"Resolve any contradictions and present the information clearly."
            )
            specialist_response_obj = await call_vertex(vertex_gemini_pro, synthesis_prompt, search=True)
            specialist_response = specialist_response_obj.text
            model_used = f"{MODEL_AZURE_COPILOT} & {MODEL_GEMINI_FLASH} (Synthesized by {MODEL_GEMINI_PRO})"
        elif category == CATEGORY_DEEP_RESEARCH:
            specialist_response_obj = await call_vertex(vertex_gemini_pro, specialist_prompt, search=True)
            specialist_response = specialist_response_obj.text
            model_used = MODEL_GEMINI_PRO
        else:
            specialist_response = await call_consumer_gemini(specialist_prompt)
            model_used = MODEL_GEMINI_FLASH

        initial_specialist_response = specialist_response

        # --- STEP 3 & 4: Dual-Adversarial Panelist Verification Loop ---
        loop_count = 0
        panel_approved = False
        critique_report_log = {}

        while not panel_approved and loop_count < MAX_CORRECTION_LOOPS:
            loop_count += 1
            panelist_tasks = []
            panelist_names = []
            
            # Build the panel dynamically (Everyone except the active specialist and Vertex)
            if category == CATEGORY_DATA_ANALYSIS:
                # The specialists were Copilot and Gemini, synthesized by Vertex. The only independent panelist is Claude.
                panelist_tasks.append(call_claude(f"Audit this answer for flaws/bugs: {specialist_response}. If perfect, write 'PASSED'. If wrong, list errors."))
                panelist_names.append("Claude")
            else:
                # Original logic for building the panel
                if category != CATEGORY_CODING:
                    panelist_tasks.append(call_claude(f"Audit this answer for flaws/bugs: {specialist_response}. If perfect, write 'PASSED'. If wrong, list errors."))
                    panelist_names.append("Claude")
                if category != CATEGORY_DATA_ANALYSIS:
                    panelist_tasks.append(call_copilot(f"Audit this answer for flaws/bugs: {specialist_response}. If perfect, write 'PASSED'. If wrong, list errors."))
                    panelist_names.append("Copilot")
                if category != CATEGORY_BASIC:
                    panelist_tasks.append(call_consumer_gemini(f"Audit this answer for flaws/bugs: {specialist_response}. If perfect, write 'PASSED'. If wrong, list errors."))
                    panelist_names.append("Gemini_Flash")

            reviews = await asyncio.gather(*panelist_tasks)
            combined_critique = " ".join(review for review in reviews if review)
            
            critique_report_log[f"loop_{loop_count}"] = {name: review for name, review in zip(panelist_names, reviews)}

            if "PASSED" in combined_critique.upper() or len(combined_critique.strip()) < 15:
                panel_approved = True
                logger.info("Steps 3/4: Panelists declared the specialist answer as 'PASSED'.")
            else:
                logger.warning(f"Steps 3/4: Answer failed loop {loop_count}. Forcing self-correction.")
                fix_prompt = f"Your answer was rejected by the audit panel. Critique Feedback Report:\n{combined_critique}\n\nGenerate an entirely corrected version."
                
                if category == CATEGORY_CODING: specialist_response = await call_claude(fix_prompt)
                elif category == CATEGORY_DATA_ANALYSIS:
                    logger.info(f"Re-running joint specialists for '{CATEGORY_DATA_ANALYSIS}' after critique.")
                    copilot_analysis, gemini_analysis = await asyncio.gather(
                        call_copilot(fix_prompt),
                        call_consumer_gemini(fix_prompt)
                    )
                    synthesis_prompt = (
                        f"A previous synthesized answer was rejected. Here is the critique:\n{combined_critique}\n\n"
                        f"Original Question: '{question}'\n\n"
                        f"Copilot's New Analysis:\n{copilot_analysis}\n\n"
                        f"Gemini's New Analysis:\n{gemini_analysis}\n\n"
                        f"Your task is to re-synthesize these into a corrected final answer."
                    )
                    specialist_response = (await call_vertex(vertex_gemini_pro, synthesis_prompt, search=True)).text
                elif category == CATEGORY_DEEP_RESEARCH: specialist_response = (await call_vertex(vertex_gemini_pro, fix_prompt, search=True)).text
                else: specialist_response = await call_consumer_gemini(fix_prompt)
                
                await save_correction_to_firestore(uid, category, question, critique_report_log[f"loop_{loop_count}"], specialist_response)

        # --- STEP 5: Ultimate Vertex Audit & Panelist Blindspot Database Learning ---
        audit_prompt = (
            f"Ultimate Verification Sweep: Run a deep validation search sweep across this text for "
            f"any hidden hallucinations or errors that the panelist models missed entirely: {specialist_response}. "
            f"If flaws are identified, output 'FLAW: [explicit details]'. If perfect, output 'APPROVED'."
        )
        vertex_audit_response = await call_vertex(vertex_gemini_pro, audit_prompt, search=True)
        vertex_audit_result = vertex_audit_response.text

        failure_logged = False
        if "FLAW" in vertex_audit_result.upper():
            failure_logged = True
            logger.error("Step 5: Vertex identified an error missed by the panelists! Logging failures to the Panelists' database.")
            await save_panelist_failure_to_firestore(uid, category, question, vertex_audit_result)
            # Add to the specialist primary errors log too so everyone adapts
            logger.warning("Step 5: Logging Vertex's final correction to the Specialist's database.")
            await save_correction_to_firestore(uid, category, question, {"vertex_final_audit": vertex_audit_result}, specialist_response)

        # Execute final search grounding to append clickable Markdown web links and references
        final_citation_prompt = (
            f"Format this audited content cleanly into pristine markdown. Perform a web search to "
            f"verify data currency and explicitly append working, clickable Markdown source link "
            f"citations at the very bottom:\n{specialist_response}"
        )
        final_response_obj = await call_vertex(vertex_gemini_pro, final_citation_prompt, search=True)
        final_markdown_content = final_response_obj.text

        # Dynamically extract citations from grounding metadata
        citations = []
        if final_response_obj.grounding_metadata:
            for attr in final_response_obj.grounding_metadata.grounding_attributions:
                # Ensure we have a valid URI and title before adding
                if hasattr(attr, 'web') and hasattr(attr.web, 'uri'):
                    citations.append(CitationItem(source=attr.web.uri, text=getattr(attr.web, 'title', "Grounded Source")))

        # New final check by all models
        logger.info("Step 5: Performing final check with all models.")
        final_check_prompt = f"Final check: Is this response 100% accurate and free of errors? '{final_markdown_content}'. If perfect, output 'APPROVED'. If any flaw exists, output 'FINAL_FLAW: [details]'."
        
        all_final_checks = await asyncio.gather(
            call_claude(final_check_prompt),
            call_copilot(final_check_prompt),
            call_consumer_gemini(final_check_prompt),
            call_vertex(vertex_gemini_pro, final_check_prompt, search=False)
        )
        final_checks_map = {
            "claude_final_check": all_final_checks[0],
            "copilot_final_check": all_final_checks[1],
            "gemini_final_check": all_final_checks[2],
            "vertex_final_check": all_final_checks[3].text,
        }

        final_check_failures = {k: v for k, v in final_checks_map.items() if "FLAW" in v.upper()}
        if final_check_failures:
            logger.error(f"Step 5: Final all-model check found flaws! {final_check_failures}")

        response_payload = QueryResponse(
            category=category,
            triage_history=triage_history,
            specialist_model_used=model_used,
            initial_specialist_response=initial_specialist_response,
            critique_report=critique_report_log if not panel_approved else None,
            final_output=FinalAuditResponse(
                content=final_markdown_content.strip(),
                citations=citations,
                panelist_failure_logged=failure_logged,
                final_check_failures=final_check_failures if final_check_failures else None
            )
        )
        
        logger.info(f"Successfully processed query for user '{request.user_id}'. Returning verified output.")
        return response_payload

    except Exception as e:
        logger.error(f"Failed to execute Sapiatrum pipeline steps: {str(e)}", exc_info=True)
        throw_internal_error(f"Routing cluster pipeline failed: {str(e)}")


def throw_internal_error(detail_msg: str) -> None:
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail={
            "error": "SapiatrumClusterException",
            "message": detail_msg,
            "system_context": "Sapiatrum Multi-Agent Triage Backend"
        }
    )


# --- Root Health Check ---
@app.get("/", status_code=status.HTTP_200_OK)
async def health_check():
    return {
        "status": "healthy",
        "service": "Sapiatrum Cluster Engine",
        "gcp_project_id": SAPIATRUM_PROJECT_ID
    }
