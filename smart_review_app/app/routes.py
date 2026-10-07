import os
import qrcode
from qrcode.image.styledpil import StyledPilImage
from qrcode.image.styles.moduledrawers import RoundedModuleDrawer
from qrcode.image.styles.colormasks import SolidFillColorMask
from flask import Blueprint, render_template, request, jsonify, redirect, url_for, current_app
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
    return "Welcome to Smart Review Automator. Please use the business-specific QR link."

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

    tone_guide = {
        "professional": "Use a professional, formal, and polished tone.",
        "friendly": "Use a warm, friendly, and casual tone.",
        "enthusiastic": "Use a high-energy, extremely enthusiastic, and excited tone."
    }

    prompt = (
        f"{tone_guide.get(business.tone, tone_guide['professional'])} "
        f"Write a short, positive 5-star Google review for a business named '{business.name}'. "
        f"The customer is praising the service: '{product_name}'. "
        f"Make it sound natural, genuine, and helpful to other users. "
        f"Keep it under 3 sentences. Output ONLY the review text."
    )

    try:
        genai.configure(api_key=current_app.config['GEMINI_API_KEY'])
        model = genai.GenerativeModel('gemini-pro')
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
    data = request.json

    business = Business.query.filter_by(name=data['name']).first()
    if not business:
        business = Business(
            name=data['name'],
            google_place_id=data['google_place_id'],
            tone=data.get('tone', 'professional')
        )
        db.session.add(business)
    else:
        business.google_place_id = data['google_place_id']
        business.tone = data.get('tone', 'professional')
        Product.query.filter_by(business_id=business.id).delete()

    db.session.commit()

    products_list = data.get('products', [])
    for p_name in products_list:
        product = Product(name=p_name, business_id=business.id)
        db.session.add(product)
    db.session.commit()

    # --- LUXURY ROUNDED QR CODE GENERATION ---
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

    # 1. Generate the base Gold QR
    qr_img = qr.make_image(
        image_factory=StyledPilImage,
        module_drawer=RoundedModuleDrawer(),
        color_mask=SolidFillColorMask(
            back_color=(255, 255, 255), # White
            front_color=(212, 175, 55)  # Gold #D4AF37
        )
    ).convert("RGBA")

    # 2. Create a rounded-corner mask (The "Instagram" look)
    # Add a small padding to the base image to allow for the rounded corners
    padding = 40
    width, height = qr_img.size
    canvas = Image.new("RGBA", (width + padding*2, height + padding*2), (0, 0, 0, 0))

    # Create the rounded mask
    mask = Image.new("L", (width + padding*2, height + padding*2), 0)
    draw = ImageDraw.Draw(mask)

    # Draw a rounded rectangle for the mask
    # radius is the corner curvature
    radius = 80
    draw.rounded_rectangle(
        [padding, padding, width + padding, height + padding],
        radius=radius,
        fill=255
    )

    # Paste the QR image into the center of the canvas
    canvas.paste(qr_img, (padding, padding))

    # Apply the rounded mask to the canvas
    final_img = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    final_img.paste(canvas, (0, 0), mask=mask)

    # Convert back to RGB to save as PNG if needed, or keep RGBA for transparency
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
    return render_template('admin_setup.html')
