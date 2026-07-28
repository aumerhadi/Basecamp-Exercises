"""
Email Processing Agent using Claude 4.6

This agent receives email data in JSON format and processes it to:
- Summarize the email
- Classify the type (request, question, issue, meeting request, or other)
- Extract keywords
- Define priority as text (high, medium, low)
- Return structured JSON output

Input format:
{
    "from": "sender@example.com",
    "to": "recipient@example.com",
    "subject": "Email subject",
    "body": "Email body content",
    "priority": "1-5 or low/medium/high",
    "date": "YYYY-MM-DD",
    "time": "HH:MM:SS"
}

Output format:
{
    "summary": "Brief summary of the email",
    "type": "request|question|issue|meeting_request|other",
    "keywords": ["keyword1", "keyword2", ...],
    "priority": "high|medium|low",
    "reasoning": "Explanation of the classification"
}

Usage:
    export ANTHROPIC_API_KEY="sk-ant-..."
    python emailProcessing.py --email-json '{"from": "...", ...}'

Or use as a module:
    from emailProcessing import EmailProcessor
    processor = EmailProcessor(api_key="sk-ant-...")
    result = processor.process_email(email_data)
"""

import json
import os
import argparse
from pathlib import Path
from typing import Dict, Any

from anthropic import Anthropic


EMAIL_PROCESSOR_SYSTEM = """\
You are an Email Processing Agent. Your job is to analyze emails and provide structured output.

For each email you receive, you must:

1. **Summarize** - Create a concise 1-2 sentence summary of the email's main point
2. **Classify Type** - Determine if the email is:
   - request: Asks for something to be done or provided
   - question: Seeks information or clarification
   - issue: Reports a problem, bug, or concern
   - meeting_request: Proposes or schedules a meeting
   - other: Informational, updates, or doesn't fit above categories
3. **Extract Keywords** - Identify 3-7 key terms that capture the main topics
4. **Define Priority** - Assess urgency as:
   - high: Requires immediate attention, time-sensitive, critical
   - medium: Important but can wait, normal business priority
   - low: Informational, no rush, nice-to-have
5. **Provide Reasoning** - Explain why you classified it this way

Be objective and base your analysis on:
- Explicit urgency indicators (URGENT, ASAP, deadline dates)
- Sender's stated needs and expectations
- Impact and scope of the request/issue
- Time sensitivity mentioned in the content

Return your analysis as a JSON object with this exact structure:
{
    "summary": "string",
    "type": "request|question|issue|meeting_request|other",
    "keywords": ["array", "of", "strings"],
    "priority": "high|medium|low",
    "reasoning": "string explaining your classification"
}
"""


class EmailProcessor:
    """Email processing agent using Claude 4.6"""

    def __init__(self, api_key: str = None):
        """
        Initialize the email processor.

        Args:
            api_key: Anthropic API key. If None, reads from ANTHROPIC_API_KEY env var
        """
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY must be set or passed as argument")

        self.client = Anthropic(api_key=self.api_key)
        self.model = "claude-sonnet-4-6"

    def process_email(self, email_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process an email and return structured analysis.

        Args:
            email_data: Dictionary containing email fields (from, to, subject, body, etc.)

        Returns:
            Dictionary with summary, type, keywords, priority, and reasoning
        """
        # Validate required fields
        required_fields = ["from", "to", "subject", "body"]
        missing = [f for f in required_fields if f not in email_data]
        if missing:
            raise ValueError(f"Missing required fields: {missing}")

        # Format email data for the agent
        email_text = self._format_email(email_data)

        # Call Claude 4.6 with structured output request
        message = self.client.messages.create(
            model=self.model,
            max_tokens=2000,
            system=EMAIL_PROCESSOR_SYSTEM,
            messages=[
                {
                    "role": "user",
                    "content": f"Analyze this email and return your analysis as JSON:\n\n{email_text}"
                }
            ]
        )

        # Extract the response
        response_text = message.content[0].text

        # Parse JSON from response
        try:
            # Try to find JSON in the response
            result = self._extract_json(response_text)

            # Validate the structure
            self._validate_output(result)

            return result
        except (json.JSONDecodeError, ValueError) as e:
            raise ValueError(f"Failed to parse agent response as JSON: {e}\nResponse: {response_text}")

    def _format_email(self, email_data: Dict[str, Any]) -> str:
        """Format email data into readable text for the agent."""
        parts = [
            f"From: {email_data['from']}",
            f"To: {email_data['to']}",
            f"Subject: {email_data['subject']}",
        ]

        if "date" in email_data:
            parts.append(f"Date: {email_data['date']}")
        if "time" in email_data:
            parts.append(f"Time: {email_data['time']}")
        if "priority" in email_data:
            parts.append(f"Original Priority: {email_data['priority']}")

        parts.append(f"\nBody:\n{email_data['body']}")

        return "\n".join(parts)

    def _extract_json(self, text: str) -> Dict[str, Any]:
        """Extract JSON from response text that might contain markdown code blocks."""
        # Try to parse as-is first
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Try to extract from markdown code block
        if "```json" in text:
            start = text.find("```json") + 7
            end = text.find("```", start)
            if end != -1:
                return json.loads(text[start:end].strip())
        elif "```" in text:
            start = text.find("```") + 3
            end = text.find("```", start)
            if end != -1:
                return json.loads(text[start:end].strip())

        # Try to find JSON object in text
        start = text.find("{")
        end = text.rfind("}") + 1
        if start != -1 and end > start:
            return json.loads(text[start:end])

        raise json.JSONDecodeError("No JSON found in response", text, 0)

    def _validate_output(self, result: Dict[str, Any]) -> None:
        """Validate the output structure."""
        required = ["summary", "type", "keywords", "priority", "reasoning"]
        missing = [f for f in required if f not in result]
        if missing:
            raise ValueError(f"Missing fields in output: {missing}")

        valid_types = ["request", "question", "issue", "meeting_request", "other"]
        if result["type"] not in valid_types:
            raise ValueError(f"Invalid type: {result['type']}. Must be one of {valid_types}")

        valid_priorities = ["high", "medium", "low"]
        if result["priority"] not in valid_priorities:
            raise ValueError(f"Invalid priority: {result['priority']}. Must be one of {valid_priorities}")

        if not isinstance(result["keywords"], list):
            raise ValueError("Keywords must be an array")


def main():
    """Command-line interface for the email processor."""
    parser = argparse.ArgumentParser(description="Process emails with Claude 4.6")
    parser.add_argument(
        "--email-json",
        type=str,
        help="Email data as JSON string"
    )
    parser.add_argument(
        "--email-file",
        type=str,
        help="Path to JSON file containing email data"
    )
    parser.add_argument(
        "--output",
        type=str,
        help="Path to save output JSON (default: print to stdout)"
    )

    args = parser.parse_args()

    # Load email data
    if args.email_json:
        email_data = json.loads(args.email_json)
    elif args.email_file:
        email_data = json.loads(Path(args.email_file).read_text())
    else:
        # Example email for testing
        email_data = {
            "from": "client@example.com",
            "to": "support@company.com",
            "subject": "URGENT: Production server down",
            "body": "Our production server has been down for 2 hours. We need immediate assistance. This is affecting all our users and costing us revenue. Please call me ASAP at 555-1234.",
            "priority": "high",
            "date": "2026-07-28",
            "time": "14:30:00"
        }
        print("No input provided. Using example email:\n")
        print(json.dumps(email_data, indent=2))
        print("\n" + "="*60 + "\n")

    # Process email
    processor = EmailProcessor()
    result = processor.process_email(email_data)

    # Output results
    output_json = json.dumps(result, indent=2)

    if args.output:
        Path(args.output).write_text(output_json)
        print(f"Results saved to {args.output}")
    else:
        print("Email Analysis Results:\n")
        print(output_json)


if __name__ == "__main__":
    main()
