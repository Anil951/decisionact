"""Order-support agent built with DecisionAct: tools, intents, outcomes.
Run from the project folder: python -m examples.order_agent"""


import os
from pathlib import Path

from dotenv import load_dotenv

from decisionact import Agent, Intent, Outcome, Param, tool
# from decisionact.checkpoint import SqliteCheckpointer
from decisionact.models import CloudflareModel, SystemOneModel
from decisionact.memory import ConversationBufferMemory
from decisionact.middleware import Approval, HumanInTheLoopMiddleware


ORDERS = {  # fake data
    "A1234": {"item": "iPhone 11 Pro", "status": "placed"},
    "B5678": {"item": "Samsung Galaxy Watch 6", "status": "dispatched"},
    "C9012": {"item": "Sony WH-1000XM5 Headphones", "status": "delivered"},
}

# ======================= TOOLS =======================
ORDER_ID = Param(desc="one uppercase letter followed by four digits, e.g. A1234",
                 pattern=r"\b[A-Z]\d{4}\b")

CANCEL_REASON = Param(
    desc="why the user cancels, as one of four categories: changed mind, delivery delay, "
         "wrong item ordered, other",
    options={"changed mind": "The user no longer wants the order or changed their mind.",
             "delivery delay": "The delivery is late or taking too long.",
             "wrong item ordered": "The user ordered the wrong item, size, colour or quantity.",
             "other": "The user gives any other reason."})


@tool(order_id=Param(desc=ORDER_ID.desc, pattern=ORDER_ID.pattern, optional=True))
def get_order(order_id: str = None) -> dict:
    """Look up an order's item and status (placed, dispatched, delivered or cancelled).
    With an order ID: returns that order. Without an order ID: returns all orders.
    Needed to answer status questions and to check an order before cancelling it."""
    if order_id is None:
        return {"orders": [{"order_id": o, **d} for o, d in ORDERS.items()]}
    if order_id not in ORDERS:
        return {"error": f"order {order_id} not found"}
    return {"order_id": order_id, **ORDERS[order_id]}


@tool(order_id=ORDER_ID, reason=CANCEL_REASON)
def cancel_order(order_id: str, reason: str) -> dict:
    """Cancel an order that is placed or dispatched (not delivered or already cancelled),
    with the reason for cancelling."""
    if order_id not in ORDERS:
        return {"error": f"order {order_id} not found"}
    order = ORDERS[order_id]
    if order["status"] in ("delivered", "cancelled"):
        return {"error": f"order {order_id} is {order['status']} and can't be cancelled",
                "item": order["item"], "status": order["status"]}
    order["status"] = "cancelled"
    return {"order_id": order_id, "item": order["item"], "status": "cancelled", "reason": reason}


# ======================= INTENTS =======================
INTENTS = {
    "order_status": Intent(
        desc="The user wants to know about an existing order or see their orders: where it is, "
             "its status, whether it has shipped or arrived, or a list of their orders. "
             "Examples: 'where is my order', 'status of A1234', 'has B5678 shipped?', "
             "'show my orders', 'track my package'. Also a reply that only gives an order ID "
             "after the agent asked which order to check. NOT cancelling (that is cancel_order).",
        context="Answer with exactly ONE get_order call, then stop: no further tool call is "
                "needed after get_order has returned. If the user's current message names an "
                "order ID, call get_order with it and the outcome is that order's status "
                "(placed, dispatched, delivered or cancelled_status), or not_found. If the "
                "current message names NO order ID, call get_order without one; it returns the "
                "list of all orders and the outcome is order_list. Never call get_order twice "
                "in the same turn.",
        tools=["get_order"],
        outcomes=["placed", "dispatched", "delivered", "cancelled_status", "not_found",
                  "order_list", "failed"]),
    "cancel_order": Intent(
        desc="The user wants to cancel or stop an order, or no longer wants it. "
             "Examples: 'cancel my order', 'cancel A1234', 'I don't want B5678 anymore', "
             "'stop my order, it's taking too long'. Also a reply that only gives an order ID "
             "and/or a reason after the agent asked which order to cancel or why. "
             "NOT refunds or returns of delivered items (that is out_of_scope).",
        context="Step 1: ALWAYS call get_order first, exactly once, even when the user names an "
                "order or picks one from a list the agent showed (e.g. 'the first one'). If the "
                "user's current message names or picks an order, call get_order for that order; "
                "otherwise call it without an order ID, which returns the list of all orders. "
                "Step 2: if get_order returned the LIST of all orders, stop: do NOT call "
                "cancel_order, the outcome is choose_order. If it returned one order that is "
                "delivered or cancelled, stop: the outcome is cancel_blocked. If it returned "
                "not found, stop: the outcome is not_found. If it returned one order that is "
                "placed or dispatched, call cancel_order for that same order ID. "
                "Never cancel an order the user did not name in this cancellation request.",
        tools=["get_order", "cancel_order"],
        outcomes=["cancelled", "cancel_blocked", "not_found", "choose_order", "failed"]),
    "greeting": Intent(
        desc="Greetings, thanks, goodbyes, small talk, or asking what the agent can do, with no "
             "order request in it. Examples: 'hi', 'good morning', 'how are you', 'thanks', "
             "'bye', 'what can you do?', 'are you a bot?'. If the message also asks about or "
             "cancels an order, it is NOT a greeting.",
        context="The user is greeting or making small talk. No tool is needed. Pick the category: "
                "opening the conversation, closing it, or asking what the agent can do.",
        tools=[],
        outcomes=["greet", "closing", "capabilities"]),
    "out_of_scope": Intent(
        desc="Any request that is neither checking an order's status nor cancelling an order. "
             "Examples: refunds, returns, complaints, changing the address, product questions, "
             "payments, weather, general questions.",
        context="The request is not about order status or cancellation. No tool is needed.",
        tools=[],
        outcomes=["out_of_scope"]),
}

# ======================= OUTCOMES =======================
OUTCOMES = {
    "greet": Outcome(
        desc="Opening or friendly small talk: hello, good morning, how are you, ok, cool.",
        reply="Hi! I can help you check an order's status or cancel an order. How can I help?"),
    "closing": Outcome(
        desc="Thanking or ending the conversation: thanks, bye, that's all, see you.",
        reply="You're welcome! Have a great day, and come back anytime you need help with "
              "your orders."),
    "capabilities": Outcome(
        desc="Asking what the agent can do or who it is: what can you do, help, are you a bot.",
        reply="I'm an order support assistant. I can show your orders, tell you an order's "
              "status, and cancel an order that hasn't been delivered yet."),
    "out_of_scope": Outcome(
        desc="The request is outside order status and cancellation.",
        reply="Sorry, I can only help with order status and cancellations."),
    "placed": Outcome(
        desc="get_order returned ONE order (with an order_id) whose status is placed.",
        reply="Your order {order_id} ({item}) is placed."),
    "dispatched": Outcome(
        desc="get_order returned ONE order (with an order_id) whose status is dispatched.",
        reply="Your order {order_id} ({item}) has been dispatched."),
    "delivered": Outcome(
        desc="get_order returned ONE order (with an order_id) whose status is delivered.",
        reply="Your order {order_id} ({item}) has been delivered."),
    "cancelled_status": Outcome(
        desc="get_order returned ONE order (with an order_id) whose status is cancelled.",
        reply="Your order {order_id} ({item}) was cancelled."),
    "not_found": Outcome(
        desc="A tool returned an error saying the order was not found.",
        reply="I couldn't find order {order_id}. Please check the ID."),
    "cancelled": Outcome(
        desc="cancel_order was called and returned status cancelled.",
        reply="Your order {order_id} ({item}) has been cancelled (reason: {reason})."),
    "cancel_blocked": Outcome(
        desc="get_order returned ONE order whose status is delivered or cancelled, so it can't "
             "be cancelled.",
        reply="Order {order_id} ({item}) can't be cancelled (status: {status})."),
    "order_list": Outcome(
        desc="get_order returned the LIST of all orders (an 'orders' list, no single order).",
        reply="Here are your orders:\n{orders}\nWhich order ID would you like to check?"),
    "choose_order": Outcome(
        desc="get_order returned the LIST of all orders (an 'orders' list, no single order), so "
             "the user must choose which order to cancel.",
        reply="Here are your orders:\n{orders}\nWhich order ID would you like to cancel, and why?"),
    # not offered to the model: chosen by the human-in-the-loop rule when a reviewer rejects
    "cancel_rejected": Outcome(
        desc="A reviewer rejected the cancellation.",
        reply="A reviewer declined to cancel order {order_id}. Reason: {rejection_reason}"),
    "failed": Outcome(
        desc="A tool returned an error that is not 'not found'.",
        reply="Something went wrong on our side. I'm handing you over to a human."),
}

def main():
    """Initialize Jev and run the interactive agent."""
    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
    model = SystemOneModel(api_key=os.getenv("TYPESAFE_API_KEY"))
    # Initialize Cloudflare Clef instead of Jev:
    # model = CloudflareModel(
    #     api_token=os.environ["CLOUDFLARE_API_TOKEN"],
    #     account_id=os.environ["CLOUDFLARE_ACCOUNT_ID"],
    #     model="clef",
    # )

    approval = HumanInTheLoopMiddleware(approvals={
        "cancel_order": Approval(
            rejected_outcome="cancel_rejected",
            waiting="Cancelling order {order_id} needs approval. "
                    "Type /approve or /reject followed by a reason.")})
    agent = Agent(
        tools=[get_order, cancel_order], intents=INTENTS, outcomes=OUTCOMES,
        model=model, memory=ConversationBufferMemory(k=7),
        # checkpointer=SqliteCheckpointer("order_agent.db"),
        middleware=[approval])

    print('Order support: try A1234, B5678, or delivered order C9012.')
    print("Demo inventory resets on restart. Ctrl+C to quit.")
    while True:
        try:
            message = input("YOU> ").strip()
        except (KeyboardInterrupt, EOFError):
            print()
            break
        if message:
            result = agent.turn(message)
            print("AGENT>", result.reply)


if __name__ == "__main__":
    main()
