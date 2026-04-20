"""
SovereignSwarm — Real Stripe Bank Transfer
Pay profits out to the owner's bank account via Stripe Connect.
"""
import os, stripe

def get_stripe_config():
    return {
        "secret_key": os.environ.get("STRIPE_SECRET_KEY", ""),
        "master_acct": os.environ.get("STRIPE_MASTER_ACCT", ""),
    }

def check_stripe_ready():
    cfg = get_stripe_config()
    if not cfg["secret_key"]:
        return False, "STRIPE_SECRET_KEY not set"
    if not cfg["master_acct"]:
        return False, "STRIPE_MASTER_ACCT not set"
    return True, "Stripe ready"

def pay_to_bank(amount_usd: float) -> dict:
    """
    Transfer money from Stripe platform to owner's connected bank.
    Returns dict with status, transfer_id, or error.
    """
    cfg = get_stripe_config()
    ready, msg = check_stripe_ready()
    if not ready:
        return {"success": False, "error": msg}

    try:
        stripe.api_key = cfg["secret_key"]

        # Create a real bank transfer (payout)
        transfer = stripe.Transfer.create(
            amount=int(amount_usd * 100),   # cents
            currency="usd",
            destination=cfg["master_acct"],
            metadata={"source": "SovereignSwarm", "agent": "system"},
        )
        return {
            "success": True,
            "transfer_id": transfer.id,
            "amount": amount_usd,
            "destination": cfg["master_acct"],
        }
    except stripe.error.AuthenticationError:
        return {"success": False, "error": "Invalid Stripe API key"}
    except stripe.error.StripeError as e:
        return {"success": False, "error": str(e)}

def create_payment_link(amount_cents: int, product_name: str, agent_id: str) -> str:
    """Create a Stripe payment link that clients can use to pay agents."""
    cfg = get_stripe_config()
    if not cfg["secret_key"]:
        return ""

    try:
        stripe.api_key = cfg["secret_key"]

        # Create product
        product = stripe.Product.create(
            name=f"SovereignSwarm — {product_name}",
            metadata={"agent_id": agent_id}
        )

        # Create price
        price = stripe.Price.create(
            product=product.id,
            unit_amount=amount_cents,
            currency="usd",
        )

        # Create payment link
        link = stripe.PaymentLink.create(
            line_items=[{"price": price.id, "quantity": 1}],
            metadata={"agent_id": agent_id}
        )
        return link.url
    except stripe.error.StripeError:
        return ""

def get_account_balance() -> dict:
    """Check actual Stripe account balance."""
    cfg = get_stripe_config()
    if not cfg["secret_key"]:
        return {"available": 0, "pending": 0}
    stripe.api_key = cfg["secret_key"]
    try:
        balance = stripe.Balance.retrieve()
        return {
            "available": balance.available[0].amount / 100 if balance.available else 0,
            "pending": balance.pending[0].amount / 100 if balance.pending else 0,
        }
    except:
        return {"available": 0, "pending": 0}
