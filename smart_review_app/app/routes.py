import os
import qrcode
from qrcode.image.styledpil import StyledPilImage
from qrcode.image.styles.moduledrawers import RoundedModuleDrawer
from qrcode.image.styles.colormasks import SolidFillColorMask
from flask import Blueprint, render_template, request, jsonify, redirect, url_for, current_app, session
from app.models import Business, Product, db
import google.generativeai as genai
from PIL import Image, ImageDraw

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
    product_name = data.get('product')
    business_id = data.get('business_id')

    business = Business.query.get_or_404(business_id)

    # Prepare services list for the prompt
    services = [p.name for p in Product.query.filter_by(business_id=business_id).all()]
    services_str = ", ".join(services)

    prompt = f"""
You are an AI assistant that helps a real customer turn their genuine feedback
into a short, natural Google review.

BUSINESS
Business name: {business.name}
Business category: {business.category}
Products/services: {services_str}

CUSTOMER
Service/product used: {product_name}
Customer feedback: The customer is very happy with the {product_name} and wants to leave a positive 5-star review.
Experience details: Positive experience with the {product_name}.

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
"""

    try:
        genai.configure(api_key=current_app.config['GEMINI_API_KEY'])
        model = genai.GenerativeModel('gemini-3-flash-preview')
        response = model.generate_content(prompt)
        review_text = response.text
    except Exception as e:
        print(f"AI Error: {e}")
        review_text = f"I had an amazing experience with {business.name}! The {product_name} was absolutely fantastic. Highly recommended!"

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

    base_url = current_app.config['APP_BASE_URL']
    qr_url = f"{base_url}/business/{business.id}"

    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=4,
    )
    qr.add_data(qr_url)
    qr.make(fit=True)

    qr_img = qr.make_image(
        image_factory=StyledPilImage,
        module_drawer=RoundedModuleDrawer(),
        color_mask=SolidFillColorMask(
            back_color=(255, 255, 255),
            front_color=(212, 175, 55)  # Gold
        )
    ).convert("RGBA")

    padding = 40
    width, height = qr_img.size
    canvas = Image.new("RGBA", (width + padding*2, height + padding*2), (0, 0, 0, 0))
    mask = Image.new("L", (width + padding*2, height + padding*2), 0)
    draw = ImageDraw.Draw(mask)
    radius = 80
    draw.rounded_rectangle(
        [padding, padding, width + padding, height + padding],
        radius=radius,
        fill=255
    )
    canvas.paste(qr_img, (padding, padding))
    final_img = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    final_img.paste(canvas, (0, 0), mask=mask)
    final_img = final_img.convert("RGB")

    static_folder = os.path.join(current_app.root_path, 'static', 'qrcodes')
    os.makedirs(static_folder, exist_ok=True)

    filename = f"qr_{business.id}.png"
    file_path = os.path.join(static_folder, filename)
    final_img.save(file_path)

    business.qr_code_path = f"static/qrcodes/{filename}"
    db.session.commit()

    return jsonify({
        "success": True,
        "qr_code": business.qr_code_path,
        "link": qr_url
    })

@main_bp.route('/admin')
def admin_page():
    if not session.get('admin_logged_in'):
        return redirect(url_for('main.index'))
    return render_template('admin_setup.html')