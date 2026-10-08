from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash, send_file
from flask_pymongo import PyMongo
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import jwt
import datetime
import os
from dotenv import load_dotenv
from bson import ObjectId
import json
import requests
import re
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
if not app.config['SECRET_KEY']:
    raise RuntimeError('Set SECRET_KEY in the environment or .env file before starting the app.')
app.config['MONGO_URI'] = os.getenv('MONGO_URI', 'mongodb://localhost:27017/smart_education')

mongo = PyMongo(app)

# Groq API Configuration
GROQ_API_KEY = os.getenv('GROQ_API_KEY', '')
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"

# Helper function to convert ObjectId to string
def json_util(data):
    if isinstance(data, list):
        for item in data:
            if '_id' in item:
                item['_id'] = str(item['_id'])
    elif isinstance(data, dict):
        if '_id' in data:
            data['_id'] = str(data['_id'])
    return data

# Login required decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please login first', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Role required decorator
def role_required(role):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if session.get('role') != role:
                flash('Access denied', 'error')
                return redirect(url_for('dashboard'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# Helper function to generate assessment using Groq
def generate_assessment_with_groq(skill, assessment_type, user_input=None):
    """
    Generate MCQ assessment using Groq API
    assessment_type: 'skill', 'project', 'certificate'
    """
    # First, try to use Groq API if key is available
    if GROQ_API_KEY and GROQ_API_KEY != '':
        try:
            if assessment_type == 'skill':
                prompt = f"""Generate 5 multiple choice questions to assess a candidate's knowledge in {skill} programming/technology.
                Questions should test practical knowledge and concepts.
                Format each question as JSON with fields: question, options (array of 4), correct_answer, explanation.
                Return as JSON array."""
            elif assessment_type == 'project':
                project_title = user_input.get('title', 'project')
                project_desc = user_input.get('description', '')
                prompt = f"""Generate 5 multiple choice questions based on this project:
                Project Title: {project_title}
                Description: {project_desc}
                
                Create questions testing understanding of technologies, architecture, and implementation details.
                Format each question as JSON with fields: question, options (array of 4), correct_answer, explanation.
                Return as JSON array."""
            else:  # certificate
                cert_name = user_input.get('name', 'certification')
                cert_issuer = user_input.get('issuer', '')
                prompt = f"""Generate 5 multiple choice questions based on {cert_name} certification from {cert_issuer}.
                Focus on core concepts and practical applications.
                Format each question as JSON with fields: question, options (array of 4), correct_answer, explanation.
                Return as JSON array."""
            
            headers = {
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "model": "mixtral-8x7b-32768",
                "messages": [
                    {"role": "system", "content": "You are an expert assessment generator. Generate only valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.7,
                "max_tokens": 2000
            }
            
            response = requests.post(GROQ_API_URL, headers=headers, json=payload, timeout=30)
            
            if response.status_code == 200:
                content = response.json()['choices'][0]['message']['content']
                # Extract JSON from response
                json_match = re.search(r'\[.*\]', content, re.DOTALL)
                if json_match:
                    questions = json.loads(json_match.group())
                    return questions
        except Exception as e:
            print(f"Groq API error: {e}")
    
    # If Groq fails or no API key, return default questions
    print(f"Using default questions for {assessment_type} assessment")
    
    if assessment_type == 'skill':
        return [
            {
                'question': f'What is a key concept in {skill} programming?',
                'options': ['Object-Oriented Programming', 'Database Design', 'Network Security', 'Cloud Computing'],
                'correct_answer': 'Object-Oriented Programming',
                'explanation': 'OOP is fundamental to most programming languages.'
            },
            {
                'question': 'Which of the following is important for software development?',
                'options': ['Code Documentation', 'Social Media', 'Video Games', 'Email'],
                'correct_answer': 'Code Documentation',
                'explanation': 'Documentation helps maintain and understand code.'
            },
            {
                'question': 'What is version control?',
                'options': ['Tracking code changes', 'Writing documentation', 'Testing software', 'Deploying applications'],
                'correct_answer': 'Tracking code changes',
                'explanation': 'Version control systems like Git track code changes.'
            },
            {
                'question': 'What does debugging mean?',
                'options': ['Finding and fixing errors', 'Writing new code', 'Testing performance', 'Deploying to production'],
                'correct_answer': 'Finding and fixing errors',
                'explanation': 'Debugging is the process of identifying and resolving bugs.'
            },
            {
                'question': 'What is an API?',
                'options': ['Application Programming Interface', 'Advanced Programming Interface', 'Application Protocol Interface', 'Advanced Protocol Integration'],
                'correct_answer': 'Application Programming Interface',
                'explanation': 'API allows different software applications to communicate.'
            }
        ]
    elif assessment_type == 'project':
        project_title = user_input.get('title', 'the project') if user_input else 'the project'
        return [
            {
                'question': f'What was the main goal of your project "{project_title}"?',
                'options': ['Solve a specific problem', 'Learn new technology', 'Get good grades', 'Complete requirement'],
                'correct_answer': 'Solve a specific problem',
                'explanation': 'Projects should address specific problems or needs.'
            },
            {
                'question': 'Which development methodology did you use?',
                'options': ['Agile', 'Waterfall', 'Scrum', 'Kanban'],
                'correct_answer': 'Agile',
                'explanation': 'Agile is commonly used for iterative development.'
            },
            {
                'question': 'How did you test your project?',
                'options': ['Unit testing', 'No testing', 'Only manual', 'User testing only'],
                'correct_answer': 'Unit testing',
                'explanation': 'Unit testing ensures individual components work correctly.'
            },
            {
                'question': 'What was your role in the project?',
                'options': ['Full Stack Developer', 'Only Frontend', 'Only Backend', 'Project Manager'],
                'correct_answer': 'Full Stack Developer',
                'explanation': 'Understanding your role shows your contribution.'
            },
            {
                'question': 'What challenge did you face?',
                'options': ['Technical difficulties', 'Team coordination', 'Time management', 'Resource constraints'],
                'correct_answer': 'Technical difficulties',
                'explanation': 'Identifying challenges shows problem-solving skills.'
            }
        ]
    else:  # certificate
        cert_name = user_input.get('name', 'the certification') if user_input else 'the certification'
        return [
            {
                'question': f'What does the {cert_name} certification validate?',
                'options': ['Your knowledge and skills', 'Your work experience', 'Your education', 'Your age'],
                'correct_answer': 'Your knowledge and skills',
                'explanation': 'Certifications validate specific knowledge areas.'
            },
            {
                'question': 'How long is this certification valid?',
                'options': ['1-3 years', 'Lifetime', '5 years', '10 years'],
                'correct_answer': '1-3 years',
                'explanation': 'Many certifications require renewal every few years.'
            },
            {
                'question': 'What is required to maintain certification?',
                'options': ['Continuing education', 'No requirements', 'Annual fee only', 'Retake exam'],
                'correct_answer': 'Continuing education',
                'explanation': 'Most certifications require continuing education credits.'
            },
            {
                'question': 'What topics does this certification cover?',
                'options': ['Core concepts', 'Basic only', 'Advanced only', 'Theory only'],
                'correct_answer': 'Core concepts',
                'explanation': 'Certifications typically cover fundamental concepts.'
            },
            {
                'question': 'How can this certification benefit your career?',
                'options': ['Demonstrates expertise', 'Guarantees job', 'Increases salary automatically', 'No benefit'],
                'correct_answer': 'Demonstrates expertise',
                'explanation': 'Certifications show verified knowledge to employers.'
            }
        ]

# Function to generate job recommendations
def generate_job_recommendations(skills, role, score):
    """Generate job recommendations based on skills and score"""
    recommendations = []
    
    # Sample job database - in production, this would come from your jobs collection
    job_templates = [
        {
            'title': f"{role} Developer",
            'company': "Tech Innovations Inc.",
            'location': "Remote / US",
            'salary_range': "$80,000 - $120,000",
            'required_skills': skills[:3] if skills else ['Programming'],
            'min_score': 60,
            'description': "Looking for a skilled developer to join our dynamic team.",
            'job_type': "Full-time",
            'match_score': score
        },
        {
            'title': "Software Engineer",
            'company': "Digital Solutions Corp",
            'location': "New York, NY",
            'salary_range': "$90,000 - $130,000",
            'required_skills': skills[:2] if skills else ['Software Development'],
            'min_score': 65,
            'description': "Join our engineering team to build scalable solutions.",
            'job_type': "Full-time",
            'match_score': score * 0.95
        },
        {
            'title': "Junior Developer",
            'company': "StartUp Hub",
            'location': "San Francisco, CA",
            'salary_range': "$70,000 - $90,000",
            'required_skills': skills[:2] if skills else ['Coding'],
            'min_score': 50,
            'description': "Great opportunity for recent graduates.",
            'job_type': "Full-time",
            'match_score': score * 0.9
        },
        {
            'title': "Technical Lead",
            'company': "Enterprise Solutions",
            'location': "Chicago, IL",
            'salary_range': "$120,000 - $160,000",
            'required_skills': skills[:3] if skills else ['Leadership', 'Architecture'],
            'min_score': 80,
            'description': "Lead our technical team to success.",
            'job_type': "Full-time",
            'match_score': score * 0.85 if score >= 80 else score * 0.5
        }
    ]
    
    # Add more job templates based on specific skills
    for skill in skills[:2]:  # Add jobs for top skills
        job_templates.append({
            'title': f"{skill} Specialist",
            'company': f"{skill} Technologies",
            'location': "Remote",
            'salary_range': "$85,000 - $110,000",
            'required_skills': [skill],
            'min_score': 55,
            'description': f"Seeking {skill} expert for exciting projects.",
            'job_type': "Full-time",
            'match_score': score * 0.92
        })
    
    # Filter jobs based on score and create recommendations
    for job in job_templates:
        if score >= job['min_score']:
            recommendations.append(job)
    
    # Sort by match score and return top 10
    recommendations.sort(key=lambda x: x['match_score'], reverse=True)
    return recommendations[:10]

# Function to generate smart resume
def generate_smart_resume(user_id):
    """Generate a smart resume PDF for the student"""
    user = mongo.db.users.find_one({'_id': user_id})
    profile = mongo.db.student_profiles.find_one({'user_id': user_id})
    results = list(mongo.db.assessment_results.find({'user_id': user_id}))
    
    if not user or not profile:
        return None
    
    # Create resumes directory if it doesn't exist
    os.makedirs('uploads/resumes', exist_ok=True)
    
    filename = f"resume_{user_id}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    filepath = os.path.join('uploads', 'resumes', filename)
    
    doc = SimpleDocTemplate(filepath, pagesize=letter)
    styles = getSampleStyleSheet()
    story = []
    
    # Title
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#667eea'),
        spaceAfter=30
    )
    story.append(Paragraph(user['name'], title_style))
    
    # Contact Info
    contact_style = ParagraphStyle('Contact', parent=styles['Normal'], fontSize=10, textColor=colors.grey)
    contact_info = f"Email: {user['email']} | Phone: {profile.get('phone', 'N/A')} | Location: {profile.get('location', 'N/A')}"
    story.append(Paragraph(contact_info, contact_style))
    story.append(Spacer(1, 20))
    
    # Professional Summary
    story.append(Paragraph("Professional Summary", styles['Heading2']))
    summary = f"{profile.get('bio', '')} Overall Skill Score: {profile.get('overall_score', 0):.1f}% - Level: {profile.get('skill_level', 'Beginner')}"
    story.append(Paragraph(summary, styles['Normal']))
    story.append(Spacer(1, 15))
    
    # Skills
    onboarding_data = profile.get('onboarding_data', {})
    skills = onboarding_data.get('skills', [])
    if skills:
        story.append(Paragraph("Technical Skills", styles['Heading2']))
        skills_text = ", ".join(skills)
        story.append(Paragraph(skills_text, styles['Normal']))
        story.append(Spacer(1, 15))
    
    # Assessment Scores
    if results:
        story.append(Paragraph("Assessment Scores", styles['Heading2']))
        data = [['Assessment', 'Score', 'Date']]
        for result in results[:5]:  # Show last 5 assessments
            data.append([
                result['assessment_title'][:30],
                f"{result['score_percentage']:.1f}%",
                result['date_taken'].strftime('%Y-%m-%d')
            ])
        
        table = Table(data)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        story.append(table)
        story.append(Spacer(1, 15))
    
    # Projects
    if onboarding_data.get('project_title'):
        story.append(Paragraph("Key Project", styles['Heading2']))
        project_text = f"<b>{onboarding_data['project_title']}</b><br/>"
        project_text += f"Technologies: {onboarding_data.get('project_technologies', 'N/A')}<br/>"
        project_text += f"Description: {onboarding_data.get('project_description', '')}"
        story.append(Paragraph(project_text, styles['Normal']))
        story.append(Spacer(1, 15))
    
    # Certifications
    if onboarding_data.get('certificate_name'):
        story.append(Paragraph("Certifications", styles['Heading2']))
        cert_text = f"<b>{onboarding_data['certificate_name']}</b> - {onboarding_data.get('certificate_issuer', '')} ({onboarding_data.get('certificate_date', '')})"
        story.append(Paragraph(cert_text, styles['Normal']))
    
    doc.build(story)
    
    # Update profile with resume path
    mongo.db.student_profiles.update_one(
        {'user_id': user_id},
        {'$set': {'resume_path': filepath, 'resume_generated_date': datetime.datetime.now()}}
    )
    
    return filepath

# Routes
@app.route('/')
def home():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        try:
            name = request.form.get('name')
            email = request.form.get('email')
            password = request.form.get('password')
            role = request.form.get('role')
            
            # Check if user exists
            existing_user = mongo.db.users.find_one({'email': email})
            if existing_user:
                flash('Email already registered', 'error')
                return redirect(url_for('register'))
            
            # Create user
            user = {
                'name': name,
                'email': email,
                'password': generate_password_hash(password),
                'role': role,
                'created_at': datetime.datetime.now()
            }
            
            result = mongo.db.users.insert_one(user)
            
            # Create role-specific profile
            if role == 'student':
                profile = {
                    'user_id': result.inserted_id,
                    'projects': [],
                    'certifications': [],
                    'achievements': [],
                    'assessments': [],
                    'skill_scores': {},
                    'overall_score': 0,
                    'resume_url': ''
                }
                mongo.db.student_profiles.insert_one(profile)
            elif role == 'recruiter':
                profile = {
                    'user_id': result.inserted_id,
                    'company_name': request.form.get('company_name', ''),
                    'company_website': request.form.get('company_website', ''),
                    'jobs_posted': []
                }
                mongo.db.recruiter_profiles.insert_one(profile)
            
            flash('Registration successful! Please login.', 'success')
            return redirect(url_for('login'))
            
        except Exception as e:
            flash(f'Registration failed: {str(e)}', 'error')
            return redirect(url_for('register'))
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        user = mongo.db.users.find_one({'email': email})
        
        if user and check_password_hash(user['password'], password):
            session['user_id'] = str(user['_id'])
            session['user_name'] = user['name']
            session['role'] = user['role']
            session['email'] = user['email']
            
            flash('Login successful!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid email or password', 'error')
            return redirect(url_for('login'))
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully', 'success')
    return redirect(url_for('home'))

@app.route('/dashboard')
@login_required
def dashboard():
    role = session.get('role')
    if role == 'student':
        return redirect(url_for('student_dashboard'))
    elif role == 'recruiter':
        return redirect(url_for('recruiter_dashboard'))
    elif role == 'admin':
        return redirect(url_for('admin_dashboard'))
    return redirect(url_for('home'))

# ============ STUDENT ROUTES ============

@app.route('/student/dashboard')
@login_required
@role_required('student')
def student_dashboard():
    user_id = ObjectId(session['user_id'])
    profile = mongo.db.student_profiles.find_one({'user_id': user_id})
    
    # Check if onboarding is needed
    if not profile:
        flash('Please complete your onboarding', 'info')
        return redirect(url_for('student_onboarding'))
    
    # Check if onboarding is completed
    if not profile.get('onboarding_completed', False):
        # Check if there are assessments generated but not completed
        onboarding_data = profile.get('onboarding_data', {})
        generated_assessments = onboarding_data.get('generated_assessments', [])
        
        if generated_assessments:
            # Check which assessments are completed
            completed_assessments = list(mongo.db.assessment_results.find({'user_id': user_id}))
            completed_ids = [str(r['assessment_id']) for r in completed_assessments]
            
            # Find first incomplete assessment
            for i, assessment_id in enumerate(generated_assessments):
                if assessment_id not in completed_ids:
                    flash(f'Please complete your remaining assessments', 'info')
                    return redirect(url_for('take_onboarding_assessment', index=i))
            
            # All assessments completed but flag not set - set it now
            # Calculate final score and complete
            all_results = list(mongo.db.assessment_results.find({'user_id': user_id}))
            if all_results:
                total_score = sum(r['score_percentage'] for r in all_results)
                overall_score = total_score / len(all_results)
                
                if overall_score >= 80:
                    skill_level = "Advanced"
                elif overall_score >= 60:
                    skill_level = "Intermediate"
                elif overall_score >= 40:
                    skill_level = "Beginner"
                else:
                    skill_level = "Novice"
                
                mongo.db.student_profiles.update_one(
                    {'user_id': user_id},
                    {'$set': {
                        'overall_score': overall_score,
                        'skill_level': skill_level,
                        'onboarding_completed': True,
                        'onboarding_completed_date': datetime.datetime.now()
                    }}
                )
                
                try:
                    generate_smart_resume(user_id)
                except Exception as e:
                    print(f"Error generating resume: {e}")
                
                session['show_welcome'] = True
                profile = mongo.db.student_profiles.find_one({'user_id': user_id})
            else:
                flash('Please complete your onboarding assessments', 'info')
                return redirect(url_for('student_onboarding'))
        else:
            flash('Please complete your onboarding', 'info')
            return redirect(url_for('student_onboarding'))
    
    # If we get here, onboarding is completed
    # Get recent job recommendations for the dashboard
    recent_jobs = list(mongo.db.job_recommendations.find(
        {'student_id': user_id}
    ).sort('recommended_date', -1).limit(5))
    
    # Get recent assessment results
    recent_assessments = list(mongo.db.assessment_results.find(
        {'user_id': user_id}
    ).sort('date_taken', -1).limit(5))
    
    # Get statistics
    total_assessments = mongo.db.assessment_results.count_documents({'user_id': user_id})
    average_score = profile.get('overall_score', 0)
    total_jobs_recommended = mongo.db.job_recommendations.count_documents({'student_id': user_id})
    
    stats = {
        'total_assessments': total_assessments,
        'average_score': round(average_score, 1),
        'skill_level': profile.get('skill_level', 'Beginner'),
        'total_jobs': total_jobs_recommended
    }
    
    if profile:
        profile = json_util(profile)
    
    recent_jobs = json_util(recent_jobs)
    recent_assessments = json_util(recent_assessments)
    
    # Check if this is first login after onboarding
    show_welcome = session.pop('show_welcome', False)
    
    return render_template('student/dashboard.html', 
                         profile=profile, 
                         stats=stats,
                         recent_jobs=recent_jobs,
                         recent_assessments=recent_assessments,
                         show_welcome=show_welcome)

# ============ ONBOARDING ROUTES ============

@app.route('/student/onboarding', methods=['GET', 'POST'])
@login_required
@role_required('student')
def student_onboarding():
    user_id = ObjectId(session['user_id'])
    profile = mongo.db.student_profiles.find_one({'user_id': user_id})
    
    # Check if onboarding is already completed
    if profile and profile.get('onboarding_completed', False):
        flash('You have already completed onboarding!', 'info')
        return redirect(url_for('student_dashboard'))
    
    if request.method == 'POST':
        try:
            # Collect onboarding data
            onboarding_data = {
                'role_specific': request.form.get('role_specific'),
                'experience': request.form.get('experience', '0'),
                'skills': [skill.strip() for skill in request.form.get('skills', '').split(',') if skill.strip()],
                'project_title': request.form.get('project_title'),
                'project_description': request.form.get('project_description'),
                'project_technologies': request.form.get('project_technologies'),
                'certificate_name': request.form.get('certificate_name'),
                'certificate_issuer': request.form.get('certificate_issuer'),
                'certificate_date': request.form.get('certificate_date'),
                'onboarding_completed': False,
                'assessments_generated': False
            }
            
            # Handle resume upload
            if 'resume_file' in request.files:
                file = request.files['resume_file']
                if file and file.filename:
                    # Create uploads directory if it doesn't exist
                    os.makedirs('uploads', exist_ok=True)
                    filename = f"{session['user_id']}_{file.filename}"
                    filepath = os.path.join('uploads', filename)
                    file.save(filepath)
                    onboarding_data['resume_path'] = filepath
                    onboarding_data['resume_filename'] = file.filename
            
            # Save onboarding data
            mongo.db.student_profiles.update_one(
                {'user_id': user_id},
                {'$set': {'onboarding_data': onboarding_data}},
                upsert=True
            )
            
            # Generate assessments based on user input
            flash('Onboarding data saved! Generating assessments...', 'info')
            return redirect(url_for('generate_onboarding_assessments'))
            
        except Exception as e:
            flash(f'Error saving onboarding data: {str(e)}', 'error')
            return redirect(url_for('student_onboarding'))
    
    return render_template('student/onboarding.html')

@app.route('/student/generate-assessments')
@login_required
@role_required('student')
def generate_onboarding_assessments():
    print("=" * 50)
    print("GENERATE ASSESSMENTS CALLED")
    print("=" * 50)
    
    user_id = ObjectId(session['user_id'])
    profile = mongo.db.student_profiles.find_one({'user_id': user_id})
    
    if not profile or 'onboarding_data' not in profile:
        print("No onboarding data found!")
        flash('Please complete onboarding first', 'error')
        return redirect(url_for('student_onboarding'))
    
    onboarding_data = profile['onboarding_data']
    print(f"Onboarding data: {onboarding_data}")
    
    if onboarding_data.get('assessments_generated', False):
        print("Assessments already generated!")
        flash('Assessments have already been generated!', 'info')
        return redirect(url_for('student_assessment'))
    
    generated_assessments = []
    
    # Generate Skill-based assessment
    if onboarding_data.get('skills'):
        primary_skill = onboarding_data['skills'][0] if onboarding_data['skills'] else onboarding_data.get('role_specific', 'Programming')
        print(f"Generating skill assessment for: {primary_skill}")
        skill_questions = generate_assessment_with_groq(primary_skill, 'skill')
        
        if skill_questions:
            skill_assessment = {
                'title': f"{primary_skill} Skills Assessment",
                'type': 'skill_based',
                'category': primary_skill,
                'description': f"Assessment to evaluate your {primary_skill} knowledge and skills",
                'difficulty': 'Intermediate',
                'duration': 30,
                'questions': skill_questions,
                'created_date': datetime.datetime.now(),
                'user_id': user_id,
                'is_onboarding': True
            }
            result = mongo.db.assessments.insert_one(skill_assessment)
            generated_assessments.append(str(result.inserted_id))
            print(f"Skill assessment created: {result.inserted_id}")
        else:
            print("Failed to generate skill assessment - using default")
            # Create a default assessment if Groq fails
            default_questions = [
                {
                    'question': 'What is your primary programming language?',
                    'options': ['Python', 'Java', 'JavaScript', 'C++'],
                    'correct_answer': 'Python',
                    'explanation': 'This is a sample question.'
                },
                {
                    'question': 'Which of the following is a key skill for developers?',
                    'options': ['Problem Solving', 'Cooking', 'Painting', 'Singing'],
                    'correct_answer': 'Problem Solving',
                    'explanation': 'Problem solving is essential.'
                }
            ]
            skill_assessment = {
                'title': f"{primary_skill} Skills Assessment",
                'type': 'skill_based',
                'category': primary_skill,
                'description': f"Assessment to evaluate your {primary_skill} knowledge",
                'difficulty': 'Intermediate',
                'duration': 30,
                'questions': default_questions,
                'created_date': datetime.datetime.now(),
                'user_id': user_id,
                'is_onboarding': True
            }
            result = mongo.db.assessments.insert_one(skill_assessment)
            generated_assessments.append(str(result.inserted_id))
    
    # Generate Project-based assessment
    if onboarding_data.get('project_title'):
        print(f"Generating project assessment for: {onboarding_data['project_title']}")
        project_questions = generate_assessment_with_groq(
            None, 
            'project', 
            {'title': onboarding_data['project_title'], 'description': onboarding_data.get('project_description', '')}
        )
        
        if project_questions:
            project_assessment = {
                'title': f"Project Assessment: {onboarding_data['project_title']}",
                'type': 'project_based',
                'category': 'Project Evaluation',
                'description': f"Assessment based on your project: {onboarding_data['project_title']}",
                'difficulty': 'Intermediate',
                'duration': 30,
                'questions': project_questions,
                'created_date': datetime.datetime.now(),
                'user_id': user_id,
                'is_onboarding': True
            }
            result = mongo.db.assessments.insert_one(project_assessment)
            generated_assessments.append(str(result.inserted_id))
            print(f"Project assessment created: {result.inserted_id}")
    
    # Generate Certificate-based assessment
    if onboarding_data.get('certificate_name'):
        print(f"Generating certificate assessment for: {onboarding_data['certificate_name']}")
        cert_questions = generate_assessment_with_groq(
            None,
            'certificate',
            {'name': onboarding_data['certificate_name'], 'issuer': onboarding_data.get('certificate_issuer', '')}
        )
        
        if cert_questions:
            cert_assessment = {
                'title': f"Certificate Assessment: {onboarding_data['certificate_name']}",
                'type': 'certificate_based',
                'category': 'Certification',
                'description': f"Assessment based on your {onboarding_data['certificate_name']} certification",
                'difficulty': 'Intermediate',
                'duration': 30,
                'questions': cert_questions,
                'created_date': datetime.datetime.now(),
                'user_id': user_id,
                'is_onboarding': True
            }
            result = mongo.db.assessments.insert_one(cert_assessment)
            generated_assessments.append(str(result.inserted_id))
            print(f"Certificate assessment created: {result.inserted_id}")
    
    print(f"Total assessments generated: {len(generated_assessments)}")
    
    # Update profile with generated assessments
    mongo.db.student_profiles.update_one(
        {'user_id': user_id},
        {'$set': {
            'onboarding_data.assessments_generated': True,
            'onboarding_data.generated_assessments': generated_assessments,
            'onboarding_completed': False
        }}
    )
    
    if generated_assessments:
        flash(f'✅ Generated {len(generated_assessments)} assessment(s) for you! Please complete them.', 'success')
        print(f"Redirecting to first assessment (index 0)")
        return redirect(url_for('take_onboarding_assessment', index=0))
    else:
        print("ERROR: No assessments generated!")
        flash('Could not generate assessments. Please try again.', 'error')
        return redirect(url_for('student_onboarding'))
@app.route('/test-dashboard')
@login_required
@role_required('student')
def test_dashboard():
    return "Dashboard is working! If you see this, the redirect should work."
@app.route('/student/onboarding-assessment/<int:index>')
@login_required
@role_required('student')
def take_onboarding_assessment(index):
    user_id = ObjectId(session['user_id'])
    profile = mongo.db.student_profiles.find_one({'user_id': user_id})
    
    if not profile or 'onboarding_data' not in profile:
        flash('Please complete onboarding first', 'error')
        return redirect(url_for('student_onboarding'))
    
    generated_assessments = profile['onboarding_data'].get('generated_assessments', [])
    
    # Check if already completed
    if profile.get('onboarding_completed', False):
        flash('You have already completed onboarding!', 'info')
        return redirect(url_for('student_dashboard'))
    
    if index >= len(generated_assessments):
        # All assessments completed - redirect to dashboard (completion will happen in submit)
        flash('All assessments completed!', 'success')
        return redirect(url_for('student_dashboard'))
    
    assessment_id = generated_assessments[index]
    assessment = mongo.db.assessments.find_one({'_id': ObjectId(assessment_id)})
    
    if not assessment:
        flash('Assessment not found', 'error')
        return redirect(url_for('student_dashboard'))
    
    # Convert ObjectId to string for template
    assessment['_id'] = str(assessment['_id'])
    assessment['current_index'] = index
    assessment['total_assessments'] = len(generated_assessments)
    
    return render_template('student/onboarding_assessment.html', assessment=assessment)

@app.route('/student/submit-onboarding-assessment', methods=['POST'])
@login_required
@role_required('student')
def submit_onboarding_assessment():
    print("=" * 50)
    print("SUBMIT ONBOARDING ASSESSMENT CALLED")
    print("=" * 50)
    
    user_id = ObjectId(session['user_id'])
    assessment_id = request.form.get('assessment_id')
    current_index = int(request.form.get('current_index', 0))
    
    print(f"User ID: {user_id}")
    print(f"Assessment ID: {assessment_id}")
    print(f"Current Index: {current_index}")
    
    assessment = mongo.db.assessments.find_one({'_id': ObjectId(assessment_id)})
    
    if not assessment:
        print("Assessment not found!")
        flash('Assessment not found', 'error')
        return redirect(url_for('student_onboarding'))
    
    print(f"Assessment found: {assessment['title']}")
    
    # Calculate score
    total_questions = len(assessment['questions'])
    score = 0
    answers = []
    
    for i, question in enumerate(assessment['questions']):
        user_answer = request.form.get(f'question_{i}')
        is_correct = (user_answer == question['correct_answer'])
        if is_correct:
            score += 1
        answers.append({
            'question': question['question'],
            'user_answer': user_answer,
            'correct_answer': question['correct_answer'],
            'is_correct': is_correct
        })
    
    score_percentage = (score / total_questions) * 100
    print(f"Score: {score}/{total_questions} = {score_percentage}%")
    
    # Save result
    result = {
        'user_id': user_id,
        'assessment_id': ObjectId(assessment_id),
        'assessment_title': assessment['title'],
        'assessment_type': assessment.get('type', 'general'),
        'score': score,
        'total_questions': total_questions,
        'score_percentage': score_percentage,
        'answers': answers,
        'date_taken': datetime.datetime.now()
    }
    
    mongo.db.assessment_results.insert_one(result)
    print("Assessment result saved")
    
    # Get updated profile
    profile = mongo.db.student_profiles.find_one({'user_id': user_id})
    generated_assessments = profile['onboarding_data'].get('generated_assessments', [])
    
    print(f"Generated assessments: {generated_assessments}")
    print(f"Current index: {current_index}")
    print(f"Next index would be: {current_index + 1}")
    print(f"Total assessments: {len(generated_assessments)}")
    
    next_index = current_index + 1
    
    if next_index >= len(generated_assessments):
        print("=" * 50)
        print("LAST ASSESSMENT COMPLETED! Calculating final score...")
        print("=" * 50)
        
        # Get all assessment results for this user
        all_results = list(mongo.db.assessment_results.find({'user_id': user_id}))
        print(f"Total results found: {len(all_results)}")
        
        if all_results:
            # Calculate overall score
            total_score = sum(r['score_percentage'] for r in all_results)
            overall_score = total_score / len(all_results)
            print(f"Overall score: {overall_score}%")
            
            # Determine skill level
            if overall_score >= 80:
                skill_level = "Advanced"
                level_description = "Expert level - Ready for senior positions"
            elif overall_score >= 60:
                skill_level = "Intermediate"
                level_description = "Good foundation - Ready for mid-level positions"
            elif overall_score >= 40:
                skill_level = "Beginner"
                level_description = "Basic understanding - Focus on learning"
            else:
                skill_level = "Novice"
                level_description = "Needs improvement - Consider training courses"
            
            print(f"Skill level: {skill_level}")
            
            # Extract skills from profile
            onboarding_data = profile.get('onboarding_data', {})
            skills = onboarding_data.get('skills', [])
            role_specific = onboarding_data.get('role_specific', '')
            
            # Generate job recommendations
            recommended_jobs = generate_job_recommendations(skills, role_specific, overall_score)
            print(f"Generated {len(recommended_jobs)} job recommendations")
            
            # Update student profile with final data
            update_result = mongo.db.student_profiles.update_one(
                {'user_id': user_id},
                {'$set': {
                    'overall_score': overall_score,
                    'skill_level': skill_level,
                    'level_description': level_description,
                    'onboarding_completed': True,
                    'onboarding_completed_date': datetime.datetime.now(),
                    'recommended_jobs': recommended_jobs[:10]
                }}
            )
            print(f"Profile updated: {update_result.modified_count} document(s) modified")
            
            # Generate smart resume
            try:
                generate_smart_resume(user_id)
                print("Resume generated successfully")
            except Exception as e:
                print(f"Error generating resume: {e}")
            
            # Set session flag for welcome message
            session['show_welcome'] = True
            session['onboarding_complete'] = True
            
            print("Redirecting to student_dashboard...")
            flash(f'🎉 Congratulations! You have completed onboarding with {overall_score:.1f}% score!', 'success')
            return redirect(url_for('student_dashboard'))
        else:
            print("ERROR: No results found!")
            flash('Error calculating scores. Please contact support.', 'error')
            return redirect(url_for('student_dashboard'))
    else:
        print(f"Moving to next assessment: index {next_index}")
        flash(f'✅ Assessment completed! Score: {score_percentage:.1f}%', 'success')
        return redirect(url_for('take_onboarding_assessment', index=next_index))
    
@app.route('/student/complete-onboarding')
@login_required
@role_required('student')
def complete_onboarding():
    # This route is now deprecated - all logic is in submit_onboarding_assessment
    # Just redirect to dashboard
    flash('Onboarding completed successfully!', 'success')
    return redirect(url_for('student_dashboard'))



# @app.route('/student/complete-onboarding')
# @login_required
# @role_required('student')
# def complete_onboarding():
#     user_id = ObjectId(session['user_id'])
#     profile = mongo.db.student_profiles.find_one({'user_id': user_id})
    
#     # Get all assessment results
#     results = list(mongo.db.assessment_results.find({'user_id': user_id}))
    
#     if not results:
#         flash('Please complete your assessments first', 'error')
#         return redirect(url_for('student_onboarding'))
    
#     # Calculate overall score
#     total_score = sum(r['score_percentage'] for r in results)
#     overall_score = total_score / len(results)
    
#     # Determine skill level
#     if overall_score >= 80:
#         skill_level = "Advanced"
#         level_description = "Expert level - Ready for senior positions"
#     elif overall_score >= 60:
#         skill_level = "Intermediate"
#         level_description = "Good foundation - Ready for mid-level positions"
#     elif overall_score >= 40:
#         skill_level = "Beginner"
#         level_description = "Basic understanding - Focus on learning"
#     else:
#         skill_level = "Novice"
#         level_description = "Needs improvement - Consider training courses"
    
#     # Extract skills from profile
#     onboarding_data = profile.get('onboarding_data', {})
#     skills = onboarding_data.get('skills', [])
#     role_specific = onboarding_data.get('role_specific', '')
    
#     # Generate job recommendations based on skills and score
#     recommended_jobs = generate_job_recommendations(skills, role_specific, overall_score)
    
#     # Save job recommendations to database
#     for job in recommended_jobs:
#         job_recommendation = {
#             'student_id': user_id,
#             'job_title': job['title'],
#             'company': job['company'],
#             'location': job['location'],
#             'salary_range': job['salary_range'],
#             'description': job['description'],
#             'job_type': job['job_type'],
#             'match_score': job['match_score'],
#             'recommended_date': datetime.datetime.now(),
#             'is_viewed': False
#         }
#         mongo.db.job_recommendations.insert_one(job_recommendation)
    
#     # Update student profile
#     mongo.db.student_profiles.update_one(
#         {'user_id': user_id},
#         {'$set': {
#             'overall_score': overall_score,
#             'skill_level': skill_level,
#             'level_description': level_description,
#             'onboarding_completed': True,
#             'onboarding_completed_date': datetime.datetime.now(),
#             'recommended_jobs': recommended_jobs[:10]
#         }}
#     )
    
#     # Generate smart resume
#     try:
#         generate_smart_resume(user_id)
#     except Exception as e:
#         print(f"Error generating resume: {e}")
    
#     # Store completion data in session for the completion page
#     session['onboarding_complete'] = True
#     session['overall_score'] = overall_score
#     session['skill_level'] = skill_level
    
#     # Flash success message
#     flash(f'🎉 Onboarding Complete! Your overall score: {overall_score:.1f}% - Level: {skill_level}', 'success')
    
#     # Redirect to dashboard
#     return redirect(url_for('student_dashboard'))

@app.route('/student/download-resume')
@login_required
@role_required('student')
def download_resume():
    user_id = ObjectId(session['user_id'])
    profile = mongo.db.student_profiles.find_one({'user_id': user_id})
    
    if not profile or not profile.get('resume_path'):
        flash('Resume not found. Please complete onboarding first.', 'error')
        return redirect(url_for('student_onboarding'))
    
    resume_path = profile['resume_path']
    
    if not os.path.exists(resume_path):
        flash('Resume file not found. Generating new resume...', 'info')
        generate_smart_resume(user_id)
        profile = mongo.db.student_profiles.find_one({'user_id': user_id})
        resume_path = profile.get('resume_path')
    
    if not resume_path or not os.path.exists(resume_path):
        flash('Could not generate resume. Please try again.', 'error')
        return redirect(url_for('student_dashboard'))
    
    return send_file(
        resume_path,
        as_attachment=True,
        download_name=f"resume_{session['user_name']}_{datetime.datetime.now().strftime('%Y%m%d')}.pdf"
    )

@app.route('/student/profile', methods=['GET', 'POST'])
@login_required
@role_required('student')
def student_profile():
    user_id = ObjectId(session['user_id'])
    
    if request.method == 'POST':
        update_data = {}
        
        # Basic Info
        update_data['phone'] = request.form.get('phone', '')
        update_data['location'] = request.form.get('location', '')
        update_data['bio'] = request.form.get('bio', '')
        update_data['linkedin'] = request.form.get('linkedin', '')
        update_data['github'] = request.form.get('github', '')
        
        # Education
        degrees = request.form.getlist('degree')
        institutions = request.form.getlist('institution')
        years = request.form.getlist('year')
        grades = request.form.getlist('grade')
        
        education = []
        for i in range(len(degrees)):
            if degrees[i] and institutions[i]:
                education.append({
                    'degree': degrees[i],
                    'institution': institutions[i],
                    'year': years[i] if i < len(years) else '',
                    'grade': grades[i] if i < len(grades) else ''
                })
        update_data['education'] = education
        
        # Projects
        project_titles = request.form.getlist('project_title')
        project_descriptions = request.form.getlist('project_description')
        project_techs = request.form.getlist('project_tech')
        project_links = request.form.getlist('project_link')
        
        projects = []
        for i in range(len(project_titles)):
            if project_titles[i]:
                projects.append({
                    'title': project_titles[i],
                    'description': project_descriptions[i] if i < len(project_descriptions) else '',
                    'technologies': project_techs[i] if i < len(project_techs) else '',
                    'link': project_links[i] if i < len(project_links) else '',
                    'date': datetime.datetime.now()
                })
        update_data['projects'] = projects
        
        # Certifications
        cert_names = request.form.getlist('cert_name')
        cert_issuers = request.form.getlist('cert_issuer')
        cert_dates = request.form.getlist('cert_date')
        cert_links = request.form.getlist('cert_link')
        
        certifications = []
        for i in range(len(cert_names)):
            if cert_names[i]:
                certifications.append({
                    'name': cert_names[i],
                    'issuer': cert_issuers[i] if i < len(cert_issuers) else '',
                    'date': cert_dates[i] if i < len(cert_dates) else '',
                    'link': cert_links[i] if i < len(cert_links) else ''
                })
        update_data['certifications'] = certifications
        
        # Achievements
        achievement_titles = request.form.getlist('achievement_title')
        achievement_descriptions = request.form.getlist('achievement_description')
        achievement_dates = request.form.getlist('achievement_date')
        
        achievements = []
        for i in range(len(achievement_titles)):
            if achievement_titles[i]:
                achievements.append({
                    'title': achievement_titles[i],
                    'description': achievement_descriptions[i] if i < len(achievement_descriptions) else '',
                    'date': achievement_dates[i] if i < len(achievement_dates) else ''
                })
        update_data['achievements'] = achievements
        
        # Skills
        skills = request.form.getlist('skills')
        skills = [s for s in skills if s.strip()]
        update_data['skills'] = skills
        
        # Handle resume upload
        if 'resume_file' in request.files:
            file = request.files['resume_file']
            if file and file.filename:
                update_data['resume_filename'] = file.filename
        
        # Update the profile
        mongo.db.student_profiles.update_one(
            {'user_id': user_id},
            {'$set': update_data},
            upsert=True
        )
        
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('student_profile'))
    
    profile = mongo.db.student_profiles.find_one({'user_id': user_id})
    profile = json_util(profile) if profile else {}
    return render_template('student/profile.html', profile=profile)

@app.route('/student/assessment')
@login_required
@role_required('student')
def student_assessment():
    assessments = list(mongo.db.assessments.find())
    assessments = json_util(assessments)
    return render_template('student/assessment.html', assessments=assessments)

@app.route('/student/take_assessment/<assessment_id>', methods=['GET', 'POST'])
@login_required
@role_required('student')
def take_assessment(assessment_id):
    assessment = mongo.db.assessments.find_one({'_id': ObjectId(assessment_id)})
    
    if not assessment:
        flash('Assessment not found', 'error')
        return redirect(url_for('student_assessment'))
    
    if request.method == 'POST':
        total_questions = len(assessment['questions'])
        score = 0
        answers = []
        
        for i, question in enumerate(assessment['questions']):
            user_answer = request.form.get(f'question_{i}')
            is_correct = (user_answer == question['correct_answer'])
            if is_correct:
                score += 1
            answers.append({
                'question': question['question'],
                'user_answer': user_answer,
                'correct_answer': question['correct_answer'],
                'is_correct': is_correct
            })
        
        score_percentage = (score / total_questions) * 100
        
        result = {
            'user_id': ObjectId(session['user_id']),
            'assessment_id': ObjectId(assessment_id),
            'assessment_title': assessment['title'],
            'score': score,
            'total_questions': total_questions,
            'score_percentage': score_percentage,
            'answers': answers,
            'date_taken': datetime.datetime.now()
        }
        
        mongo.db.assessment_results.insert_one(result)
        
        student_profile = mongo.db.student_profiles.find_one({'user_id': ObjectId(session['user_id'])})
        skill_scores = student_profile.get('skill_scores', {})
        
        category = assessment.get('category', 'general')
        skill_scores[category] = score_percentage
        
        if skill_scores:
            overall_score = sum(skill_scores.values()) / len(skill_scores)
        else:
            overall_score = score_percentage
        
        mongo.db.student_profiles.update_one(
            {'user_id': ObjectId(session['user_id'])},
            {'$set': {
                'skill_scores': skill_scores,
                'overall_score': overall_score
            }}
        )
        
        flash(f'Assessment completed! Your score: {score_percentage:.2f}%', 'success')
        return redirect(url_for('student_assessment_results'))
    
    assessment['_id'] = str(assessment['_id'])
    return render_template('student/take_assessment.html', assessment=assessment)

@app.route('/student/feedback', methods=['GET'])
@login_required
@role_required('student')
def student_feedback():
    applications = list(mongo.db.applications.find({'student_id': ObjectId(session['user_id'])}))
    for app in applications:
        job = mongo.db.jobs.find_one({'_id': app['job_id']})
        app['job_title'] = job['title'] if job else 'Unknown'
    
    feedbacks = list(mongo.db.feedback.find({'student_id': ObjectId(session['user_id'])}).sort('date', -1))
    feedbacks = json_util(feedbacks)
    
    return render_template('student/feedback.html', applications=applications, feedbacks=feedbacks)

@app.route('/student/results')
@login_required
@role_required('student')
def student_assessment_results():
    results = list(mongo.db.assessment_results.find({'user_id': ObjectId(session['user_id'])}))
    results = json_util(results)
    return render_template('student/results.html', results=results)

@app.route('/student/resume')
@login_required
@role_required('student')
def student_resume():
    user_id = ObjectId(session['user_id'])
    user = mongo.db.users.find_one({'_id': user_id})
    profile = mongo.db.student_profiles.find_one({'user_id': user_id})
    results = list(mongo.db.assessment_results.find({'user_id': user_id}))
    results = json_util(results)
    
    return render_template('student/resume.html', user=user, profile=profile, results=results)

@app.route('/student/feedback/application', methods=['POST'])
@login_required
@role_required('student')
def submit_application_feedback():
    feedback = {
        'student_id': ObjectId(session['user_id']),
        'student_name': session['user_name'],
        'type': 'application',
        'application_id': ObjectId(request.form.get('job_id')),
        'rating': int(request.form.get('rating')),
        'feedback': request.form.get('feedback'),
        'date': datetime.datetime.now()
    }
    mongo.db.feedback.insert_one(feedback)
    flash('Thank you for your feedback!', 'success')
    return redirect(url_for('student_feedback'))

@app.route('/student/feedback/interview', methods=['POST'])
@login_required
@role_required('student')
def submit_interview_feedback():
    feedback = {
        'student_id': ObjectId(session['user_id']),
        'student_name': session['user_name'],
        'type': 'interview',
        'interview_title': request.form.get('interview_title'),
        'rating': int(request.form.get('rating')),
        'feedback': request.form.get('feedback'),
        'suggestions': request.form.get('suggestions', ''),
        'date': datetime.datetime.now()
    }
    mongo.db.feedback.insert_one(feedback)
    flash('Thank you for sharing your interview experience!', 'success')
    return redirect(url_for('student_feedback'))

# @app.route('/student/jobs')
# @login_required
# @role_required('student')
# def student_jobs():
#     profile = mongo.db.student_profiles.find_one({'user_id': ObjectId(session['user_id'])})
#     overall_score = profile.get('overall_score', 0) if profile else 0
    
#     jobs = list(mongo.db.jobs.find({'min_score': {'$lte': overall_score}}))
#     jobs = json_util(jobs)
    
#     return render_template('student/jobs.html', jobs=jobs)

@app.route('/student/apply/<job_id>', methods=['POST'])
@login_required
@role_required('student')
def apply_job(job_id):
    existing_application = mongo.db.applications.find_one({
        'job_id': ObjectId(job_id),
        'student_id': ObjectId(session['user_id'])
    })
    
    if existing_application:
        flash('You have already applied for this job', 'warning')
        return redirect(url_for('student_jobs'))
    
    application = {
        'job_id': ObjectId(job_id),
        'student_id': ObjectId(session['user_id']),
        'student_name': session['user_name'],
        'applied_date': datetime.datetime.now(),
        'status': 'pending'
    }
    
    mongo.db.applications.insert_one(application)
    
    mongo.db.jobs.update_one(
        {'_id': ObjectId(job_id)},
        {'$inc': {'applications_count': 1}}
    )
    
    flash('Application submitted successfully!', 'success')
    return redirect(url_for('student_jobs'))

# ============ RECRUITER ROUTES ============

@app.route('/recruiter/dashboard')
@login_required
@role_required('recruiter')
def recruiter_dashboard():
    user_id = ObjectId(session['user_id'])
    
    recruiter_profile = mongo.db.recruiter_profiles.find_one({'user_id': user_id})
    jobs = list(mongo.db.jobs.find({'recruiter_id': user_id}))
    
    active_jobs = 0
    total_applications = 0
    total_shortlisted = 0
    total_hired = 0
    
    for job in jobs:
        if job.get('status', 'active') == 'active':
            active_jobs += 1
        
        applications = list(mongo.db.applications.find({'job_id': job['_id']}))
        total_applications += len(applications)
        
        shortlisted = len([a for a in applications if a.get('status') == 'shortlisted'])
        total_shortlisted += shortlisted
        
        hired = len([a for a in applications if a.get('status') == 'hired'])
        total_hired += hired
    
    stats = {
        'active_jobs': active_jobs,
        'total_jobs': len(jobs),
        'total_applications': total_applications,
        'shortlisted': total_shortlisted,
        'hired': total_hired
    }
    
    all_students = list(mongo.db.users.find({'role': 'student'}))
    top_candidates = []
    
    for student in all_students:
        profile = mongo.db.student_profiles.find_one({'user_id': student['_id']})
        if profile:
            overall_score = profile.get('overall_score', 0)
            top_candidates.append({
                'id': str(student['_id']),
                'name': student['name'],
                'email': student['email'],
                'overall_score': overall_score,
                'match_score': overall_score
            })
    
    top_candidates.sort(key=lambda x: x['overall_score'], reverse=True)
    top_candidates = top_candidates[:4]
    
    jobs = json_util(jobs)
    recruiter_profile = json_util(recruiter_profile) if recruiter_profile else {}
    
    return render_template('recruiter/dashboard.html', 
                         profile=recruiter_profile, 
                         jobs=jobs, 
                         stats=stats,
                         top_candidates=top_candidates)

@app.route('/recruiter/post_job', methods=['GET', 'POST'])
@login_required
@role_required('recruiter')
def post_job():
    if request.method == 'POST':
        skills_required = request.form.getlist('skills_required')
        skills_required = [skill for skill in skills_required if skill.strip()]
        
        job = {
            'recruiter_id': ObjectId(session['user_id']),
            'recruiter_name': session['user_name'],
            'title': request.form.get('title'),
            'company': request.form.get('company'),
            'description': request.form.get('description'),
            'requirements': request.form.get('requirements'),
            'skills_required': skills_required,
            'min_score': int(request.form.get('min_score', 0)),
            'experience_level': request.form.get('experience_level'),
            'location': request.form.get('location'),
            'salary_range': request.form.get('salary_range'),
            'job_type': request.form.get('job_type', 'Full-time'),
            'work_mode': request.form.get('work_mode', 'On-site'),
            'posted_date': datetime.datetime.now(),
            'applications_count': 0,
            'status': 'active'
        }
        
        result = mongo.db.jobs.insert_one(job)
        
        mongo.db.recruiter_profiles.update_one(
            {'user_id': ObjectId(session['user_id'])},
            {'$push': {'jobs_posted': result.inserted_id}}
        )
        
        flash('Job posted successfully!', 'success')
        return redirect(url_for('recruiter_dashboard'))
    
    return render_template('recruiter/post_job.html')

@app.route('/recruiter/company_profile', methods=['GET', 'POST'])
@login_required
@role_required('recruiter')
def recruiter_company_profile():
    user_id = ObjectId(session['user_id'])
    
    if request.method == 'POST':
        update_data = {
            'company_name': request.form.get('company_name'),
            'website': request.form.get('website'),
            'industry': request.form.get('industry'),
            'company_size': request.form.get('company_size'),
            'headquarters': request.form.get('headquarters'),
            'description': request.form.get('description'),
            'linkedin': request.form.get('linkedin'),
            'twitter': request.form.get('twitter'),
            'facebook': request.form.get('facebook'),
            'contact_email': request.form.get('contact_email'),
            'contact_phone': request.form.get('contact_phone')
        }
        
        if 'logo' in request.files:
            file = request.files['logo']
            if file and file.filename:
                update_data['logo_url'] = f"/uploads/{file.filename}"
        
        mongo.db.recruiter_profiles.update_one(
            {'user_id': user_id},
            {'$set': update_data},
            upsert=True
        )
        flash('Company profile updated successfully!', 'success')
        return redirect(url_for('recruiter_company_profile'))
    
    profile = mongo.db.recruiter_profiles.find_one({'user_id': user_id})
    profile = json_util(profile) if profile else {}
    return render_template('recruiter/company_profile.html', profile=profile)

@app.route('/recruiter/jobs')
@login_required
@role_required('recruiter')
def recruiter_jobs():
    jobs = list(mongo.db.jobs.find({'recruiter_id': ObjectId(session['user_id'])}))
    jobs = json_util(jobs)
    return render_template('recruiter/jobs.html', jobs=jobs)

@app.route('/recruiter/edit_job/<job_id>', methods=['GET', 'POST'])
@login_required
@role_required('recruiter')
def edit_job(job_id):
    job = mongo.db.jobs.find_one({'_id': ObjectId(job_id)})
    
    if request.method == 'POST':
        update_data = {
            'title': request.form.get('title'),
            'description': request.form.get('description'),
            'requirements': request.form.get('requirements'),
            'location': request.form.get('location'),
            'salary_range': request.form.get('salary_range'),
            'min_score': int(request.form.get('min_score')),
            'experience_level': request.form.get('experience_level')
        }
        
        mongo.db.jobs.update_one(
            {'_id': ObjectId(job_id)},
            {'$set': update_data}
        )
        flash('Job updated successfully!', 'success')
        return redirect(url_for('recruiter_jobs'))
    
    return render_template('recruiter/edit_job.html', job=job)

@app.route('/recruiter/close_job/<job_id>')
@login_required
@role_required('recruiter')
def close_job(job_id):
    mongo.db.jobs.update_one(
        {'_id': ObjectId(job_id), 'recruiter_id': ObjectId(session['user_id'])},
        {'$set': {'status': 'closed', 'closed_date': datetime.datetime.now()}}
    )
    flash('Job closed successfully!', 'success')
    return redirect(url_for('recruiter_jobs'))

@app.route('/recruiter/delete_job/<job_id>')
@login_required
@role_required('recruiter')
def delete_job(job_id):
    try:
        result = mongo.db.jobs.delete_one({'_id': ObjectId(job_id), 'recruiter_id': ObjectId(session['user_id'])})
        
        if result.deleted_count > 0:
            mongo.db.applications.delete_many({'job_id': ObjectId(job_id)})
            flash('Job deleted successfully!', 'success')
        else:
            flash('Job not found or you don\'t have permission to delete it.', 'error')
    except Exception as e:
        flash(f'Error deleting job: {str(e)}', 'error')
    
    return redirect(url_for('recruiter_jobs'))

@app.route('/recruiter/applications/<job_id>')
@login_required
@role_required('recruiter')
def view_applications(job_id):
    applications = list(mongo.db.applications.find({'job_id': ObjectId(job_id)}))
    
    for app in applications:
        student = mongo.db.users.find_one({'_id': app['student_id']})
        profile = mongo.db.student_profiles.find_one({'user_id': app['student_id']})
        app['student_name'] = student['name'] if student else 'Unknown'
        app['overall_score'] = profile.get('overall_score', 0) if profile else 0
        app['student_profile'] = profile
    
    applications = json_util(applications)
    job = mongo.db.jobs.find_one({'_id': ObjectId(job_id)})
    job = json_util(job)
    
    return render_template('recruiter/applications.html', applications=applications, job=job)

@app.route('/recruiter/update_application_status', methods=['POST'])
@login_required
@role_required('recruiter')
def update_application_status():
    application_id = request.form.get('application_id')
    status = request.form.get('status')
    
    mongo.db.applications.update_one(
        {'_id': ObjectId(application_id)},
        {'$set': {'status': status}}
    )
    
    feedback = request.form.get('feedback')
    if feedback:
        mongo.db.applications.update_one(
            {'_id': ObjectId(application_id)},
            {'$set': {'feedback': feedback, 'feedback_date': datetime.datetime.now()}}
        )
    
    flash('Application status updated!', 'success')
    return redirect(request.referrer)

@app.route('/recruiter/candidates')
@login_required
@role_required('recruiter')
def recruiter_candidates():
    min_score = int(request.args.get('min_score', 0))
    skills_filter = request.args.get('skills', '').split(',')
    location_filter = request.args.get('location', '')
    sort_by = request.args.get('sort_by', 'score')
    
    students = list(mongo.db.users.find({'role': 'student'}))
    candidates = []
    
    for student in students:
        profile = mongo.db.student_profiles.find_one({'user_id': student['_id']})
        if profile:
            overall_score = profile.get('overall_score', 0)
            
            if overall_score < min_score:
                continue
            
            if skills_filter and skills_filter[0]:
                student_skills = profile.get('skills', [])
                if not any(skill.strip().lower() in [s.lower() for s in student_skills] for skill in skills_filter if skill.strip()):
                    continue
            
            if location_filter and location_filter.lower() not in profile.get('location', '').lower():
                continue
            
            candidates.append({
                'id': str(student['_id']),
                'name': student['name'],
                'email': student['email'],
                'overall_score': overall_score,
                'skills': profile.get('skills', []),
                'location': profile.get('location', ''),
                'match_score': overall_score
            })
    
    if sort_by == 'score':
        candidates.sort(key=lambda x: x['match_score'], reverse=True)
    elif sort_by == 'name':
        candidates.sort(key=lambda x: x['name'])
    
    filters = {
        'min_score': min_score,
        'skills': request.args.get('skills', ''),
        'location': location_filter,
        'sort_by': sort_by
    }
    
    return render_template('recruiter/candidates.html', candidates=candidates, filters=filters)

@app.route('/recruiter/view_candidate/<candidate_id>')
@login_required
@role_required('recruiter')
def view_candidate(candidate_id):
    candidate = mongo.db.users.find_one({'_id': ObjectId(candidate_id)})
    profile = mongo.db.student_profiles.find_one({'user_id': ObjectId(candidate_id)})
    results = list(mongo.db.assessment_results.find({'user_id': ObjectId(candidate_id)}))
    
    return render_template('recruiter/view_candidate.html', candidate=candidate, profile=profile, results=results)

@app.route('/recruiter/shortlist_candidate/<candidate_id>')
@login_required
@role_required('recruiter')
def shortlist_candidate(candidate_id):
    mongo.db.applications.update_many(
        {'student_id': ObjectId(candidate_id)},
        {'$set': {'status': 'shortlisted'}}
    )
    flash('Candidate shortlisted successfully!', 'success')
    return redirect(request.referrer or url_for('recruiter_candidates'))

@app.route('/recruiter/interviews')
@login_required
@role_required('recruiter')
def recruiter_interviews():
    interviews = list(mongo.db.interviews.find({'recruiter_id': ObjectId(session['user_id'])}))
    
    recruiter_jobs = list(mongo.db.jobs.find({'recruiter_id': ObjectId(session['user_id'])}))
    job_ids = [job['_id'] for job in recruiter_jobs]
    
    applications = list(mongo.db.applications.find({'job_id': {'$in': job_ids}}))
    
    candidates = []
    for app in applications:
        student = mongo.db.users.find_one({'_id': app['student_id']})
        job = mongo.db.jobs.find_one({'_id': app['job_id']})
        profile = mongo.db.student_profiles.find_one({'user_id': app['student_id']})
        
        if student:
            candidates.append({
                'id': str(student['_id']),
                'name': student['name'],
                'email': student['email'],
                'job_title': job['title'] if job else 'Unknown',
                'score': profile.get('overall_score', 0) if profile else 0,
                'status': app.get('status', 'pending')
            })
    
    seen = set()
    unique_candidates = []
    for candidate in candidates:
        if candidate['id'] not in seen:
            seen.add(candidate['id'])
            unique_candidates.append(candidate)
    
    unique_candidates.sort(key=lambda x: x['score'], reverse=True)
    
    for interview in interviews:
        interview['_id'] = str(interview['_id'])
    
    current_date = datetime.datetime.now().strftime('%Y-%m-%d')
    
    return render_template('recruiter/interviews.html', 
                         interviews=interviews, 
                         candidates=unique_candidates,
                         current_date=current_date)

@app.route('/recruiter/schedule_interview', methods=['POST'])
@login_required
@role_required('recruiter')
def schedule_interview():
    candidate_id = request.form.get('candidate_id')
    candidate = mongo.db.users.find_one({'_id': ObjectId(candidate_id)})
    
    interview = {
        'recruiter_id': ObjectId(session['user_id']),
        'candidate_id': ObjectId(candidate_id),
        'candidate_name': candidate['name'] if candidate else 'Unknown',
        'job_title': request.form.get('job_title'),
        'interview_type': request.form.get('interview_type'),
        'date': request.form.get('date'),
        'time': request.form.get('time'),
        'interviewer': request.form.get('interviewer'),
        'meeting_link': request.form.get('meeting_link', ''),
        'notes': request.form.get('notes', ''),
        'status': 'scheduled',
        'created_date': datetime.datetime.now()
    }
    
    mongo.db.interviews.insert_one(interview)
    flash('Interview scheduled successfully!', 'success')
    return redirect(url_for('recruiter_interviews'))

@app.route('/recruiter/complete_interview/<interview_id>', methods=['POST'])
@login_required
@role_required('recruiter')
def complete_interview(interview_id):
    data = request.get_json() or {}
    rating = data.get('rating', 0)
    
    mongo.db.interviews.update_one(
        {'_id': ObjectId(interview_id)},
        {'$set': {
            'status': 'completed',
            'completed_date': datetime.datetime.now(),
            'rating': rating
        }}
    )
    
    interview = mongo.db.interviews.find_one({'_id': ObjectId(interview_id)})
    if interview:
        mongo.db.applications.update_one(
            {'student_id': interview['candidate_id']},
            {'$set': {'status': 'interview_completed'}}
        )
    
    return jsonify({'success': True})

@app.route('/recruiter/cancel_interview/<interview_id>', methods=['POST'])
@login_required
@role_required('recruiter')
def cancel_interview(interview_id):
    mongo.db.interviews.update_one(
        {'_id': ObjectId(interview_id)},
        {'$set': {'status': 'cancelled'}}
    )
    return jsonify({'success': True})

@app.route('/recruiter/get_interview/<interview_id>')
@login_required
@role_required('recruiter')
def get_interview(interview_id):
    interview = mongo.db.interviews.find_one({'_id': ObjectId(interview_id)})
    if interview:
        return jsonify({
            'feedback': interview.get('feedback', ''),
            'rating': interview.get('rating', 0),
            'notes': interview.get('notes', '')
        })
    return jsonify({'error': 'Interview not found'}), 404

@app.route('/recruiter/interview_feedback/<interview_id>', methods=['POST'])
@login_required
@role_required('recruiter')
def interview_feedback(interview_id):
    data = request.get_json()
    mongo.db.interviews.update_one(
        {'_id': ObjectId(interview_id)},
        {'$set': {
            'feedback': data.get('feedback'),
            'rating': data.get('rating', 0)
        }}
    )
    return jsonify({'success': True})

@app.route('/recruiter/messages')
@login_required
@role_required('recruiter')
def recruiter_messages():
    messages = list(mongo.db.messages.find({
        'recruiter_id': ObjectId(session['user_id'])
    }).sort('sent_date', -1))
    
    return render_template('recruiter/messages.html', messages=messages)

@app.route('/recruiter/send_message/<candidate_id>', methods=['GET', 'POST'])
@login_required
@role_required('recruiter')
def send_message(candidate_id):
    if request.method == 'POST':
        message = {
            'recruiter_id': ObjectId(session['user_id']),
            'candidate_id': ObjectId(candidate_id),
            'subject': request.form.get('subject'),
            'message': request.form.get('message'),
            'sent_date': datetime.datetime.now(),
            'status': 'sent'
        }
        mongo.db.messages.insert_one(message)
        flash('Message sent successfully!', 'success')
        return redirect(url_for('recruiter_messages'))
    
    candidate = mongo.db.users.find_one({'_id': ObjectId(candidate_id)})
    return render_template('recruiter/send_message.html', candidate=candidate)

@app.route('/recruiter/analytics')
@login_required
@role_required('recruiter')
def recruiter_analytics():
    jobs = list(mongo.db.jobs.find({'recruiter_id': ObjectId(session['user_id'])}))
    
    total_applications = 0
    total_shortlisted = 0
    total_hired = 0
    
    for job in jobs:
        applications = mongo.db.applications.count_documents({'job_id': job['_id']})
        total_applications += applications
        
        shortlisted = mongo.db.applications.count_documents({
            'job_id': job['_id'],
            'status': 'shortlisted'
        })
        total_shortlisted += shortlisted
        
        hired = mongo.db.applications.count_documents({
            'job_id': job['_id'],
            'status': 'hired'
        })
        total_hired += hired
    
    stats = {
        'active_jobs': len([j for j in jobs if j.get('status') != 'closed']),
        'total_jobs': len(jobs),
        'total_applications': total_applications,
        'total_shortlisted': total_shortlisted,
        'total_hired': total_hired,
        'hiring_rate': (total_hired / total_applications * 100) if total_applications > 0 else 0
    }
    
    return render_template('recruiter/analytics.html', stats=stats, jobs=jobs)

# ============ ADMIN ROUTES ============

@app.route('/admin/dashboard')
@login_required
@role_required('admin')
def admin_dashboard():
    # Get statistics
    total_students = mongo.db.users.count_documents({'role': 'student'})
    total_recruiters = mongo.db.users.count_documents({'role': 'recruiter'})
    total_jobs = mongo.db.jobs.count_documents({})
    total_applications = mongo.db.applications.count_documents({})
    total_assessments = mongo.db.assessment_results.count_documents({})
    total_questions = mongo.db.questions.count_documents({})
    
    # Get today's new users
    today_start = datetime.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    new_users_today = mongo.db.users.count_documents({'created_at': {'$gte': today_start}})
    
    # Get assessments taken today
    assessments_today = mongo.db.assessment_results.count_documents({'date_taken': {'$gte': today_start}})
    
    # Get fraud alerts count
    fraud_alerts_count = mongo.db.fraud_alerts.count_documents({'status': 'active'})
    
    # Get active sessions (simplified - in production you'd track this)
    active_sessions = 42  # Placeholder
    active_sessions_percent = (active_sessions / 100) * 100 if active_sessions < 100 else 100
    
    # Get recent users
    recent_users = list(mongo.db.users.find().sort('created_at', -1).limit(5))
    recent_users = json_util(recent_users)
    
    # Get fraud alerts for display
    fraud_alerts = list(mongo.db.fraud_alerts.find({'status': 'active'}).sort('date', -1).limit(5))
    for alert in fraud_alerts:
        student = mongo.db.users.find_one({'_id': alert['student_id']})
        alert['student_name'] = student['name'] if student else 'Unknown'
        alert['email'] = student['email'] if student else 'Unknown'
        alert['_id'] = str(alert['_id'])
    
    # Get recent activities (simplified - you can expand this)
    activities = []
    recent_activities = list(mongo.db.assessment_results.find().sort('date_taken', -1).limit(5))
    for activity in recent_activities:
        student = mongo.db.users.find_one({'_id': activity['user_id']})
        if student:
            activities.append({
                'user': student['name'],
                'action': 'Completed Assessment',
                'details': f"Scored {activity['score_percentage']:.1f}% on {activity['assessment_title']}",
                'time': activity['date_taken'],
                'icon': 'check-circle'
            })
    
    # Add user registration activities
    recent_registrations = list(mongo.db.users.find().sort('created_at', -1).limit(3))
    for reg in recent_registrations:
        activities.append({
            'user': reg['name'],
            'action': 'Registered',
            'details': f"Joined as {reg['role']}",
            'time': reg['created_at'],
            'icon': 'person-plus'
        })
    
    # Sort activities by time (newest first)
    activities.sort(key=lambda x: x['time'], reverse=True)
    activities = activities[:10]  # Limit to 10 activities
    
    # Get monthly growth data (last 6 months)
    growth_data = []
    for i in range(5, -1, -1):
        month_date = datetime.datetime.now() - datetime.timedelta(days=30*i)
        month_start = month_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        # Calculate month end
        if month_date.month == 12:
            month_end = month_date.replace(year=month_date.year + 1, month=1, day=1)
        else:
            month_end = month_date.replace(month=month_date.month + 1, day=1)
        
        month_users = mongo.db.users.count_documents({
            'created_at': {'$gte': month_start, '$lt': month_end}
        })
        growth_data.append({
            'month': month_date.strftime('%B'),
            'users': month_users
        })
    
    # Calculate student growth percentage (compare last 30 days vs previous 30 days)
    thirty_days_ago = datetime.datetime.now() - datetime.timedelta(days=30)
    sixty_days_ago = datetime.datetime.now() - datetime.timedelta(days=60)
    
    recent_students = mongo.db.users.count_documents({
        'role': 'student',
        'created_at': {'$gte': thirty_days_ago}
    })
    previous_students = mongo.db.users.count_documents({
        'role': 'student',
        'created_at': {'$gte': sixty_days_ago, '$lt': thirty_days_ago}
    })
    
    student_growth = 0
    if previous_students > 0:
        student_growth = ((recent_students - previous_students) / previous_students) * 100
    
    stats = {
        'total_users': total_students + total_recruiters + 1,  # +1 for admin
        'total_students': total_students,
        'total_recruiters': total_recruiters,
        'total_jobs': total_jobs,
        'total_applications': total_applications,
        'total_assessments': total_assessments,
        'total_questions': total_questions,
        'new_users_today': new_users_today,
        'assessments_today': assessments_today,
        'fraud_alerts': fraud_alerts_count,
        'new_alerts': fraud_alerts_count,
        'student_growth': round(student_growth, 1),
        'storage_usage': 45,  # Placeholder percentage
        'active_sessions': active_sessions,
        'active_sessions_percent': active_sessions_percent
    }
    
    return render_template('admin/dashboard.html', 
                         stats=stats, 
                         recent_users=recent_users,
                         fraud_alerts=fraud_alerts,
                         activities=activities,
                         growth_data=growth_data)

@app.route('/admin/users')
@login_required
@role_required('admin')
def admin_users():
    users = list(mongo.db.users.find())
    users = json_util(users)
    return render_template('admin/users.html', users=users)

@app.route('/admin/delete_user/<user_id>', methods=['DELETE'])
@login_required
@role_required('admin')
def admin_delete_user(user_id):
    try:
        mongo.db.users.delete_one({'_id': ObjectId(user_id)})
        mongo.db.student_profiles.delete_one({'user_id': ObjectId(user_id)})
        mongo.db.recruiter_profiles.delete_one({'user_id': ObjectId(user_id)})
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/admin/assessments', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def admin_assessments():
    if request.method == 'POST':
        questions = []
        num_questions = int(request.form.get('num_questions', 0))
        
        for i in range(num_questions):
            options_text = request.form.get(f'options_{i}', '')
            options = [opt.strip() for opt in options_text.split('\n') if opt.strip()]
            
            if not options and ',' in options_text:
                options = [opt.strip() for opt in options_text.split(',') if opt.strip()]
            
            question = {
                'question': request.form.get(f'question_{i}'),
                'options': options,
                'correct_answer': request.form.get(f'correct_answer_{i}')
            }
            questions.append(question)
        
        assessment = {
            'title': request.form.get('title'),
            'category': request.form.get('category'),
            'description': request.form.get('description'),
            'duration': int(request.form.get('duration', 30)),
            'questions': questions,
            'created_date': datetime.datetime.now()
        }
        
        mongo.db.assessments.insert_one(assessment)
        flash('Assessment created successfully!', 'success')
        return redirect(url_for('admin_assessments'))
    
    assessments = list(mongo.db.assessments.find())
    assessments = json_util(assessments)
    return render_template('admin/assessments.html', assessments=assessments)

@app.route('/admin/delete_assessment/<assessment_id>', methods=['DELETE'])
@login_required
@role_required('admin')
def admin_delete_assessment(assessment_id):
    try:
        mongo.db.assessments.delete_one({'_id': ObjectId(assessment_id)})
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/admin/analytics')
@login_required
@role_required('admin')
def admin_analytics():
    # Get skill trends from assessment results
    pipeline = [
        {'$group': {
            '_id': '$category',
            'avg_score': {'$avg': '$score_percentage'}
        }}
    ]
    skill_trends = list(mongo.db.assessment_results.aggregate(pipeline))
    
    # If no data, provide sample data for visualization
    if not skill_trends:
        skill_trends = [
            {'_id': 'Python', 'avg_score': 75},
            {'_id': 'Java', 'avg_score': 68},
            {'_id': 'JavaScript', 'avg_score': 72},
            {'_id': 'SQL', 'avg_score': 65},
            {'_id': 'Data Structures', 'avg_score': 70},
            {'_id': 'Algorithms', 'avg_score': 62}
        ]
    
    # Get hiring success rates
    pipeline = [
        {'$group': {
            '_id': '$status',
            'count': {'$sum': 1}
        }}
    ]
    hiring_stats = list(mongo.db.applications.aggregate(pipeline))
    
    # If no data, provide sample data
    if not hiring_stats:
        hiring_stats = [
            {'_id': 'pending', 'count': 45},
            {'_id': 'shortlisted', 'count': 28},
            {'_id': 'hired', 'count': 12},
            {'_id': 'rejected', 'count': 35}
        ]
    
    # Get total counts for stats
    total_users = mongo.db.users.count_documents({})
    total_students = mongo.db.users.count_documents({'role': 'student'})
    total_recruiters = mongo.db.users.count_documents({'role': 'recruiter'})
    total_assessments = mongo.db.assessment_results.count_documents({})
    total_jobs = mongo.db.jobs.count_documents({})
    
    # Calculate hiring rate
    total_hired = sum([stat['count'] for stat in hiring_stats if stat['_id'] == 'hired'])
    total_applications = sum([stat['count'] for stat in hiring_stats])
    hiring_rate = (total_hired / total_applications * 100) if total_applications > 0 else 0
    
    # Calculate growth percentages (compare last 30 days with previous 30 days)
    thirty_days_ago = datetime.datetime.now() - datetime.timedelta(days=30)
    sixty_days_ago = datetime.datetime.now() - datetime.timedelta(days=60)
    
    recent_users = mongo.db.users.count_documents({'created_at': {'$gte': thirty_days_ago}})
    previous_users = mongo.db.users.count_documents({
        'created_at': {'$gte': sixty_days_ago, '$lt': thirty_days_ago}
    })
    user_growth = ((recent_users - previous_users) / previous_users * 100) if previous_users > 0 else 12
    
    recent_assessments = mongo.db.assessment_results.count_documents({'date_taken': {'$gte': thirty_days_ago}})
    previous_assessments = mongo.db.assessment_results.count_documents({
        'date_taken': {'$gte': sixty_days_ago, '$lt': thirty_days_ago}
    })
    assessment_growth = ((recent_assessments - previous_assessments) / previous_assessments * 100) if previous_assessments > 0 else 8
    
    recent_jobs = mongo.db.jobs.count_documents({'posted_date': {'$gte': thirty_days_ago}})
    previous_jobs = mongo.db.jobs.count_documents({
        'posted_date': {'$gte': sixty_days_ago, '$lt': thirty_days_ago}
    })
    job_growth = ((recent_jobs - previous_jobs) / previous_jobs * 100) if previous_jobs > 0 else 15
    
    hiring_growth = 5  # Placeholder
    
    # Get monthly growth data for chart
    growth_data = []
    for i in range(5, -1, -1):
        month_date = datetime.datetime.now() - datetime.timedelta(days=30*i)
        month_start = month_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if month_date.month == 12:
            month_end = month_date.replace(year=month_date.year + 1, month=1, day=1)
        else:
            month_end = month_date.replace(month=month_date.month + 1, day=1)
        
        month_users = mongo.db.users.count_documents({
            'created_at': {'$gte': month_start, '$lt': month_end}
        })
        growth_data.append({
            'month': month_date.strftime('%B'),
            'users': month_users
        })
    
    stats = {
        'total_users': total_users,
        'total_students': total_students,
        'total_recruiters': total_recruiters,
        'total_assessments': total_assessments,
        'total_jobs': total_jobs,
        'hiring_rate': round(hiring_rate, 1),
        'user_growth': round(user_growth, 1),
        'assessment_growth': round(assessment_growth, 1),
        'job_growth': round(job_growth, 1),
        'hiring_growth': hiring_growth,
        'overall_success': 68  # Placeholder percentage
    }
    
    return render_template('admin/analytics.html', 
                         skill_trends=skill_trends, 
                         hiring_stats=hiring_stats,
                         stats=stats,
                         growth_data=growth_data)

# Question Bank Management
@app.route('/admin/question_bank')
@login_required
@role_required('admin')
def admin_question_bank():
    page = int(request.args.get('page', 1))
    per_page = 20
    search = request.args.get('search', '')
    category = request.args.get('category', '')
    difficulty = request.args.get('difficulty', '')
    
    query = {}
    if search:
        query['question'] = {'$regex': search, '$options': 'i'}
    if category:
        query['category'] = category
    if difficulty:
        query['difficulty'] = difficulty
    
    total_questions = mongo.db.questions.count_documents(query)
    total_pages = (total_questions + per_page - 1) // per_page if total_questions > 0 else 1
    
    questions = list(mongo.db.questions.find(query).skip((page - 1) * per_page).limit(per_page))
    questions = json_util(questions)
    
    return render_template('admin/question_bank.html',
                         questions=questions,
                         total_questions=total_questions,
                         total_pages=total_pages,
                         page=page,
                         search=search,
                         category=category,
                         difficulty=difficulty)

@app.route('/admin/add_question', methods=['POST'])
@login_required
@role_required('admin')
def admin_add_question():
    options_text = request.form.get('options', '')
    options = [opt.strip() for opt in options_text.split('\n') if opt.strip()]
    
    question = {
        'question': request.form.get('question'),
        'category': request.form.get('category'),
        'difficulty': request.form.get('difficulty'),
        'options': options,
        'correct_answer': request.form.get('correct_answer'),
        'explanation': request.form.get('explanation', ''),
        'usage_count': 0,
        'created_date': datetime.datetime.now()
    }
    
    mongo.db.questions.insert_one(question)
    flash('Question added successfully!', 'success')
    return redirect(url_for('admin_question_bank'))

@app.route('/admin/edit_question/<question_id>', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def admin_edit_question(question_id):
    question = mongo.db.questions.find_one({'_id': ObjectId(question_id)})
    
    if request.method == 'POST':
        options_text = request.form.get('options', '')
        options = [opt.strip() for opt in options_text.split('\n') if opt.strip()]
        
        update_data = {
            'question': request.form.get('question'),
            'category': request.form.get('category'),
            'difficulty': request.form.get('difficulty'),
            'options': options,
            'correct_answer': request.form.get('correct_answer'),
            'explanation': request.form.get('explanation', ''),
            'updated_date': datetime.datetime.now()
        }
        
        mongo.db.questions.update_one({'_id': ObjectId(question_id)}, {'$set': update_data})
        flash('Question updated successfully!', 'success')
        return redirect(url_for('admin_question_bank'))
    
    return render_template('admin/edit_question.html', question=question)

@app.route('/admin/delete_question/<question_id>', methods=['DELETE'])
@login_required
@role_required('admin')
def admin_delete_question(question_id):
    try:
        mongo.db.questions.delete_one({'_id': ObjectId(question_id)})
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

# Assessment Rules
@app.route('/admin/assessment_rules')
@login_required
@role_required('admin')
def admin_assessment_rules():
    rules = mongo.db.assessment_rules.find_one({}) or {}
    return render_template('admin/assessment_rules.html', rules=rules)

@app.route('/admin/update_time_rules', methods=['POST'])
@login_required
@role_required('admin')
def admin_update_time_rules():
    mongo.db.assessment_rules.update_one(
        {},
        {'$set': {
            'default_duration': int(request.form.get('default_duration', 30)),
            'max_duration': int(request.form.get('max_duration', 120)),
            'enable_timer_warning': 'enable_timer_warning' in request.form
        }},
        upsert=True
    )
    flash('Time rules updated!', 'success')
    return redirect(url_for('admin_assessment_rules'))

@app.route('/admin/update_attempt_rules', methods=['POST'])
@login_required
@role_required('admin')
def admin_update_attempt_rules():
    mongo.db.assessment_rules.update_one(
        {},
        {'$set': {
            'max_attempts': int(request.form.get('max_attempts', 3)),
            'cooldown_days': int(request.form.get('cooldown_days', 7))
        }},
        upsert=True
    )
    flash('Attempt rules updated!', 'success')
    return redirect(url_for('admin_assessment_rules'))

@app.route('/admin/update_scoring_rules', methods=['POST'])
@login_required
@role_required('admin')
def admin_update_scoring_rules():
    mongo.db.assessment_rules.update_one(
        {},
        {'$set': {
            'points_correct': float(request.form.get('points_correct', 1)),
            'negative_marking': float(request.form.get('negative_marking', 0)),
            'enable_partial_scoring': 'enable_partial_scoring' in request.form
        }},
        upsert=True
    )
    flash('Scoring rules updated!', 'success')
    return redirect(url_for('admin_assessment_rules'))

@app.route('/admin/update_passing_rules', methods=['POST'])
@login_required
@role_required('admin')
def admin_update_passing_rules():
    mongo.db.assessment_rules.update_one(
        {},
        {'$set': {
            'passing_percentage': int(request.form.get('passing_percentage', 50)),
            'min_questions': int(request.form.get('min_questions', 0)),
            'require_all_questions': 'require_all_questions' in request.form
        }},
        upsert=True
    )
    flash('Passing rules updated!', 'success')
    return redirect(url_for('admin_assessment_rules'))

# Fraud Detection
@app.route('/admin/fraud_detection')
@login_required
@role_required('admin')
def admin_fraud_detection():
    alerts = list(mongo.db.fraud_alerts.find({'status': 'active'}).sort('date', -1))
    
    stats = {
        'high_risk': mongo.db.fraud_alerts.count_documents({'severity': 'high', 'status': 'active'}),
        'medium_risk': mongo.db.fraud_alerts.count_documents({'severity': 'medium', 'status': 'active'}),
        'low_risk': mongo.db.fraud_alerts.count_documents({'severity': 'low', 'status': 'active'}),
        'resolved': mongo.db.fraud_alerts.count_documents({'status': 'resolved'})
    }
    
    fraud_trends = []
    for i in range(30, -1, -1):
        date = datetime.datetime.now() - datetime.timedelta(days=i)
        count = mongo.db.fraud_alerts.count_documents({
            'date': {'$gte': date.replace(hour=0, minute=0, second=0, microsecond=0),
                    '$lt': date.replace(hour=23, minute=59, second=59, microsecond=999999)}
        })
        fraud_trends.append({
            'date': date.strftime('%Y-%m-%d'),
            'count': count
        })
    
    for alert in alerts:
        student = mongo.db.users.find_one({'_id': alert['student_id']})
        alert['student_name'] = student['name'] if student else 'Unknown'
        alert['email'] = student['email'] if student else 'Unknown'
        alert['_id'] = str(alert['_id'])
    
    return render_template('admin/fraud_detection.html',
                         alerts=alerts,
                         stats=stats,
                         fraud_trends=fraud_trends)

@app.route('/admin/fraud_alert_details/<alert_id>')
@login_required
@role_required('admin')
def admin_fraud_alert_details(alert_id):
    alert = mongo.db.fraud_alerts.find_one({'_id': ObjectId(alert_id)})
    if alert:
        student = mongo.db.users.find_one({'_id': alert['student_id']})
        return jsonify({
            'student_name': student['name'] if student else 'Unknown',
            'assessment_title': alert.get('assessment_title', 'Unknown'),
            'alert_type': alert.get('alert_type', 'Unknown'),
            'severity': alert.get('severity', 'low'),
            'details': alert.get('details', ''),
            'recommendation': alert.get('recommendation', 'Review assessment and take appropriate action.')
        })
    return jsonify({'error': 'Alert not found'}), 404

@app.route('/admin/resolve_fraud_alert/<alert_id>', methods=['POST'])
@login_required
@role_required('admin')
def admin_resolve_fraud_alert(alert_id):
    try:
        mongo.db.fraud_alerts.update_one(
            {'_id': ObjectId(alert_id)},
            {'$set': {'status': 'resolved', 'resolved_date': datetime.datetime.now()}}
        )
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/admin/resolve_all_alerts', methods=['POST'])
@login_required
@role_required('admin')
def admin_resolve_all_alerts():
    try:
        mongo.db.fraud_alerts.update_many(
            {'status': 'active'},
            {'$set': {'status': 'resolved', 'resolved_date': datetime.datetime.now()}}
        )
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/admin/save_detection_rules', methods=['POST'])
@login_required
@role_required('admin')
def admin_save_detection_rules():
    data = request.get_json()
    mongo.db.detection_rules.update_one({}, {'$set': data}, upsert=True)
    return jsonify({'success': True})

# Scoring Algorithms
@app.route('/admin/scoring_algorithms')
@login_required
@role_required('admin')
def admin_scoring_algorithms():
    config = mongo.db.scoring_config.find_one({}) or {}
    
    all_scores = list(mongo.db.student_profiles.find({}, {'overall_score': 1}))
    scores = [s.get('overall_score', 0) for s in all_scores]
    
    distribution = [0, 0, 0, 0, 0]
    for score in scores:
        if score < 20:
            distribution[0] += 1
        elif score < 40:
            distribution[1] += 1
        elif score < 60:
            distribution[2] += 1
        elif score < 80:
            distribution[3] += 1
        else:
            distribution[4] += 1
    
    stats = {
        'mean_score': sum(scores) / len(scores) if scores else 0,
        'median_score': sorted(scores)[len(scores)//2] if scores else 0,
        'std_dev': (sum((x - (sum(scores)/len(scores)))**2 for x in scores) / len(scores))**0.5 if scores else 0,
        'top_10_percent': sorted(scores)[int(len(scores)*0.9)] if scores else 0
    }
    
    return render_template('admin/scoring_algorithms.html',
                         config=config,
                         score_distribution=distribution,
                         stats=stats)

@app.route('/admin/update_scoring_algorithm', methods=['POST'])
@login_required
@role_required('admin')
def admin_update_scoring_algorithm():
    update_data = {
        'algorithm_type': request.form.get('algorithm_type', 'simple_average'),
        'recent_weight': int(request.form.get('recent_weight', 70)),
        'older_weight': int(request.form.get('older_weight', 30)),
        'decay_factor': float(request.form.get('decay_factor', 0.5)),
        'easy_multiplier': float(request.form.get('easy_multiplier', 1.0)),
        'medium_multiplier': float(request.form.get('medium_multiplier', 1.5)),
        'hard_multiplier': float(request.form.get('hard_multiplier', 2.0))
    }
    
    mongo.db.scoring_config.update_one({}, {'$set': update_data}, upsert=True)
    flash('Scoring algorithm updated!', 'success')
    return redirect(url_for('admin_scoring_algorithms'))

@app.route('/admin/update_normalization', methods=['POST'])
@login_required
@role_required('admin')
def admin_update_normalization():
    update_data = {
        'enable_normalization': 'enable_normalization' in request.form,
        'min_cap': int(request.form.get('min_cap', 0)),
        'max_cap': int(request.form.get('max_cap', 100))
    }
    
    mongo.db.scoring_config.update_one({}, {'$set': update_data}, upsert=True)
    flash('Normalization settings updated!', 'success')
    return redirect(url_for('admin_scoring_algorithms'))

# Recommendation Engine
@app.route('/admin/recommendation_engine')
@login_required
@role_required('admin')
def admin_recommendation_engine():
    factors = mongo.db.recommendation_factors.find_one({}) or {}
    config = mongo.db.recommendation_config.find_one({}) or {}
    
    recent_feedback = list(mongo.db.feedback.find().sort('date', -1).limit(10))
    for fb in recent_feedback:
        fb['_id'] = str(fb['_id'])
        fb['student_name'] = fb.get('student_name', 'Unknown')
    
    total_recommendations = mongo.db.recommendations.count_documents({}) if hasattr(mongo.db, 'recommendations') else 0
    total_clicks = mongo.db.recommendations.count_documents({'clicked': True}) if hasattr(mongo.db, 'recommendations') else 0
    total_applications = mongo.db.recommendations.count_documents({'applied': True}) if hasattr(mongo.db, 'recommendations') else 0
    total_shortlisted = mongo.db.applications.count_documents({'status': 'shortlisted'})
    total_hired = mongo.db.applications.count_documents({'status': 'hired'})
    
    analytics = {
        'ctr': (total_clicks / total_recommendations * 100) if total_recommendations else 0,
        'application_rate': (total_applications / total_recommendations * 100) if total_recommendations else 0,
        'hiring_success': (total_hired / total_shortlisted * 100) if total_shortlisted else 0,
        'model_accuracy': 85
    }
    
    return render_template('admin/recommendation_engine.html',
                         factors=factors,
                         config=config,
                         analytics=analytics,
                         recent_feedback=recent_feedback)

@app.route('/admin/update_recommendation_factors', methods=['POST'])
@login_required
@role_required('admin')
def admin_update_recommendation_factors():
    factors = {
        'skill_weight': int(request.form.get('skill_weight', 50)),
        'profile_weight': int(request.form.get('profile_weight', 20)),
        'history_weight': int(request.form.get('history_weight', 20)),
        'feedback_weight': int(request.form.get('feedback_weight', 10))
    }
    
    mongo.db.recommendation_factors.update_one({}, {'$set': factors}, upsert=True)
    flash('Recommendation factors updated!', 'success')
    return redirect(url_for('admin_recommendation_engine'))

@app.route('/admin/update_feedback_integration', methods=['POST'])
@login_required
@role_required('admin')
def admin_update_feedback_integration():
    config = {
        'use_application_feedback': 'use_application_feedback' in request.form,
        'use_interview_feedback': 'use_interview_feedback' in request.form,
        'feedback_impact': float(request.form.get('feedback_impact', 1.0)),
        'min_feedback_samples': int(request.form.get('min_feedback_samples', 5))
    }
    
    mongo.db.recommendation_config.update_one({}, {'$set': config}, upsert=True)
    flash('Feedback integration updated!', 'success')
    return redirect(url_for('admin_recommendation_engine'))

@app.route('/admin/retrain_recommendation_model', methods=['POST'])
@login_required
@role_required('admin')
def admin_retrain_model():
    data = request.get_json()
    range_type = data.get('range', 'all')
    flash('Model retraining started. This may take a few minutes.', 'info')
    return jsonify({'success': True})

@app.route('/admin/recommendation_details')
@login_required
@role_required('admin')
def admin_recommendation_details():
    recommendations = list(mongo.db.recommendations.find().sort('date', -1).limit(100)) if hasattr(mongo.db, 'recommendations') else []
    
    job_performance = []
    jobs = list(mongo.db.jobs.find())
    for job in jobs:
        job_recommendations = mongo.db.recommendations.count_documents({'job_id': job['_id']}) if hasattr(mongo.db, 'recommendations') else 0
        job_applications = mongo.db.applications.count_documents({'job_id': job['_id']})
        job_performance.append({
            'title': job['title'],
            'recommendations': job_recommendations,
            'applications': job_applications,
            'conversion_rate': (job_applications / job_recommendations * 100) if job_recommendations else 0
        })
    
    return render_template('admin/recommendation_details.html',
                         recommendations=recommendations,
                         job_performance=job_performance)

@app.route('/admin/model_performance')
@login_required
@role_required('admin')
def admin_model_performance():
    metrics = {
        'precision': 0.85,
        'recall': 0.78,
        'f1_score': 0.81,
        'auc': 0.88,
        'last_training_date': datetime.datetime.now() - datetime.timedelta(days=7),
        'training_samples': 1250
    }
    
    return render_template('admin/model_performance.html', metrics=metrics)

# Create default admin user if not exists
def create_default_admin():
    try:
        admin_exists = mongo.db.users.find_one({'email': 'admin@gmail.com'})
        if not admin_exists:
            admin_user = {
                'name': 'Administrator',
                'email': 'admin@gmail.com',
                'password': generate_password_hash('admin123'),
                'role': 'admin',
                'created_at': datetime.datetime.now()
            }
            mongo.db.users.insert_one(admin_user)
            print("=" * 50)
            print("Default admin user created successfully!")
            print("Email: admin@gmail.com")
            print("Password: admin123")
            print("=" * 50)
        else:
            print("Admin user already exists: admin@gmail.com")
    except Exception as e:
        print(f"Error creating admin user: {e}")

# Create sample assessment if none exists
def create_sample_assessment():
    try:
        assessment_count = mongo.db.assessments.count_documents({})
        if assessment_count == 0:
            sample_assessment = {
                'title': 'Python Programming Basics',
                'category': 'Python',
                'description': 'Test your knowledge of Python programming fundamentals',
                'duration': 30,
                'questions': [
                    {
                        'question': 'What is the correct way to create a function in Python?',
                        'options': ['function myFunc():', 'def myFunc():', 'create myFunc():', 'new myFunc():'],
                        'correct_answer': 'def myFunc():'
                    },
                    {
                        'question': 'Which of the following is a Python data type?',
                        'options': ['list', 'array', 'vector', 'map'],
                        'correct_answer': 'list'
                    },
                    {
                        'question': 'What is the output of print(2**3)?',
                        'options': ['6', '8', '9', '5'],
                        'correct_answer': '8'
                    }
                ],
                'created_date': datetime.datetime.now()
            }
            mongo.db.assessments.insert_one(sample_assessment)
            print("Sample assessment created successfully!")
    except Exception as e:
        print(f"Error creating sample assessment: {e}")

# Add this import at the top
from jobspy import scrape_jobs
import pandas as pd

# Function to fetch real jobs from job boards
def fetch_real_jobs(skills, role, location="Remote", results_wanted=20):
    """
    Fetch real job listings from LinkedIn, Indeed, Glassdoor, and Google Jobs
    """
    try:
        # Create search term from user's skills and role
        if skills:
            search_term = f"{role} {' '.join(skills[:3])}"
        else:
            search_term = role if role else "software developer"
        
        print(f"Searching for: {search_term} in {location}")
        
        # Scrape jobs from multiple platforms
        jobs = scrape_jobs(
            site_name=["linkedin", "indeed", "glassdoor", "google"],
            search_term=search_term,
            location=location,
            results_wanted=results_wanted,
            hours_old=168,  # Last 7 days
            country_indeed='USA',
            linkedin_fetch_description=True,  # Get full descriptions
            verbose=2
        )
        
        # Convert to list of dictionaries
        if isinstance(jobs, pd.DataFrame):
            job_list = jobs.to_dict('records')
        else:
            job_list = jobs
        
        print(f"Found {len(job_list)} jobs")
        return job_list
        
    except Exception as e:
        print(f"Error fetching jobs: {e}")
        # Return fallback jobs if API fails
        return get_fallback_jobs(skills, role, location)

# Fallback jobs in case API fails
def get_fallback_jobs(skills, role, location):
    """Return fallback job recommendations"""
    fallback_jobs = [
        {
            'title': f"{role} Developer",
            'company': "Tech Innovations Inc.",
            'location': location or "Remote",
            'salary': "$80,000 - $120,000",
            'description': f"We are looking for a skilled {role} developer with experience in {', '.join(skills[:3]) if skills else 'relevant technologies'}.",
            'job_url': "https://www.linkedin.com/jobs/view/example1",
            'site': "LinkedIn",
            'job_type': "Full-time",
            'date_posted': "2024-01-15"
        },
        {
            'title': f"Senior {role} Engineer",
            'company': "Digital Solutions Corp",
            'location': location or "New York, NY",
            'salary': "$100,000 - $150,000",
            'description': f"Join our team as a Senior {role} Engineer. Required skills: {', '.join(skills[:3]) if skills else 'Python, SQL, JavaScript'}.",
            'job_url': "https://www.indeed.com/viewjob/example2",
            'site': "Indeed",
            'job_type': "Full-time",
            'date_posted': "2024-01-14"
        },
        {
            'title': f"Junior {role} - Entry Level",
            'company': "StartUp Hub",
            'location': location or "San Francisco, CA",
            'salary': "$70,000 - $90,000",
            'description': f"Great opportunity for recent graduates. Looking for {', '.join(skills[:2]) if skills else 'passionate learners'}.",
            'job_url': "https://www.glassdoor.com/job-listing/example3",
            'site': "Glassdoor",
            'job_type': "Full-time",
            'date_posted': "2024-01-13"
        }
    ]
    
    # Generate more fallback jobs based on skills
    for skill in skills[:2] if skills else ['Python', 'JavaScript']:
        fallback_jobs.append({
            'title': f"{skill} Specialist",
            'company': f"{skill} Technologies",
            'location': location or "Remote",
            'salary': "$85,000 - $110,000",
            'description': f"Seeking {skill} expert for exciting projects. Must have strong {skill} skills.",
            'job_url': f"https://www.ziprecruiter.com/jobs/{skill.lower()}-specialist",
            'site': "ZipRecruiter",
            'job_type': "Full-time",
            'date_posted': "2024-01-12"
        })
    
    return fallback_jobs[:10]

# Update the student_jobs route to fetch real jobs
@app.route('/student/jobs')
@login_required
@role_required('student')
def student_jobs():
    user_id = ObjectId(session['user_id'])
    profile = mongo.db.student_profiles.find_one({'user_id': user_id})
    
    # Get user's skills and role
    onboarding_data = profile.get('onboarding_data', {})
    skills = onboarding_data.get('skills', [])
    role_specific = onboarding_data.get('role_specific', 'Software Developer')
    location = profile.get('location', 'Remote')
    
    # Get filters from request
    search_term = request.args.get('search', '')
    job_type = request.args.get('job_type', '')
    remote_only = request.args.get('remote_only', 'false') == 'true'
    page = int(request.args.get('page', 1))
    per_page = 10
    
    # Fetch real jobs
    try:
        jobs = fetch_real_jobs(
            skills=skills,
            role=role_specific if not search_term else search_term,
            location=location,
            results_wanted=50
        )
        
        # Apply filters
        if job_type:
            jobs = [j for j in jobs if j.get('job_type', '').lower() == job_type.lower()]
        
        if remote_only:
            jobs = [j for j in jobs if 'remote' in j.get('location', '').lower() or 'remote' in j.get('description', '').lower()]
        
        # Pagination
        total_jobs = len(jobs)
        start = (page - 1) * per_page
        end = start + per_page
        paginated_jobs = jobs[start:end]
        
        # Calculate match scores based on user's skills
        for job in paginated_jobs:
            match_score = calculate_match_score(job, skills, profile.get('overall_score', 0))
            job['match_score'] = match_score
        
        # Sort by match score
        paginated_jobs.sort(key=lambda x: x.get('match_score', 0), reverse=True)
        
    except Exception as e:
        print(f"Error in student_jobs: {e}")
        paginated_jobs = []
        total_jobs = 0
    
    return render_template('student/jobs.html', 
                         jobs=paginated_jobs,
                         total_jobs=total_jobs,
                         page=page,
                         per_page=per_page,
                         total_pages=(total_jobs + per_page - 1) // per_page if total_jobs > 0 else 1,
                         search_term=search_term,
                         job_type=job_type,
                         remote_only=remote_only)

def calculate_match_score(job, user_skills, overall_score):
    """Calculate how well a job matches the user's profile"""
    score = 0
    
    # Title match (30% weight)
    job_title = job.get('title', '').lower()
    for skill in user_skills[:3]:
        if skill.lower() in job_title:
            score += 10
    
    # Description match (40% weight)
    description = job.get('description', '').lower()
    skill_matches = 0
    for skill in user_skills:
        if skill.lower() in description:
            skill_matches += 1
    score += (skill_matches / max(len(user_skills), 1)) * 40
    
    # Overall score match (30% weight)
    score += (overall_score / 100) * 30
    
    return min(100, int(score))

# Call the functions to create default data
with app.app_context():
    create_default_admin()
    create_sample_assessment()


###

# Add these routes to your app.py

# ============ FEEDBACK ROUTES (Add these) ============

@app.route('/recruiter/feedback')
@login_required
@role_required('recruiter')
def recruiter_feedback():
    """View all feedback from students"""
    try:
        recruiter_id = ObjectId(session['user_id'])
        
        # Get all jobs posted by this recruiter
        recruiter_jobs = list(mongo.db.jobs.find({'recruiter_id': recruiter_id}))
        print(f"Found {len(recruiter_jobs)} jobs for recruiter {recruiter_id}")
        
        if not recruiter_jobs:
            print("No jobs found for this recruiter")
            return render_template('recruiter/feedback.html', 
                                 feedbacks=[], 
                                 stats={
                                     'total_feedbacks': 0,
                                     'avg_rating': 0,
                                     'positive_feedback': 0,
                                     'needs_improvement': 0,
                                     'rating_distribution': {5:0,4:0,3:0,2:0,1:0},
                                     'feedback_by_type': {'application': 0, 'interview': 0}
                                 })
        
        job_ids = [job['_id'] for job in recruiter_jobs]
        print(f"Job IDs: {job_ids}")
        
        # Get applications for these jobs
        applications = list(mongo.db.applications.find({'job_id': {'$in': job_ids}}))
        print(f"Found {len(applications)} applications")
        
        if not applications:
            print("No applications found for these jobs")
            return render_template('recruiter/feedback.html', 
                                 feedbacks=[], 
                                 stats={
                                     'total_feedbacks': 0,
                                     'avg_rating': 0,
                                     'positive_feedback': 0,
                                     'needs_improvement': 0,
                                     'rating_distribution': {5:0,4:0,3:0,2:0,1:0},
                                     'feedback_by_type': {'application': 0, 'interview': 0}
                                 })
        
        student_ids = list(set([app['student_id'] for app in applications]))
        print(f"Student IDs: {[str(sid) for sid in student_ids]}")
        
        # Get feedback from these students
        feedbacks = list(mongo.db.feedback.find({
            'student_id': {'$in': student_ids}
        }).sort('date', -1))
        
        print(f"Found {len(feedbacks)} feedback entries")
        
        # If no feedback found, try to get all feedback to debug
        if len(feedbacks) == 0:
            all_feedback = list(mongo.db.feedback.find())
            print(f"Total feedback in DB: {len(all_feedback)}")
            if all_feedback:
                print(f"Sample feedback student IDs: {[str(f.get('student_id')) for f in all_feedback[:5]]}")
        
        # Enrich feedback with additional data
        for feedback in feedbacks:
            # Get student info
            student = mongo.db.users.find_one({'_id': feedback['student_id']})
            feedback['student_name'] = student['name'] if student else 'Unknown'
            feedback['student_email'] = student['email'] if student else 'Unknown'
            
            # Get job info if it's application feedback
            if feedback.get('type') == 'application' and feedback.get('application_id'):
                job = mongo.db.jobs.find_one({'_id': feedback['application_id']})
                feedback['job_title'] = job['title'] if job else 'N/A'
            
            # Convert ObjectId to string for template
            feedback['_id'] = str(feedback['_id'])
        
        # Calculate feedback statistics
        total_feedbacks = len(feedbacks)
        avg_rating = 0
        if total_feedbacks > 0:
            ratings = [f.get('rating', 0) for f in feedbacks if f.get('rating')]
            avg_rating = sum(ratings) / len(ratings) if ratings else 0
        
        # Group by rating
        rating_distribution = {
            5: len([f for f in feedbacks if f.get('rating') == 5]),
            4: len([f for f in feedbacks if f.get('rating') == 4]),
            3: len([f for f in feedbacks if f.get('rating') == 3]),
            2: len([f for f in feedbacks if f.get('rating') == 2]),
            1: len([f for f in feedbacks if f.get('rating') == 1])
        }
        
        # Group by type
        feedback_by_type = {
            'application': len([f for f in feedbacks if f.get('type') == 'application']),
            'interview': len([f for f in feedbacks if f.get('type') == 'interview'])
        }
        
        stats = {
            'total_feedbacks': total_feedbacks,
            'avg_rating': round(avg_rating, 1),
            'positive_feedback': len([f for f in feedbacks if f.get('rating', 0) >= 4]),
            'needs_improvement': len([f for f in feedbacks if f.get('rating', 0) <= 2]),
            'rating_distribution': rating_distribution,
            'feedback_by_type': feedback_by_type
        }
        
        print(f"Stats: {stats}")
        
        return render_template('recruiter/feedback.html', 
                             feedbacks=feedbacks,
                             stats=stats)
                             
    except Exception as e:
        print(f"Error in recruiter_feedback: {str(e)}")
        import traceback
        traceback.print_exc()
        flash(f'Error loading feedback: {str(e)}', 'error')
        return render_template('recruiter/feedback.html', 
                             feedbacks=[], 
                             stats={
                                 'total_feedbacks': 0,
                                 'avg_rating': 0,
                                 'positive_feedback': 0,
                                 'needs_improvement': 0,
                                 'rating_distribution': {5:0,4:0,3:0,2:0,1:0},
                                 'feedback_by_type': {'application': 0, 'interview': 0}
                             })

@app.route('/admin/feedback')
@login_required
@role_required('admin')
def admin_feedback():
    """View all feedback from all users"""
    # Get all feedback
    feedbacks = list(mongo.db.feedback.find().sort('date', -1))
    
    # Enrich feedback with additional data
    for feedback in feedbacks:
        # Get student info
        student = mongo.db.users.find_one({'_id': feedback['student_id']})
        feedback['student_name'] = student['name'] if student else 'Unknown'
        feedback['student_email'] = student['email'] if student else 'Unknown'
        
        # Get job info if it's application feedback
        if feedback.get('type') == 'application' and feedback.get('application_id'):
            job = mongo.db.jobs.find_one({'_id': feedback['application_id']})
            feedback['job_title'] = job['title'] if job else 'N/A'
            
            # Get recruiter info
            if job and job.get('recruiter_id'):
                recruiter = mongo.db.users.find_one({'_id': job['recruiter_id']})
                feedback['recruiter_name'] = recruiter['name'] if recruiter else 'Unknown'
        
        # Convert ObjectId to string
        feedback['_id'] = str(feedback['_id'])
        if feedback.get('student_id'):
            feedback['student_id'] = str(feedback['student_id'])
        if feedback.get('application_id'):
            feedback['application_id'] = str(feedback['application_id'])
    
    # Calculate overall statistics
    total_feedbacks = len(feedbacks)
    avg_rating = 0
    if total_feedbacks > 0:
        ratings = [f.get('rating', 0) for f in feedbacks if f.get('rating')]
        avg_rating = sum(ratings) / len(ratings) if ratings else 0
    
    # Group by type
    feedback_by_type = {
        'application': len([f for f in feedbacks if f.get('type') == 'application']),
        'interview': len([f for f in feedbacks if f.get('type') == 'interview'])
    }
    
    # Group by rating
    rating_distribution = {
        5: len([f for f in feedbacks if f.get('rating') == 5]),
        4: len([f for f in feedbacks if f.get('rating') == 4]),
        3: len([f for f in feedbacks if f.get('rating') == 3]),
        2: len([f for f in feedbacks if f.get('rating') == 2]),
        1: len([f for f in feedbacks if f.get('rating') == 1])
    }
    
    # Get monthly feedback trends
    monthly_trends = []
    for i in range(5, -1, -1):
        month_date = datetime.datetime.now() - datetime.timedelta(days=30*i)
        month_start = month_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if month_date.month == 12:
            month_end = month_date.replace(year=month_date.year + 1, month=1, day=1)
        else:
            month_end = month_date.replace(month=month_date.month + 1, day=1)
        
        month_feedbacks = mongo.db.feedback.count_documents({
            'date': {'$gte': month_start, '$lt': month_end}
        })
        monthly_trends.append({
            'month': month_date.strftime('%B'),
            'count': month_feedbacks
        })
    
    stats = {
        'total_feedbacks': total_feedbacks,
        'avg_rating': round(avg_rating, 1),
        'positive_feedback': len([f for f in feedbacks if f.get('rating', 0) >= 4]),
        'needs_improvement': len([f for f in feedbacks if f.get('rating', 0) <= 2]),
        'feedback_by_type': feedback_by_type,
        'rating_distribution': rating_distribution,
        'response_rate': 78  # Placeholder - can calculate actual response rate
    }
    
    return render_template('admin/feedback.html', 
                         feedbacks=feedbacks,
                         stats=stats,
                         monthly_trends=monthly_trends)

@app.route('/admin/feedback/<feedback_id>')
@login_required
@role_required('admin')
def admin_feedback_detail(feedback_id):
    """View detailed feedback"""
    feedback = mongo.db.feedback.find_one({'_id': ObjectId(feedback_id)})
    
    if not feedback:
        flash('Feedback not found', 'error')
        return redirect(url_for('admin_feedback'))
    
    # Enrich feedback data
    student = mongo.db.users.find_one({'_id': feedback['student_id']})
    feedback['student_name'] = student['name'] if student else 'Unknown'
    feedback['student_email'] = student['email'] if student else 'Unknown'
    
    if feedback.get('type') == 'application' and feedback.get('application_id'):
        job = mongo.db.jobs.find_one({'_id': feedback['application_id']})
        feedback['job_title'] = job['title'] if job else 'N/A'
        
        if job and job.get('recruiter_id'):
            recruiter = mongo.db.users.find_one({'_id': job['recruiter_id']})
            feedback['recruiter_name'] = recruiter['name'] if recruiter else 'Unknown'
            feedback['recruiter_email'] = recruiter['email'] if recruiter else 'Unknown'
    
    # Convert ObjectId to string
    feedback['_id'] = str(feedback['_id'])
    
    return render_template('admin/feedback_detail.html', feedback=feedback)

@app.route('/admin/delete_feedback/<feedback_id>', methods=['DELETE'])
@login_required
@role_required('admin')
def admin_delete_feedback(feedback_id):
    """Delete feedback (admin only)"""
    try:
        mongo.db.feedback.delete_one({'_id': ObjectId(feedback_id)})
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/recruiter/feedback/<feedback_id>')
@login_required
@role_required('recruiter')
def recruiter_feedback_detail(feedback_id):
    """View detailed feedback for recruiter"""
    feedback = mongo.db.feedback.find_one({'_id': ObjectId(feedback_id)})
    
    if not feedback:
        flash('Feedback not found', 'error')
        return redirect(url_for('recruiter_feedback'))
    
    # Verify that this feedback is for a job posted by this recruiter
    recruiter_id = ObjectId(session['user_id'])
    if feedback.get('type') == 'application' and feedback.get('application_id'):
        job = mongo.db.jobs.find_one({'_id': feedback['application_id']})
        if not job or job.get('recruiter_id') != recruiter_id:
            flash('Access denied', 'error')
            return redirect(url_for('recruiter_dashboard'))
    
    # Enrich feedback data
    student = mongo.db.users.find_one({'_id': feedback['student_id']})
    feedback['student_name'] = student['name'] if student else 'Unknown'
    feedback['student_email'] = student['email'] if student else 'Unknown'
    
    if feedback.get('type') == 'application' and feedback.get('application_id'):
        job = mongo.db.jobs.find_one({'_id': feedback['application_id']})
        feedback['job_title'] = job['title'] if job else 'N/A'
    
    # Convert ObjectId to string
    feedback['_id'] = str(feedback['_id'])
    
    return render_template('recruiter/feedback_detail.html', feedback=feedback)

@app.route('/recruiter/feedback/respond', methods=['POST'])
@login_required
@role_required('recruiter')
def respond_to_feedback():
    """Respond to student feedback"""
    feedback_id = request.form.get('feedback_id')
    response = request.form.get('response')
    
    mongo.db.feedback.update_one(
        {'_id': ObjectId(feedback_id)},
        {'$set': {
            'recruiter_response': response,
            'response_date': datetime.datetime.now(),
            'responded_by': session['user_name']
        }}
    )
    
    flash('Response sent successfully!', 'success')
    return redirect(url_for('recruiter_feedback_detail', feedback_id=feedback_id))





if __name__ == '__main__':
    # Create necessary directories
    os.makedirs('uploads', exist_ok=True)
    os.makedirs('uploads/resumes', exist_ok=True)
    app.run(debug=True, port=5000)