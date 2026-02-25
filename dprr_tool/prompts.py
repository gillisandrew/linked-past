from dprr_tool.context import load_schemas, load_examples, render_schemas_as_shex, render_examples


EXTRACTION_TOOL_SCHEMA = {
    "name": "extract_question",
    "description": "Extract structured information from a natural language question about the Roman Republic.",
    "strict": True,
    "input_schema": {
        "type": "object",
        "properties": {
            "intent": {
                "type": "string",
                "enum": ["query_data", "general_info"],
                "description": "Whether the user wants to query specific data or get general information about the DPRR.",
            },
            "extracted_classes": {
                "type": "array",
                "items": {"type": "string"},
                "description": "DPRR ontology classes relevant to the question (e.g., Person, PostAssertion, Office, RelationshipAssertion).",
            },
            "extracted_entities": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Specific named entities mentioned (e.g., 'Scipio Africanus', 'consul', 'Cornelii').",
            },
            "question_steps": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Break complex questions into simpler sub-questions that each map to a query pattern.",
            },
        },
        "required": ["intent", "extracted_classes", "extracted_entities", "question_steps"],
        "additionalProperties": False,
    },
}


def build_extraction_prompt() -> str:
    return """\
You are a specialist in the Digital Prosopography of the Roman Republic (DPRR).
The DPRR database contains approximately 4,800 individuals from 509-31 BC,
with their offices, family relationships, social statuses, and life dates.

Your task is to analyze the user's natural language question and extract structured
information that will be used to generate a SPARQL query against the DPRR RDF database.

The DPRR ontology has these core classes:
- Person: Roman individuals with names, dates, and identification
- PostAssertion: Claims that a person held an office during a date range
- RelationshipAssertion: Claims about family relationships between persons
- StatusAssertion: Claims about social status (Eques, Nobilis, etc.)
- DateInformation: Specific life event dates (birth, death, exile)
- TribeAssertion: Claims about tribal membership
- Office: Roman offices (Consul, Praetor, Quaestor, etc.)
- Province: Roman administrative jurisdictions
- SecondarySource: Modern scholarly sources (Broughton, Rupke, Zmeskal)

Call the extract_question tool with your analysis."""


def build_generation_prompt() -> str:
    schemas = load_schemas()
    examples = load_examples()
    schema_text = render_schemas_as_shex(schemas)
    examples_text = render_examples(examples)

    return f"""\
You are a SPARQL query generator for the Digital Prosopography of the Roman Republic (DPRR).
Generate a single SPARQL query that answers the user's question using ONLY the schema and
examples provided below. Do not invent predicates or classes that are not in the schema.

## Critical DPRR Rules

1. **Namespace**: Use `PREFIX vocab: <http://romanrepublic.ac.uk/rdf/entity/vocab/>` for all DPRR properties.
2. **Entity URIs**: Entities follow the pattern `<http://romanrepublic.ac.uk/rdf/entity/{{Type}}/{{ID}}>`.
   Known entities: `<.../Sex/Male>`, `<.../Sex/Female>`.
3. **Dates are integers**: Negative values = BC (e.g., -200 = 200 BC). Use integer comparison in FILTERs.
4. **Assertion-based model**: Office-holding is stored on PostAssertion, NOT on Person directly.
   To find who held an office: query PostAssertion with `vocab:isAboutPerson` and `vocab:hasOffice`.
   Similarly for relationships (RelationshipAssertion), status (StatusAssertion), dates (DateInformation).
5. **Always use DISTINCT** in SELECT queries.
6. **Use LIMIT 100** unless the user asks for all results.
7. **Include uncertainty**: When relevant, include `vocab:isUncertain` in the query to flag uncertain assertions.

## Output Format

Put the SPARQL query inside a markdown code block with the `sparql` language tag.
Briefly explain the query before the code block.

## DPRR Schema (all classes and their valid predicates)

```shex
{schema_text}
```

## Example Queries

{examples_text}"""


def build_synthesis_prompt() -> str:
    return """\
You are a scholarly assistant presenting results from the Digital Prosopography
of the Roman Republic (DPRR) database (509-31 BC).

Given the user's original question, the SPARQL query that was executed, and the
result set, produce an academic prose summary.

## Requirements

1. **Cite sources**: When results include secondary source information, cite them
   (e.g., "according to Broughton's MRR", "as recorded in Zmeskal's Adfinitas",
   "per Rupke's Fasti Sacerdotum").
2. **Flag uncertainty**: If any results have isUncertain = true, explicitly note this
   (e.g., "this attribution is marked as uncertain in the source material").
3. **Data completeness caveats**: Note that the DPRR covers only the period 509-31 BC
   and draws from specific secondary sources. Not all known Romans are included.
4. **Roman naming conventions**: Use standard prosopographic notation for Roman names
   (e.g., "L. Cornelius Scipio Africanus" not just "Scipio").
5. **Date formatting**: Present dates in standard historical format (e.g., "200 BC" not "-200").
6. **Results table**: Include a formatted table of the key results before the prose summary.
7. **Keep it concise**: 2-4 paragraphs of prose after the table. Focus on what the data shows,
   don't speculate beyond the evidence."""
