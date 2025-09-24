"""
This module defines the Pydantic models for the tools that the LLM can call.

**Core Design Principle: LLM as an Indexer, not a Copier.**

To minimize expensive output tokens and ensure perfect content fidelity, the LLM
does not repeat the content it chunks. Instead, it references the content's
location using start and end line numbers from the input it received.

The backend tool implementation is responsible for:
1.  Preprocessing the input text to add line numbers.
2.  Receiving tool calls with line numbers.
3.  Extracting the original text based on these line numbers to store in the
    `Chunk.raw_content` field.
4.  Storing the optional `paraphrase` field only when the LLM needs to
    rewrite, redact, or purify the original content.
"""
from pydantic import BaseModel, Field
from typing import Optional, List

class CreateHeadingChunkTool(BaseModel):
    """
    Call this tool to create a new heading chunk. The heading text must be unique
    within the document.
    """
    class Config:
        title = "create_heading_chunk"

    parent_heading_text: Optional[str] = Field(
        default=None, 
        description="The text content of the parent heading. Use null for root-level headings."
    )
    level: int = Field(
        ..., 
        description="The heading level (e.g., 1 for H1, 2 for H2)."
    )
    heading_text: str = Field(
        ..., 
        description="The exact, normalized text content of the new heading."
    )
    start_line: int = Field(
        ...,
        gt=0,
        description="The positive, 1-indexed starting line number of the heading in the input text, relative to the entire document."
    )
    end_line: int = Field(
        ...,
        gt=0,
        description="The positive, 1-indexed ending line number of the heading in the input text, relative to the entire document. Must be >= start_line."
    )
    summary: str = Field(
        ..., 
        description="A brief, one-sentence summary of the heading's topic."
    )
    paraphrase: Optional[str] = Field(
        default=None,
        description="A unique, paraphrased version of the heading, useful for disambiguation if similar headings exist."
    )

class CreateContentChunkTool(BaseModel):
    """
    Call this tool to create a new content chunk under a specified parent heading
    by referencing its line numbers.
    """

    class Config:
        title = "create_content_chunk"

    parent_heading_text: Optional[str] = Field(
        default=None, 
        description="The text content of the parent heading this content belongs to. Use null for content that is not under any heading."
    )
    start_line: int = Field(
        ...,
        gt=0,
        description="The positive, 1-indexed starting line number of the content block in the input text, relative to the entire document."
    )
    end_line: int = Field(
        ...,
        gt=0,
        description="The positive, 1-indexed ending line number of the content block in the input text, relative to the entire document. Must be >= start_line."
    )
    summary: str = Field(
        ..., 
        description="A concise summary of the key information in the content chunk."
    )
    paraphrase: Optional[str] = Field(
        default=None,
        description="Use this field ONLY to provide a rewritten, redacted, or purified version of the original content. If null, the original content will be used."
    )


class IdentifyHeadingsTool(BaseModel):
    """
    Call this tool to identify all headings in the provided text block.
    This is the first step of the two-step chunking process.
    """
    
    class Config:
        title = "identify_headings"
    
    headings: List[dict] = Field(
        ...,
        description="List of all headings found in the text. Each heading should have: level (int), text (str), parent_text (Optional[str])"
    )


class GenerateContentSummaryTool(BaseModel):
    """
    Call this tool to generate summary and paraphrase for a content chunk.
    This is used in the second step of the two-step chunking process.
    """
    
    class Config:
        title = "generate_content_summary"
    
    start_line: int = Field(
        ...,
        gt=0,
        description="The starting line number of the content chunk"
    )
    end_line: int = Field(
        ...,
        gt=0,
        description="The ending line number of the content chunk"
    )
    summary: str = Field(
        ...,
        description="A concise summary of the key information in the content chunk"
    )
    paraphrase: Optional[str] = Field(
        default=None,
        description="Use this field ONLY to provide a rewritten, redacted, or purified version of the original content. If null, the original content will be used."
    )
