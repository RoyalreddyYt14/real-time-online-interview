# Real-Time Online Interview System

A comprehensive web-based interview platform built with Flask that conducts automated interviews with real-time proctoring, face detection, and multi-stage assessment.

## 🚀 Features

- **Multi-Stage Interviews**: Aptitude, Technical, Coding, and HR rounds
- **Real-Time Proctoring**: Face detection and monitoring during interviews
- **Admin Dashboard**: Complete candidate management and analytics
- **Resume Processing**: Automatic skill extraction from PDF resumes
- **Real-Time Communication**: Socket.IO for live updates
- **Face Verification**: AI-powered face recognition and verification
- **Automated Scoring**: Intelligent evaluation across all interview stages

## 📋 Prerequisites

- Python 3.8 or higher
- Webcam (for proctoring features)
- Modern web browser

## 🛠️ Installation

1. **Clone the repository:**

   ```bash
   git clone <your-repo-url>
   cd real_time_online_interview
   ```

2. **Create a virtual environment:**

   ```bash
   python -m venv venv
   # On Windows:
   venv\Scripts\activate
   # On macOS/Linux:
   source venv/bin/activate
   ```

3. **Install dependencies:**

   ```bash
   pip install -r requirements.txt
   ```

4. **Download YOLO model:**
   - The `yolov8n.pt` file should be included in the repository
   - If missing, download from: https://github.com/ultralytics/assets/releases/download/v0.0.0/yolov8n.pt

## 🚀 Running the Application

1. **Start the Flask application:**

   ```bash
   python app.py
   ```

2. **Open your browser and navigate to:**

   ```
   http://localhost:5000
   ```

3. **Admin Access:**
   - URL: `http://localhost:5000/admin`
   - Default credentials: `admin@example.com` / `admin123`

## 📁 Project Structure

```
real_time_online_interview/
├── app.py                      # Main Flask application
├── modules/                    # Modular components
│   ├── config.py              # Configuration settings
│   ├── utils.py               # General utilities
│   └── admin_utils.py         # Admin dashboard logic
├── database/                  # Database models and setup
│   ├── db.py
│   ├── user_model.py
│   ├── warning_event_model.py
│   └── interview_attempt_model.py
├── models/                    # Additional models
├── static/                    # Static assets (CSS, JS, images)
│   ├── css/
│   ├── js/
│   ├── faces/                 # Face verification images
│   └── resumes/               # Uploaded resumes
├── templates/                 # HTML templates
├── utils/                     # Interview utilities
│   └── question_generator.py
├── face_detection.py          # Face detection script
├── face_verification.py       # Face verification script
├── voice_interview.py         # Voice interview script
├── yolov8n.pt                 # YOLO model file
└── requirements.txt           # Python dependencies
```

## 🔧 Configuration

### Environment Variables (Optional)

You can customize the following settings using environment variables:

```bash
# Admin credentials
export ADMIN_EMAIL="your-admin@example.com"
export ADMIN_PASSWORD="your-secure-password"

# Flask settings
export SECRET_KEY="your-secret-key"
export DEBUG="true"

# Database
export DATABASE_URL="sqlite:///instance/interview.db"
```

### Interview Settings

Modify settings in `modules/config.py`:

- `INTERVIEW_DURATION_SECONDS`: Total interview time (default: 15 minutes)
- `MAX_ATTEMPTS`: Maximum interview attempts per user (default: 3)
- `SELECTION_THRESHOLD`: Minimum score for selection (default: 70%)

## 👥 User Roles

1. **Candidates**: Take interviews, upload resumes, view results
2. **Admins**: Manage candidates, view analytics, monitor interviews

## 📊 Admin Features

- **Dashboard**: Overview of all candidates and statistics
- **Candidate Management**: View, filter, and sort candidates
- **Analytics**: Charts showing selection rates and performance
- **Export**: Download candidate data as Excel files
- **Real-time Monitoring**: Live interview progress tracking

## 🔒 Security Features

- Session-based authentication
- CSRF protection
- Secure file uploads
- Admin role validation
- Proctoring with face detection

## 🐛 Troubleshooting

### Common Issues:

1. **"Module not found" errors:**

   ```bash
   pip install -r requirements.txt
   ```

2. **Database errors:**
   - Delete `instance/interview.db` and restart the app
   - The database will be recreated automatically

3. **Camera not working:**
   - Ensure your webcam is connected and not used by other applications
   - Check camera permissions in your browser

4. **Face detection not working:**
   - Ensure `yolov8n.pt` file is present
   - Check that OpenCV and ultralytics are properly installed

### Logs

Check the console output for detailed error messages and debugging information.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature-name`
3. Commit your changes: `git commit -am 'Add feature'`
4. Push to the branch: `git push origin feature-name`
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 📞 Support

For questions or issues, please open an issue on GitHub or contact the development team.

---

**Note**: This application uses AI-powered face detection for proctoring purposes. Ensure compliance with local privacy laws and obtain consent from users before using face detection features.
