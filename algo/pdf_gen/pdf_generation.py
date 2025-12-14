# pdf_gen/pdf_generation.py (UPDATED VERSION )
import json
import os
import hashlib
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm, mm
from reportlab.pdfgen import canvas
from reportlab.pdfbase.pdfmetrics import stringWidth

# Import template manager with proper error handling
try:
    from .template_manager import template_manager
except ImportError:
    try:
        from template_manager import template_manager
    except ImportError:
        print("⚠️ Template manager not available, using fallback mode")
        template_manager = None

CACHE_DIR = "pdf_gen/seat_plan_generated"
IMAGE_PATH = "pdf_gen/data/banner.png"
CUSTOM_PAGE_SIZE = (304 * mm, 235 * mm)

def seating_payload_digest(data: dict, user_id: str = 'system', template_name: str = 'default') -> str:
    """Create hash including user template configuration"""
    seating_data_normalized = json.dumps(data, sort_keys=True, separators=(',', ':'))
    
    if template_manager:
        template_hash = template_manager.get_template_hash(user_id, template_name)
        combined = f"{seating_data_normalized}|{user_id}|{template_name}|{template_hash}"
    else:
        # Fallback without template system
        combined = seating_data_normalized
    
    return hashlib.sha256(combined.encode('utf-8')).hexdigest()

def get_or_create_seating_pdf(data: dict, user_id: str = 'system', template_name: str = 'default', cache_dir: str = CACHE_DIR) -> str:
    """Generate PDF with user-specific template and caching"""
    if data is None:
        raise ValueError("Seating data required")

    digest = seating_payload_digest(data, user_id, template_name)
    
    # Create user-specific cache directory if template manager available
    if template_manager and user_id != 'system':
        user_cache_dir = os.path.join(cache_dir, str(user_id))
        os.makedirs(user_cache_dir, exist_ok=True)
        filename = os.path.join(user_cache_dir, f"seating_plan_{digest}.pdf")
    else:
        # Fallback to original behavior
        os.makedirs(cache_dir, exist_ok=True)
        filename = os.path.join(cache_dir, f"seating_plan_{digest}.pdf")

    if not os.path.exists(filename):
        print(f"🔄 Generating new PDF for user: {user_id}")
        create_seating_pdf(filename=filename, data=data, user_id=user_id, template_name=template_name)
    else:
        print(f"♻️ Using cached PDF for user: {user_id}")
    
    return filename

def process_seating_data(json_data):
    """Returns matrix of cell dicts: {'text': str, 'bg': color_or_None}"""
    seating_rows = json_data.get('seating', [])
    metadata = json_data.get('metadata', {})
    num_rows = metadata.get('rows', 0)
    num_cols = metadata.get('cols', 0)

    actual_rows = len(seating_rows)
    actual_cols = max((len(r) for r in seating_rows), default=0)
    if num_rows == 0:
        num_rows = actual_rows
    if num_cols == 0:
        num_cols = actual_cols

    matrix = [[{'text': '', 'bg': None} for _ in range(num_cols)] for _ in range(num_rows)]

    for r in range(num_rows):
        if r >= len(seating_rows):
            continue
        row = seating_rows[r]
        for c in range(num_cols):
            if c >= len(row):
                continue
            seat = row[c]
            
            if seat.get('is_broken'):
                content = seat.get('display', 'BROKEN')
                bg = seat.get('color', '#FF0000')
            elif seat.get('is_unallocated'):
                content = seat.get('display','UNALLOC')
                bg = seat.get('color','#F3F4F6')
            else:
                roll = seat.get('roll_number', '')
                pset = seat.get('paper_set', '')
                content = f"{roll}\nSET {pset}"
                bg = seat.get('color')
                
            matrix[r][c] = {'text': content, 'bg': bg}
    return matrix

def format_cell_content(raw, style):
    if not raw.strip():
        return ''
    parts = raw.strip().split('\n')
    if len(parts) == 2:
        text = f"<b>{parts[0]}</b><br/>{parts[1]}"
    else:
        text = f"<b>{parts[0]}</b>"
    return Paragraph(text, style)

def create_seating_pdf(filename="pdf_gen/seat_plan_generated/seating_plan.pdf", data=None, user_id: str = 'system', template_name: str = 'default'):
    """Generate PDF using user's specific template or fallback to default"""
    if data is None:
        raise ValueError("Seating data required")
    
    # Load user's template configuration or use defaults
    if template_manager:
        template_config = template_manager.get_user_template(user_id, template_name)
        print(f"📋 Using template for user {user_id}: {template_config.get('dept_name', 'Default')}")
    else:
        # Fallback template config
        template_config = {
            'dept_name': 'Department of Computer Science & Engineering',
            'exam_details': 'Minor-II Examination (2025 Admitted), November 2025',
            'seating_plan_title': 'Seating Plan',
            'branch_text': 'Branch: B.Tech(CSE & CSD Ist year)',
            'room_number': 'Room no. 103A',
            'coordinator_name': 'Dr. Dheeraj K. Dixit',
            'coordinator_title': 'Dept. Exam Coordinator',
            'banner_image_path': IMAGE_PATH
        }
    
    def header_and_footer(c, doc):
        c.saveState()
        page_width, page_height = CUSTOM_PAGE_SIZE
        BANNER_HEIGHT = 3.5 * cm
        CONTENT_WIDTH = page_width - doc.leftMargin - doc.rightMargin
        
        # Use template's banner image path
        banner_path = template_config.get('banner_image_path', IMAGE_PATH)
        try:
            c.drawImage(banner_path,
                        x=doc.leftMargin,
                        y=page_height - doc.topMargin - 0.3 * cm,
                        width=CONTENT_WIDTH,
                        height=BANNER_HEIGHT,
                        preserveAspectRatio=True)
        except Exception:
            c.setFont('Helvetica-Bold', 12)
            c.drawCentredString(page_width / 2, page_height - doc.topMargin + 1.2 * cm,
                                "Header image missing")
        
        c.setFont('Helvetica', 9)
        footer_x = page_width - doc.rightMargin
        footer_y = doc.bottomMargin / 2
        c.drawRightString(footer_x, footer_y + 8, template_config.get('coordinator_name', 'Dr. Dheeraj K. Dixit'))
        c.drawRightString(footer_x, footer_y, template_config.get('coordinator_title', 'Dept. Exam Coordinator'))
        c.restoreState()
    
    seating_matrix = process_seating_data(data)
    metadata = data.get('metadata', {})
    num_cols = metadata.get('cols', 0) or (len(seating_matrix[0]) if seating_matrix else 0)
    num_rows = metadata.get('rows', 0) or len(seating_matrix)
    block_width = metadata.get('block_width', 1)
    num_blocks = metadata.get('blocks', 1)

    doc = SimpleDocTemplate(
        filename,
        pagesize=CUSTOM_PAGE_SIZE,
        topMargin=3.5 * cm,
        bottomMargin=2.0 * cm,
        leftMargin=1.5 * cm,
        rightMargin=1.5 * cm
    )
    story = []
    styles = getSampleStyleSheet()

    cell_style = styles['Normal'].clone('Cell')
    cell_style.fontSize = 9
    cell_style.alignment = 1
    cell_style.leading = 12
    cell_style.fontName = 'Helvetica-Bold'

    header_style = styles['Normal'].clone('Header')
    header_style.fontSize = 12
    header_style.alignment = 1
    header_style.fontName = 'Helvetica-Bold'

    story.append(Spacer(0, 0.2 * cm))
    
    # Use template values
    dept_style = styles['Normal'].clone('Dept')
    dept_style.fontSize = 13
    dept_style.alignment = 1
    story.append(Paragraph(f"<b>{template_config.get('dept_name')}</b>", dept_style))
    
    story.append(Spacer(0, 0.15 * cm))
    exam_style = styles['Normal'].clone('Exam')
    exam_style.fontSize = 12
    exam_style.alignment = 1
    story.append(Paragraph(template_config.get('exam_details'), exam_style))
    
    title_style = styles['Heading4'].clone('Title')
    title_style.alignment = 1
    title_style.fontSize = 18
    story.append(Paragraph(f"<b>{template_config.get('seating_plan_title')}</b>", title_style))

    br_style = styles['Normal'].clone('BR')
    br_style.fontSize = 12
    br_style.fontName = 'Helvetica-Bold'
    
    branch = Paragraph(f"<b>{template_config.get('branch_text')}</b>", br_style)
    room = Paragraph(f"<b>{template_config.get('room_number')}</b>", br_style)
    
    page_width = CUSTOM_PAGE_SIZE[0]
    content_width = page_width - doc.leftMargin - doc.rightMargin

    room_text = template_config.get('room_number', 'Room no. 103A')
    room_width = stringWidth(room_text, "Helvetica-Bold", 12) + 10
    room_width = min(room_width, content_width)
    branch_col_width = content_width - room_width 

    br_table = Table([[branch, room]], colWidths=[branch_col_width, room_width])
    br_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (0, 0), 'LEFT'),
        ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))
    story.append(Spacer(0, 0.5 * cm))
    story.append(br_table)
    story.append(Spacer(0, 0.4 * cm))

    # Rest of your existing table code stays the same
    if num_cols > 0 and num_rows > 0:
        table_content = []
        style_cmds = []

        block_header_row = [''] * num_cols
        col_index = 0
        for block_idx in range(num_blocks):
            start_col = col_index
            end_col = min(col_index + block_width, num_cols)
            if start_col < num_cols:
                block_header_row[start_col] = Paragraph(f"<b>Block {block_idx + 1}</b>", header_style)
            col_index = end_col

        table_content.append(block_header_row)

        col_index = 0
        for block_idx in range(num_blocks):
            start_col = col_index
            end_col = min(col_index + block_width, num_cols) - 1
            if start_col <= end_col:
                style_cmds.append(('SPAN', (start_col, 0), (end_col, 0)))
                style_cmds.append(('BACKGROUND', (start_col, 0), (end_col, 0), colors.HexColor("#E0E0E0")))
            col_index = end_col + 1

        for row in seating_matrix:
            table_content.append([format_cell_content(cell['text'], cell_style) for cell in row])

        col_width = content_width / num_cols + 6
        table = Table(table_content, colWidths=[col_width] * num_cols)

        style_cmds.extend([
            ('GRID', (0, 0), (-1, -1), 2.0, colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 2),
            ('RIGHTPADDING', (0, 0), (-1, -1), 2),
            ('TOPPADDING', (0, 0), (-1, 0), 6),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
            ('TOPPADDING', (0, 1), (-1, -1), 7),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 7),
        ])

        for r_idx, row in enumerate(seating_matrix, start=1):
            for c_idx, cell in enumerate(row):
                bg = cell.get('bg')
                if bg:
                    style_cmds.append(('BACKGROUND', (c_idx, r_idx), (c_idx, r_idx), colors.HexColor(bg)))

        table.setStyle(TableStyle(style_cmds))
        story.append(table)

    doc.build(story, onFirstPage=header_and_footer, onLaterPages=header_and_footer)
    print(f"✅ PDF generated: {filename}")
    return filename