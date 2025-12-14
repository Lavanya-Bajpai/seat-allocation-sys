# pdf_gen/template_manager.py
import json
import hashlib
import os
import sqlite3
from datetime import datetime

# Simple secure_filename fallback
def secure_filename(filename):
    """Basic secure filename function"""
    import re
    filename = re.sub(r'[^\w\s.-]', '', filename).strip()
    return re.sub(r'[-\s]+', '_', filename)

class UserTemplateManager:
    def __init__(self, db_path="pdf_templates.db"):
        self.db_path = db_path
        self.upload_folder = "pdf_gen/data/user_uploads"
        os.makedirs(self.upload_folder, exist_ok=True)
        
        # Initialize database
        from .database import init_database
        init_database()
    
    def get_db_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def get_user_template(self, user_id, template_name='default'):
        """Get template for specific user, fallback to system default"""
        conn = self.get_db_connection()
        cursor = conn.cursor()
        
        try:
            # Try user-specific template first
            cursor.execute('''
                SELECT * FROM user_templates 
                WHERE user_id = ? AND template_name = ?
            ''', (user_id, template_name))
            
            result = cursor.fetchone()
            
            if not result:
                # Fallback to system default
                cursor.execute('''
                    SELECT * FROM user_templates 
                    WHERE user_id = 'system' AND template_name = 'default'
                ''')
                result = cursor.fetchone()
            
            if result:
                return dict(result)
            else:
                return self._get_default_template()
            
        except Exception as e:
            print(f"Template fetch error: {e}")
            return self._get_default_template()
        finally:
            cursor.close()
            conn.close()
    
    def save_user_template(self, user_id, template_data, template_name='default'):
        """Save or update user template"""
        conn = self.get_db_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                INSERT OR REPLACE INTO user_templates (
                    user_id, template_name, dept_name, exam_details, 
                    seating_plan_title, branch_text, room_number,
                    coordinator_name, coordinator_title, banner_image_path,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                user_id, template_name,
                template_data.get('dept_name'),
                template_data.get('exam_details'),
                template_data.get('seating_plan_title'),
                template_data.get('branch_text'),
                template_data.get('room_number'),
                template_data.get('coordinator_name'),
                template_data.get('coordinator_title'),
                template_data.get('banner_image_path'),
                datetime.now().isoformat()
            ))
            conn.commit()
            print(f"✅ Template saved for user: {user_id}")
            return True
            
        except Exception as e:
            print(f"❌ Template save error: {e}")
            conn.rollback()
            raise e
        finally:
            cursor.close()
            conn.close()
    
    def save_user_banner(self, user_id, file, template_name='default'):
        """Save user banner image"""
        if not file or not self._allowed_file(file.filename):
            return None
            
        # Create user-specific directory
        user_folder = os.path.join(self.upload_folder, str(user_id))
        os.makedirs(user_folder, exist_ok=True)
        
        # Generate unique filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"banner_{template_name}_{timestamp}_{secure_filename(file.filename)}"
        file_path = os.path.join(user_folder, filename)
        
        file.save(file_path)
        print(f"✅ Banner saved: {file_path}")
        return file_path
    
    def get_template_hash(self, user_id, template_name='default'):
        """Generate hash for template content (for caching)"""
        template = self.get_user_template(user_id, template_name)
        
        template_data = {
            'dept_name': template.get('dept_name'),
            'exam_details': template.get('exam_details'),
            'seating_plan_title': template.get('seating_plan_title'),
            'branch_text': template.get('branch_text'),
            'room_number': template.get('room_number'),
            'coordinator_name': template.get('coordinator_name'),
            'coordinator_title': template.get('coordinator_title'),
            'banner_image_path': template.get('banner_image_path')
        }
        
        normalized = json.dumps(template_data, sort_keys=True, separators=(',', ':'))
        return hashlib.sha256(normalized.encode('utf-8')).hexdigest()
    
    def _allowed_file(self, filename):
        allowed = {'png', 'jpg', 'jpeg', 'gif', 'bmp'}
        return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed
    
    def _get_default_template(self):
        """Fallback default template"""
        return {
            'dept_name': 'Department of Computer Science & Engineering',
            'exam_details': 'Minor-II Examination (2025 Admitted), November 2025',
            'seating_plan_title': 'Seating Plan',
            'branch_text': 'Branch: B.Tech(CSE & CSD Ist year)',
            'room_number': 'Room no. 103A',
            'coordinator_name': 'Dr. Dheeraj K. Dixit',
            'coordinator_title': 'Dept. Exam Coordinator',
            'banner_image_path': 'data/banner.png'
        }

# Global instance
template_manager = UserTemplateManager()