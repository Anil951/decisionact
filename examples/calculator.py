"""Live calculator example: python -m examples.calculator [message].

Example: "divide 5 by 2, multiply the result by 4, subtract 3 from that result,
then add 1 to the result".
"""
# Query guide: intended tool traces and replies, not a claim that every live run
# passes. Decisions are probabilistic; inspect tool_calls and decisions in the
# printed JSON. Independent calculations execute separately; the done template
# displays the LAST result, not a list of all intermediate answers.
#
# Basic and repeated operations:
# - "Add 4+5" -> add(4, 5)=9 -> "Result: 9".
# - "Add 4+5 and add 6+7" -> add(4, 5)=9; add(6, 7)=13
#   -> "Result: 13". The trace contains both results.
# - "Add 4+5 and add 4+5 again" / "Add 4+5 twice"
#   -> add(4, 5)=9; add(4, 5)=9 -> "Result: 9".
# - "Add 4+5, then add 4+7" -> add(4, 5)=9; add(4, 7)=11
#   -> "Result: 11". Reusing 4 is valid; do not add the two results.
# - "First subtract 3 from 10, then subtract 4 from 20"
#   -> subtract(10, 3)=7; subtract(20, 4)=16 -> "Result: 16".
# - "Multiply 2 by 3, then multiply 4 by 5"
#   -> multiply(2, 3)=6; multiply(4, 5)=20 -> "Result: 20".
# - "Divide 8 by 2, then divide 9 by 3"
#   -> divide(8, 2)=4; divide(9, 3)=3 -> "Result: 3".
# - "Divide 8 by 2 twice, as two separate independent calculations"
#   -> divide(8, 2)=4; divide(8, 2)=4 -> "Result: 4".
#
# Dependencies, operand order and combining earlier results:
# - "Add 4+5, then add the result to 7"
#   -> add(4, 5)=9; add(9, 7)=16 -> "Result: 16".
# - "Add 4+5, and then add 6"
#   -> add(4, 5)=9; add(9, 6)=15 -> "Result: 15"
#   when the second addition refers to the running result.
# - "Add 4+5, add 6 to the result, then add 7 to that result"
#   -> add(4, 5)=9; add(9, 6)=15; add(15, 7)=22 -> "Result: 22".
# - "Divide 8 by 2, then divide the result by 2"
#   -> divide(8, 2)=4; divide(4, 2)=2 -> "Result: 2".
# - "Divide 5 by 2, multiply the result by 4, subtract 3 from that result,
#   then add 1 to the result" -> divide(5, 2)=2.5; multiply(2.5, 4)=10;
#   subtract(10, 3)=7; add(7, 1)=8 -> "Result: 8".
# - "First add 4 and 5. Next subtract 3 from 10. Next multiply 2 by 6.
#   Finally divide 20 by 4" -> add(4, 5)=9; subtract(10, 3)=7;
#   multiply(2, 6)=12; divide(20, 4)=5 -> "Result: 5".
# - "Add 2+3, multiply that result by 4, add 7 to that result, then divide
#   the result by 3" -> add(2, 3)=5; multiply(5, 4)=20;
#   add(20, 7)=27; divide(27, 3)=9 -> "Result: 9".
# - "First subtract 3 from 10. Next multiply 2 by 4. Finally divide the first
#   result by the second result" -> subtract(10, 3)=7; multiply(2, 4)=8;
#   divide(7, 8)=0.875 -> "Result: 0.875".
# - "Subtract 10 from 3, then subtract that result from 20"
#   -> subtract(3, 10)=-7; subtract(20, -7)=27 -> "Result: 27".
# - "Divide 3 by 12, then divide 2 by that result"
#   -> divide(3, 12)=0.25; divide(2, 0.25)=8 -> "Result: 8".
#
# Numeric forms:
# - "Add -4+5, then add the result to 0"
#   -> add(-4, 5)=1; add(1, 0)=1 -> "Result: 1".
# - "Multiply -2.5 by 4, then divide the result by -2"
#   -> multiply(-2.5, 4)=-10; divide(-10, -2)=5 -> "Result: 5".
# - "Multiply 1e-3 by 2e-3, then divide the result by 2"
#   -> multiply(0.001, 0.002)=0.000002; divide(0.000002, 2)=0.000001.
#   The printed reply can use Python's scientific notation: "Result: 1e-06".
#
# Missing, ambiguous and invalid inputs:
# - "Add 4+5, then multiply the result by an unknown number. Ask me for that
#   number" -> add(4, 5)=9; ask for the multiplier; no multiply yet.
# - "Add 4+5 and multiply 2 by 6, then divide one of those results by 3"
#   -> add(4, 5)=9; multiply(2, 6)=12; ask which result; no divide yet.
# - "Add 4+5 and add 6+7, then add one of those results to 8"
#   -> add(4, 5)=9; add(6, 7)=13; ask which result; no final add yet.
# - "Divide 5 by 0" -> divide(5, 0) returns an error. Report
#   "Calculation failed: Cannot divide by zero." or ask for a valid divisor
#   through input repair; never silently replace 0 with another number.
# - "Add 4+5, then divide that result by 0, then multiply the result by 3"
#   -> add(4, 5)=9; divide(9, 0) returns an error; report the error or ask
#   for a valid divisor. Do not multiply an unsuccessful division result.
# Clarification wording comes from the framework; low confidence outside input
# resolution can instead produce "Could you rephrase?". These are incomplete
# flows, not successful calculations. A tool effect can precede a fallback.
#
# Call allowances (configure with make_agent(model, max_calls=..., ...)):
# - Six-step chain: "Add 2+3, multiply the result by 2, subtract 4 from that
#   result, divide that result by 3, add 8 to the result, then divide that
#   result by 2" -> add(2, 3)=5; multiply(5, 2)=10; subtract(10, 4)=6;
#   divide(6, 3)=2; add(2, 8)=10; divide(10, 2)=5 -> "Result: 5".
# - Append "then multiply that result by 3" to the six-step chain:
#   after call 6, a continuation Noul may grant the next allowance;
#   multiply(5, 3)=15 -> "Result: 15". Default hard cap: 24 executions.
# - With max_calls=2: "First add 4 and 5. Next subtract 3 from 10. Finally
#   multiply 2 by 6" -> add(4, 5)=9; subtract(10, 3)=7; allowance check;
#   multiply(2, 6)=12 -> "Result: 12" if continuation is granted.
# - With max_calls=2, max_call_limit=3: the four independent tools query
#   above runs add, subtract and multiply, then returns outcome limit_reached,
#   limit_reason=hard_limit and an unfinished-work reply; divide must not run.
# - A declined allowance extension returns limit_reached with
#   limit_reason=continuation_declined; it must not report the task as done.
#
# Framework-only test fixtures also simulated a tool rejecting operand 5 with
# an explicit fallback 7, a service failure, and paused/approval continuation.
# Those fixtures are not behaviors of these four arithmetic functions. They
# check bounded retries, preservation of sibling inputs and execution counts.
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from decisionact import Agent, Intent, Outcome, Param, tool
from decisionact.models import SystemOneModel


NUMBER = r"-?(?:\d+(?:\.\d+)?|\.\d+)(?:[eE][+-]?\d+)?"


def _result(value):
    """Keep whole-number results readable while allowing fractional dependencies."""
    return {"result": int(value) if value.is_integer() else value}


@tool(a=Param(desc="The first operand of the next unfinished addition", pattern=NUMBER),
      b=Param(desc="The second operand of that same addition", pattern=NUMBER))
def add(a, b):
    """Add two numbers: a + b. Call once per requested addition."""
    return _result(float(a) + float(b))


@tool(a=Param(desc="The number to subtract from (the minuend)", pattern=NUMBER),
      b=Param(desc="The number to subtract from a (the subtrahend)", pattern=NUMBER))
def subtract(a, b):
    """Subtract b from a: a - b. 'Subtract 3 from 10' means a=10, b=3."""
    return _result(float(a) - float(b))


@tool(a=Param(desc="The first factor of the next unfinished multiplication", pattern=NUMBER),
      b=Param(desc="The second factor of that same multiplication", pattern=NUMBER))
def multiply(a, b):
    """Multiply two numbers: a * b. Call once per requested multiplication."""
    return _result(float(a) * float(b))


@tool(a=Param(desc="The number being divided (the dividend)", pattern=NUMBER),
      b=Param(desc="The number to divide a by (the divisor)", pattern=NUMBER))
def divide(a, b):
    """Divide a by b: a / b. The divisor b must not be zero."""
    divisor = float(b)
    if divisor == 0:
        raise ValueError("Cannot divide by zero.")
    return _result(float(a) / divisor)


def make_agent(model, **kwargs):
    return Agent(
        tools=[add, subtract, multiply, divide],
        intents={"calculate": Intent(
            "Perform requested additions, subtractions, multiplications, and divisions",
            context=(
                "Four arithmetic tools are available:\n"
                "- add(a, b): return a + b; call for addition.\n"
                "- subtract(a, b): return a - b; call to subtract b from a.\n"
                "- multiply(a, b): return a * b; call for multiplication.\n"
                "- divide(a, b): return a / b; call to divide a by b.\n"
                "All tools take two numeric operands, a and b."
            ),
            tools=["add", "subtract", "multiply", "divide"], outcomes=["done", "failed"])},
        outcomes={"done": Outcome("All requested arithmetic operations succeeded", "Result: {result}"),
                  "failed": Outcome("An arithmetic operation failed", "Calculation failed: {error}")},
        model=model, **kwargs)


def main():
    root = Path(__file__).resolve().parents[1]
    load_dotenv(root / ".env")
    load_dotenv(root.parent / ".env")

    agent = make_agent(SystemOneModel(api_key=os.getenv("TYPESAFE_API_KEY")))
    message = " ".join(sys.argv[1:]) or (
        "divide 5 by 2, multiply the result by 4, subtract 3 from that result, "
        "then add 1 to the result")
    result = agent.turn(message)
    print(json.dumps({"message": message, "outcome": result.outcome, "reply": result.reply,
                      "tool_calls": result.tool_calls, "decisions": result.decisions}, indent=2))


if __name__ == "__main__":
    main()
