import os
import qrcode
from qrcode.image.styledpil import StyledPilImage
from qrcode.image.styles.moduledrawers import RoundedModuleDrawer
from qrcode.image.styles.colormasks import SolidFillColorMask
from flask import Blueprint, render_template, request, jsonify, redirect, url_for, current_app, session
from app.models import Business, Product, db
import time
from PIL import Image, ImageDraw
from app.qr_modifier import QRModifier

main_bp = Blueprint('main', __name__)


main_bp = Blueprint('main', __name__)

# Helper to generate Google Review Link
def get_google_review_link(place_id):
    if "g.page" in place_id:
        return place_id
    return f"https://search.google.com/local/writereview?placeid={place_id}"

@main_bp.route('/')
def index():
    if session.get('admin_logged_in'):
        return redirect(url_for('main.admin_page'))
    return render_template('login.html')

@main_bp.route('/login', methods=['POST'])
def login():
    username = request.form.get('username')
    password = request.form.get('password')

    # DEBUG: Print values to console to see if they match
    admin_user = current_app.config.get('ADMIN_USERNAME')
    admin_pass = current_app.config.get('ADMIN_PASSWORD')

    print(f"LOGIN ATTEMPT: {username} / {password}")
    print(f"EXPECTED: {admin_user} / {admin_pass}")

    if username == admin_user and password == admin_pass:
        session['admin_logged_in'] = True
        print("LOGIN SUCCESS")
        return redirect(url_for('main.admin_page'))

    print("LOGIN FAILED")
    return render_template('login.html', error="Invalid username or password")

@main_bp.route('/logout')
def logout():
    session.pop('admin_logged_in', None)
    return redirect(url_for('main.index'))

@main_bp.route('/business/<int:business_id>')
def business_landing(business_id):
    business = Business.query.get_or_404(business_id)
    products = Product.query.filter_by(business_id=business_id).all()
    return render_template('landing.html', business=business, products=products)

@main_bp.route('/generate_review', methods=['POST'])
def generate_review():
    data = request.json
    products = data.get('products', [])
    business_id = data.get('business_id')
    if not products:
        return jsonify({"success": False, "error": "Please select at least one product"}), 400
    business = Business.query.get_or_404(business_id)

    selected_products_str = ", ".join(products) if isinstance(products, list) else str(products)
    # Prepare services list for the prompt
    #services = [p.name for p in Product.query.filter_by(business_id=business_id).all()]
    #services_str = ", ".join(services)

    #selected_products_str = ", ".join(products) if isinstance(products, list) else str(products)

    prompt = f"""
You are an AI assistant that helps a real customer turn their genuine feedback
into a short, natural Google review.

BUSINESS
Business: {business.name} ({business.category})
Products used: {selected_products_str}

CUSTOMER
Service/product used: {selected_products_str}
Customer feedback: The customer is very happy with {selected_products_str} and wants to leave a positive 5-star review.
Experience details: Positive experience with {selected_products_str}.

RULES:
- Use ONLY information provided by the customer.
- Never invent experiences, employees, products, results, prices, or claims.
- Write like a normal customer, NOT like a marketer or business owner.
- Keep it SHORT: 2-3 sentences and preferably 50–60 words.
- Maximum 60 words.
- Avoid long paragraphs.
- Do not repeat the same sentence structure or opening used in previous reviews.
- Naturally focus on the most relevant aspect of the customer's experience,
  such as service quality, product quality, staff/owner behaviour,
  professionalism, value, speed, cleanliness, expertise, or convenience.
- Adapt the wording to the business category.
- Do not force keywords or mention every product/service.
- Avoid repetitive phrases like "highly recommended", "excellent service",
  "amazing experience", and "best service" unless they genuinely reflect
  the customer's feedback.
- Use simple, conversational language.
- Do not use emojis unless the customer used them.
- Do not mention AI.
- Do not use quotation marks.
- Output ONLY the review.

IMPORTANT:
Every review should feel naturally different in wording, length,
sentence structure, vocabulary, and the aspect being highlighted.
If multiple products are selected, combine them naturally into the review.
"""

    try:
        # Use the singleton client initialized in app/__init__.py
        client = current_app.extensions.get('gemini_client')
        if not client:
            raise Exception("Gemini client not initialized")

        start_time = time.perf_counter()

        # Use modern google-genai SDK and fast flash model
        response = client.models.generate_content(
            model='gemini-2.0-flash',
            contents=prompt,
            config={
                'max_output_tokens': 80,
                'temperature': 0.7
            }
        )

        latency = time.perf_counter() - start_time
        current_app.logger.info("Gemini review generation latency: %.2fs", latency)

        review_text = response.text.strip()
    except Exception as e:
        current_app.logger.exception("Gemini review generation failed")
        review_text = f"I had a great experience with {business.name}! The {selected_products_str} was fantastic. Highly recommended!"

    return jsonify({
        "review": review_text,
        "review_link": get_google_review_link(business.google_place_id)
    })


@main_bp.route('/admin/setup', methods=['POST'])
def admin_setup():
    if not session.get('admin_logged_in'):
        return jsonify({"success": False, "error": "Unauthorized"}), 401

    data = request.json

    business = Business.query.filter_by(name=data['name']).first()
    if not business:
        business = Business(
            name=data['name'],
            category=data.get('category'),
            google_place_id=data['google_place_id'],
            tone=data.get('tone', 'professional')
        )
        db.session.add(business)
    else:
        business.google_place_id = data['google_place_id']
        business.category = data.get('category')
        business.tone = data.get('tone', 'professional')
        Product.query.filter_by(business_id=business.id).delete()

    db.session.commit()

    products_list = data.get('products', [])
    for p_name in products_list:
        product = Product(name=p_name, business_id=business.id)
        db.session.add(product)
    db.session.commit()

    # --- NEW MODIFIER FLOW ---
    base_url = current_app.config['APP_BASE_URL']
    qr_url = f"{base_url}/business/{business.id}"

    try:
        # 1. Initialize the modifier
        modifier = QRModifier(business=business, qr_url=qr_url)

        # 2. Apply modifications (Professional template flow)
        final_image = modifier.generate_professional_card()

        # 3. Save the result
        static_folder = os.path.join(current_app.root_path, 'static', 'qrcodes')
        os.makedirs(static_folder, exist_ok=True)
        filename = f"qr_{business.id}.png"
        file_path = os.path.join(static_folder, filename)
        final_image.save(file_path)

        business.qr_code_path = f"static/qrcodes/{filename}"
        db.session.commit()

        return jsonify({
            "success": True,
            "qr_code": business.qr_code_path,
            "link": qr_url
        })
    except Exception as e:
        print(f"QR Modifier Error: {e}")
        return jsonify({"success": False, "error": f"Design failed: {str(e)}"}), 500

@main_bp.route('/admin')
def admin_page():
    if not session.get('admin_logged_in'):
        return redirect(url_for('main.index'))
    return render_template('admin_setup.html')