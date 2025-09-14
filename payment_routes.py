import os
from flask import Blueprint, render_template, request, redirect, url_for, current_app
import stripe
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Create a Blueprint for payment routes
payment_bp = Blueprint('payment', __name__) #template_folder='templates')

# Set your Stripe API key from the environment variable
stripe.api_key = os.getenv('STRIPE_SECRET_KEY')

@payment_bp.route('/donate_money', methods=['GET'])
def donate_money():
    """Renders the donation page."""
    # We can pass the public key to the template if we were using Stripe.js elements
    # For a simple redirect, it's not strictly necessary on this page.
    return render_template('donate_money.html')

@payment_bp.route('/create-checkout-session', methods=['POST'])
def create_checkout_session():
    """Creates a Stripe Checkout Session and redirects the user."""
    try:
        # Get the donation amount from the form
        amount = request.form.get('amount')
        
        # Convert amount to cents (Stripe's required format)
        amount_in_cents = int(float(amount) * 100)

        # Ensure the amount is at least $0.50 (Stripe's minimum)
        if amount_in_cents < 50:
            return "Donation amount must be at least $0.50", 400

        # Create a new Checkout Session
        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'usd',
                    'product_data': {
                        'name': 'Donation to NourishAI',
                        'description': 'Your generous contribution to help us fight food insecurity.',
                    },
                    'unit_amount': amount_in_cents,
                },
                'quantity': 1,
            }],
            mode='payment',
            # These are the URLs Stripe will redirect to on success or cancellation
            success_url=url_for('payment.success', _external=True) + '?session_id={CHECKOUT_SESSION_ID}',
            cancel_url=url_for('payment.cancel', _external=True),
        )
        # Redirect the user to the Stripe-hosted checkout page
        return redirect(session.url, code=303)

    except Exception as e:
        current_app.logger.error(f"Error creating Stripe session: {e}")
        return str(e), 400

@payment_bp.route('/success')
def success():
    """Renders the success page after a successful payment."""
    # In a real app, you would use the session_id to verify the payment
    # and update your database.
    return render_template('success.html')

@payment_bp.route('/cancel')
def cancel():
    """Renders the cancellation page."""
    return render_template('cancel.html')
