"""Manual spot-check for the Policy Parser against the real Groq API.

Run from repo root:
    uv run python scripts/spot_check_parser.py
"""

from complyagent.agents.parser import parse_policy


SAMPLE_POLICY = """We collect your name, email address, and IP address when you register for an account.
We use this information to provide our services and to send you marketing communications.
We share your data with third-party analytics providers and advertising partners.
You may request deletion of your account by contacting our support team.
We retain your data for 24 months after account closure."""


def main():
    print("Parsing sample policy...\n")
    statements = parse_policy(SAMPLE_POLICY)

    print(f"Extracted {len(statements)} statements:\n")
    for s in statements:
        print(f"  [{s.statement_id}] ({s.category.value})")
        print(f"    text:        {s.text}")
        print(f"    source_span: {s.source_span}")
        print()

    print("Short-circuit check (empty input):")
    print(f"  parse_policy('') -> {parse_policy('')}")
    print(f"  parse_policy('hi') -> {parse_policy('hi')}")


if __name__ == "__main__":
    main()