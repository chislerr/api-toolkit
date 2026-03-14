import io
import os
from PIL import Image, ImageDraw, ImageFont

# Define path to fonts
ASSETS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'assets')
FONT_BOLD_PATH = os.path.join(ASSETS_DIR, 'Roboto-Bold.ttf')
FONT_REGULAR_PATH = os.path.join(ASSETS_DIR, 'Roboto-Regular.ttf')

def wrap_text(text: str, font: ImageFont.FreeTypeFont, max_width: int, draw: ImageDraw.Draw) -> list[str]:
    """Wraps text to fit within a given maximum width."""
    lines = []
    
    # Check if the whole text fits
    if draw.textlength(text, font=font) <= max_width:
        return [text]
        
    words = text.split(' ')
    current_line = ""
    
    for word in words:
        test_line = f"{current_line} {word}".strip()
        length = draw.textlength(test_line, font=font)
        if length <= max_width:
            current_line = test_line
        else:
            if current_line:
                lines.append(current_line)
            current_line = word
            
    if current_line:
        lines.append(current_line)
        
    return lines

def generate_og_image(title: str, subtitle: str | None = None, bg_color: str = "#1a202c", text_color: str = "#ffffff") -> bytes:
    """
    Generates a 1200x630 Open Graph image using Pillow.
    Returns the binary PNG data.
    """
    width = 1200
    height = 630
    
    # In case user sends empty strings
    if not bg_color:
        bg_color = "#1a202c"
    if not text_color:
        text_color = "#ffffff"

    # Create a new image with the background color
    img = Image.new('RGB', (width, height), color=bg_color)
    draw = ImageDraw.Draw(img)
    
    # Load fonts (fallback to default if file not found)
    try:
        title_font = ImageFont.truetype(FONT_BOLD_PATH, size=80)
        subtitle_font = ImageFont.truetype(FONT_REGULAR_PATH, size=40)
    except IOError:
        title_font = ImageFont.load_default()
        subtitle_font = ImageFont.load_default()

    # Metrics
    margin_x = 100
    margin_y = 150
    max_text_width = width - (margin_x * 2)

    # Calculate wrapped title
    wrapped_title_lines = wrap_text(title, title_font, max_text_width, draw)
    
    # Draw Title
    current_y = margin_y
    for line in wrapped_title_lines:
        line_bbox = draw.textbbox((0, 0), line, font=title_font)
        line_height = line_bbox[3] - line_bbox[1]
        draw.text((margin_x, current_y), line, font=title_font, fill=text_color)
        current_y += line_height + 20 # Add leading

    # Draw Subtitle if exists
    if subtitle:
        current_y += 40 # Margin between title and subtitle
        wrapped_subtitle_lines = wrap_text(subtitle, subtitle_font, max_text_width, draw)
        
        # Subtitle font color is often slightly faded, but we use the provided text_color
        # For a truly premium feel we could lower alpha, but let's keep it simple
        for line in wrapped_subtitle_lines:
            line_bbox = draw.textbbox((0, 0), line, font=subtitle_font)
            line_height = line_bbox[3] - line_bbox[1]
            draw.text((margin_x, current_y), line, font=subtitle_font, fill=text_color)
            current_y += line_height + 15
            
    # Save the generated image to an in-memory buffer
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    
    return buf.getvalue()
