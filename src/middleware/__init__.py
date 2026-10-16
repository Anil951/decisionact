"""Middleware: hooks into the steps of a turn. Pass a list to Agent(..., middleware=[...]).

  HumanInTheLoopMiddleware(approvals={...})   a person approves or rejects chosen tool calls
                                              before they run: the user types /approve or
                                              /reject [reason] and agent.turn() handles it

To write your own, subclass Middleware and override a hook (before_tool, answer_interrupt).
"""
from .base import Interrupt, Middleware
from .humanintheloop import (Approval, Decision, HumanInTheLoopMiddleware, PendingApproval,
                             approve, parse_command, reject)

__all__ = ["Middleware", "Interrupt", "HumanInTheLoopMiddleware", "Approval", "Decision",
           "approve", "reject", "parse_command", "PendingApproval"]
