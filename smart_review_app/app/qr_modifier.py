import qrcode
from PIL import Image, ImageDraw, ImageFont
import os
from flask import current_app

class QRModifier:
    def __init__(self, business, qr_url):
        self.business = business
        self.qr_url = qr_url
        # Path to the professional static template
        self.template_path = os.path.join(current_app.root_path, 'static', 'images', 'review_template.jpeg')

    def _generate_raw_qr(self):
        """Generates a high-quality QR code with no border"""
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_H,
            box_size=15,
            border=0, # No border, the template provides the spacing
        )
        qr.add_data(self.qr_url)
        qr.make(fit=True)
        return qr.make_image(fill_color="black", back_color="white").convert("RGBA")

    def generate_professional_card(self):
        # 1. Load the static template
        if not os.path.exists(self.template_path):
            # Fallback: Create a basic white canvas if template is missing to avoid app crash
            print(f"WARNING: Template image not found at {self.template_path}. Using fallback white background.")
            template = Image.new("RGBA", (1000, 1400), (255, 255, 255, 255))
        else:
            template = Image.open(self.template_path).convert("RGBA")

        canvas_w, canvas_h = template.size

        # 2. Generate the QR code
        qr_img = self._generate_raw_qr()

        # 3. Resize QR to fit the template's "hole"
        # These values are standard for a 1000x1400 template
        qr_size = 400
        qr_img = qr_img.resize((qr_size, qr_size), Image.Resampling.LANCZOS)

        # 4. Position the QR code (Centered)
        offset_x = (canvas_w - qr_size) // 2
        offset_y = (canvas_h // 2) - (qr_size // 2)

        # Paste QR onto template
        template.paste(qr_img, (offset_x, offset_y), qr_img)

        # 5. Add the Business Name (since this changes per business)
        # draw = ImageDraw.Draw(template)
        # try:
        #     # Attempt to use a professional font for the business name
        #     font_name = ImageFont.truetype("arialbd.ttf", 60)
        # except:
        #     font_name = ImageFont.load_default()

        # # Position the business name at the bottom area of the template
        # # Adjust 1200 based on the template layout
        # draw.text((canvas_w//2, 1200), self.business.name.upper(), fill="black", font=font_name, anchor="mm")

        return template.convert("RGB")
