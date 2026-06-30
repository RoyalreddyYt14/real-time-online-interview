import json
from pathlib import Path
import random

QUESTION_BANK_PATH = Path(__file__).resolve().parents[1] / "data" / "question_bank.json"


def load_question_bank():
    if QUESTION_BANK_PATH.exists():
        try:
            with open(QUESTION_BANK_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_question_bank(question_bank):
    QUESTION_BANK_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(QUESTION_BANK_PATH, "w", encoding="utf-8") as f:
        json.dump(question_bank, f, indent=2, ensure_ascii=False)


def add_question(skill, question):
    question_bank = load_question_bank()
    if not skill or not question:
        return
    skill_key = skill.strip().title()
    question_bank.setdefault(skill_key, [])
    question_bank[skill_key].append(question.strip())
    save_question_bank(question_bank)


def _normalize_skill(skill):
    normalized_skill = skill.strip().lower()
    aliases = {
        "js": "JavaScript",
        "javascript": "JavaScript",
        "c++": "C++",
        "cpp": "C++",
        "python": "Python",
        "sql": "SQL",
        "java": "Java",
        "html": "HTML",
        "css": "CSS",
        "machine learning": "Machine Learning",
        "django": "Django",
        "flask": "Flask",
        "react": "React",
        "c": "C",
    }
    return aliases.get(normalized_skill, skill.strip().title())


def generate_technical_questions(skills):
    """
    Generate a fixed set of 10 technical interview questions.

    Args:
        skills (list): List of skill names (e.g., ['Python', 'SQL'])

    Returns:
        list: List of 10 generated technical questions.
    """
    skill_questions = {
        "Python": [
            "What is a list in Python and how do you use it?",
            "Explain the difference between a list and a tuple in Python.",
            "How do you handle exceptions in Python?",
            "What is a dictionary in Python?",
            "How do you define a function in Python?",
        ],
        "SQL": [
            "What is SQL and what is it used for?",
            "How do you retrieve all records from a table in SQL?",
            "Explain the difference between WHERE and HAVING clauses.",
            "What is a primary key in SQL?",
            "How would you update data in a SQL table?",
        ],
        "Java": [
            "What is a class in Java?",
            "How do you write a basic for loop in Java?",
            "What is inheritance in Java?",
            "Explain the concept of method overloading in Java.",
            "How do you declare an array in Java?",
        ],
        "C++": [
            "What is the difference between a pointer and a reference in C++?",
            "How do you write a simple 'Hello World' program in C++?",
            "What is a constructor in C++?",
            "Explain the use of 'namespace' in C++.",
            "How do you declare a function in C++?",
        ],
        "HTML": [
            "What does HTML stand for?",
            "How do you create a hyperlink in HTML?",
            "What is the purpose of the <head> tag in HTML?",
            "What tag is used to insert an image in HTML?",
            "How do you create a table in HTML?",
        ],
        "JavaScript": [
            "How do you declare a variable in JavaScript?",
            "What is the difference between == and === in JavaScript?",
            "How do you write a function in JavaScript?",
            "What is the DOM in JavaScript?",
            "How do you add a comment in JavaScript?",
        ],
        "React": [
            "What is a React component?",
            "How do you pass data between React components?",
            "What are hooks in React?",
            "Explain the difference between state and props in React.",
            "How do you manage side effects in React?",
        ],
        "Django": [
            "What is a Django model?",
            "How do you create a view in Django?",
            "What is the purpose of Django migrations?",
            "How do you configure URLs in Django?",
            "What is the Django admin interface used for?",
        ],
        "Flask": [
            "What is a Flask route?",
            "How do you handle form submission in Flask?",
            "What is a Flask blueprint?",
            "How do you access request data in Flask?",
            "What is Jinja2 used for in Flask?",
        ],
        "Machine Learning": [
            "What is supervised learning?",
            "What is overfitting and how do you prevent it?",
            "Explain the difference between classification and regression.",
            "What is a training dataset?",
            "What is feature engineering?",
        ],
        "CSS": [
            "What does CSS stand for?",
            "How do you center a div using CSS?",
            "What is the box model in CSS?",
            "How do you apply a background color in CSS?",
            "What is the difference between margin and padding?",
        ],
        "C": [
            "What is a pointer in C?",
            "How do you declare an array in C?",
            "What is the purpose of the main() function in C?",
            "How do you write a simple if statement in C?",
            "How do you allocate memory dynamically in C?",
        ],
    }

    generic_questions = [
        "Explain the difference between procedural and object-oriented programming.",
        "What is the purpose of version control systems like Git?",
        "Describe how a database index improves query performance.",
        "What is a REST API and why is it useful?",
        "Explain the software development life cycle.",
        "How do you handle errors in a production application?",
        "What is the difference between client-side and server-side code?",
        "Describe the role of unit testing in software development.",
        "How do you debug a broken application?",
        "What is the difference between HTTP and HTTPS?",
        "Explain what a data structure is and give an example.",
        "What is the purpose of a build tool like Maven or npm?",
        "How do you keep your code maintainable over time?",
        "Describe the concept of recursion with an example.",
        "What is a software design pattern?",
        "How does caching improve performance?",
        "Explain the difference between synchronous and asynchronous operations.",
        "How would you explain code refactoring to a teammate?",
        "What is continuous integration?",
        "How do you prioritize bug fixes in a development cycle?",
    ]

    questions_list = []
    for skill in skills:
        skill_key = _normalize_skill(skill)
        questions = skill_questions.get(skill_key)
        if questions:
            selected_questions = random.sample(questions, k=min(2, len(questions)))
            questions_list.extend(selected_questions)

    random.shuffle(generic_questions)
    for question in generic_questions:
        if len(questions_list) >= 10:
            break
        if question not in questions_list:
            questions_list.append(question)

    if not questions_list:
        questions_list = generic_questions[:10]

    return questions_list[:10]


def generate_aptitude_questions(skills):
    """
    Generate 20 aptitude questions for the first round.

    Args:
        skills (list): List of detected resume skills.

    Returns:
        dict: Aptitude question data with 20 questions.
    """
    aptitude_bank = {
        "Python": {
            "question": "Your resume shows Python experience. If a script processes 100 records in 5 seconds, how long will 400 records take at the same speed?",
            "options": ["15 seconds", "20 seconds", "25 seconds", "30 seconds"],
            "answer": "20 seconds",
        },
        "SQL": {
            "question": "If a SQL query returns duplicate rows, which clause can remove duplicates?",
            "options": ["GROUP BY", "ORDER BY", "DISTINCT", "HAVING"],
            "answer": "DISTINCT",
        },
        "JavaScript": {
            "question": "A JavaScript array contains 5 elements. What is its last valid index?",
            "options": ["3", "4", "5", "6"],
            "answer": "4",
        },
        "Java": {
            "question": "Which keyword in Java is used to define a class?",
            "options": ["method", "class", "object", "package"],
            "answer": "class",
        },
        "C++": {
            "question": "What happens if you use delete on a pointer in C++?",
            "options": [
                "Memory is freed",
                "Variable is copied",
                "Program pauses",
                "Function is called",
            ],
            "answer": "Memory is freed",
        },
        "HTML": {
            "question": "Which HTML tag is used to add a link?",
            "options": ["<div>", "<a>", "<link>", "<href>"],
            "answer": "<a>",
        },
        "CSS": {
            "question": "In CSS, which property changes the text color?",
            "options": ["font-size", "color", "background", "margin"],
            "answer": "color",
        },
        "Machine Learning": {
            "question": "Which term describes the set of examples used to train a machine learning model?",
            "options": ["Test set", "Validation set", "Training set", "Feature set"],
            "answer": "Training set",
        },
    }

    default_questions = [
        {
            "question": "A vehicle travels 60 km in 1 hour. How far will it travel in 2.5 hours?",
            "options": ["120 km", "150 km", "180 km", "200 km"],
            "answer": "150 km",
        },
        {
            "question": "If a train travels 90 km in 1.5 hours, what is its average speed?",
            "options": ["45 km/h", "55 km/h", "60 km/h", "75 km/h"],
            "answer": "60 km/h",
        },
        {
            "question": "What is 25% of 240?",
            "options": ["40", "50", "60", "70"],
            "answer": "60",
        },
        {
            "question": "If you save $150 each month, how much will you save in 8 months?",
            "options": ["$1000", "$1100", "$1200", "$1300"],
            "answer": "$1200",
        },
        {
            "question": "If a project is 30% complete and takes 15 days total, how many days are left?",
            "options": ["4.5", "7", "10.5", "12"],
            "answer": "10.5",
        },
        {
            "question": "What is the value of 7 x 8?",
            "options": ["42", "48", "54", "56"],
            "answer": "56",
        },
        {
            "question": "If a recipe requires 3 cups of flour and you double it, how many cups do you need?",
            "options": ["5", "6", "7", "8"],
            "answer": "6",
        },
        {
            "question": "A taxi ride costs $4 plus $2 per mile. How much does a 6-mile ride cost?",
            "options": ["$12", "$14", "$16", "$18"],
            "answer": "$16",
        },
        {
            "question": "What is the next number in the sequence: 2, 4, 6, 8, ?",
            "options": ["8", "9", "10", "12"],
            "answer": "10",
        },
        {
            "question": "What is 15% of 200?",
            "options": ["20", "25", "30", "35"],
            "answer": "30",
        },
        {
            "question": "If a shirt costs $30 and is discounted by 20%, what is the sale price?",
            "options": ["$20", "$22", "$24", "$26"],
            "answer": "$24",
        },
        {
            "question": "If you work 5 days a week, how many days do you work in 4 weeks?",
            "options": ["15", "18", "20", "22"],
            "answer": "20",
        },
        {
            "question": "A car uses 8 liters of fuel to travel 100 km. How much fuel for 250 km?",
            "options": ["16", "18", "20", "22"],
            "answer": "20",
        },
        {
            "question": "What is the result of 9 + 14?",
            "options": ["21", "23", "24", "25"],
            "answer": "23",
        },
        {
            "question": "If a box contains 5 red and 7 blue balls, how many balls are there in total?",
            "options": ["10", "11", "12", "13"],
            "answer": "12",
        },
        {
            "question": "What is the difference between 100 and 37?",
            "options": ["62", "63", "64", "65"],
            "answer": "63",
        },
        {
            "question": "If a meeting starts at 9:15 and lasts 1 hour 20 minutes, what time does it end?",
            "options": ["10:15", "10:25", "10:35", "10:45"],
            "answer": "10:35",
        },
        {
            "question": "What is 6 squared?",
            "options": ["12", "18", "24", "36"],
            "answer": "36",
        },
        {
            "question": "If a worker completes 2 tasks per hour, how many tasks are done in 7 hours?",
            "options": ["12", "13", "14", "15"],
            "answer": "14",
        },
        {
            "question": "What is the perimeter of a square with side length 4?",
            "options": ["12", "14", "16", "18"],
            "answer": "16",
        },
    ]

    selected_questions = []
    for skill in skills:
        skill_key = _normalize_skill(skill)
        if skill_key in aptitude_bank:
            selected_questions.append(aptitude_bank[skill_key])

    remaining = [q for q in default_questions if q not in selected_questions]
    random.shuffle(remaining)
    selected_questions.extend(remaining)

    if len(selected_questions) < 20:
        selected_questions.extend(default_questions[: 20 - len(selected_questions)])

    return {"questions": selected_questions[:20]}


def generate_coding_questions(skills):
    """
    Generate 5 coding questions for the third round.

    Args:
        skills (list): List of detected resume skills.

    Returns:
        dict: Coding question prompts and keyword hints.
    """
    coding_bank = {
        "Python": {
            "questions": [
                "Write a Python function that counts how many times a word appears in a given sentence.",
                "Write a Python function that reverses a string without using built-in reverse methods.",
                "Write a Python script to find all even numbers in a list.",
                "Create a Python function that returns whether a number is prime.",
                "Write a Python function that removes duplicate items from a list.",
            ],
            "keywords": ["def ", "return", "split(", "lower()", "for ", "if ", "in "],
        },
        "JavaScript": {
            "questions": [
                "Write a JavaScript function to filter out even numbers from an array.",
                "Write a JavaScript function that checks if a string is a palindrome.",
                "Write a JavaScript function to calculate the sum of numbers in an array.",
                "Write a JavaScript function that converts an array to a comma-separated string.",
                "Write a JavaScript function to find the maximum value in an array.",
            ],
            "keywords": ["function ", "return", "filter(", "map(", "for (", "=>"],
        },
        "SQL": {
            "questions": [
                "Write an SQL SELECT query to retrieve all employees with salary greater than 50000.",
                "Write an SQL query to count the number of orders per customer.",
                "Write an SQL query to show only unique city names from a table.",
                "Write an SQL query to join customers with their orders.",
                "Write an SQL query to order products by price descending.",
            ],
            "keywords": ["SELECT", "FROM", "WHERE", "JOIN", "GROUP BY"],
        },
        "Java": {
            "questions": [
                "Write a Java method to check whether a number is prime.",
                "Write a Java method that reverses a string.",
                "Write a Java method to calculate the factorial of a number.",
                "Write a Java method that checks whether a string contains a substring.",
                "Write a Java method to sum numbers in an integer array.",
            ],
            "keywords": ["public", "static", "boolean", "for (", "return"],
        },
        "C++": {
            "questions": [
                "Write a C++ function to reverse a string.",
                "Write a C++ function to find the maximum number in an array.",
                "Write a C++ function to calculate the sum of array elements.",
                "Write a C++ function to check whether a number is even.",
                "Write a C++ function to swap two variables.",
            ],
            "keywords": ["std::", "return", "for (", "string", "vector"],
        },
        "HTML": {
            "questions": [
                "Write a simple HTML snippet for a contact form with name and email fields.",
                "Write an HTML snippet to create an ordered list of three items.",
                "Write an HTML snippet to display an image with alt text.",
                "Write an HTML snippet to create a table with two rows.",
                "Write an HTML snippet to create a navigation menu.",
            ],
            "keywords": ["<form", "<input", "<img", "<table", "<a"],
        },
        "React": {
            "questions": [
                "Write a React component that renders a button and logs a message when clicked.",
                "Write a React component that displays a greeting message.",
                "Write a React component that renders a list of items.",
                "Write a React component that conditionally renders content.",
                "Write a React component that uses useState to toggle text.",
            ],
            "keywords": [
                "function ",
                "return (",
                "onClick",
                "useState",
                "export default",
            ],
        },
        "Django": {
            "questions": [
                "Write a Django view function that renders a template called 'home.html'.",
                "Write a Django model with a CharField called title.",
                "Write a Django URL pattern for a homepage view.",
                "Write a Django form class with a single email field.",
                "Write a Django template snippet that loops over a list of items.",
            ],
            "keywords": ["def ", "render(request", "models.Model", "urlpatterns", "{{"],
        },
    }

    default_questions = [
        "Write a function that returns the square of a number.",
        "Write a function that counts vowels in a string.",
        "Write a function that finds the largest number in a list.",
        "Write a function that checks whether a number is even.",
        "Write a function that swaps two variables.",
    ]

    selected_questions = []
    keywords = set()
    for skill in skills:
        skill_key = _normalize_skill(skill)
        if skill_key in coding_bank:
            selected_questions.extend(coding_bank[skill_key]["questions"][:2])
            keywords.update(coding_bank[skill_key]["keywords"])

    if len(selected_questions) < 5:
        selected_questions.extend(default_questions)

    if not keywords:
        keywords.update(
            [
                "function ",
                "return",
                "if ",
                "for ",
                "while ",
                "const ",
                "let ",
                "var ",
                "def ",
                "class ",
                "print(",
            ]
        )

    keywords = {keyword.lower() for keyword in keywords}
    selected_questions = selected_questions[:5]
    return {
        "questions": selected_questions,
        "keywords": sorted(keywords),
    }


def generate_hr_questions(skills):
    """
    Generate HR interview questions based on resume skills.

    Args:
        skills (list): List of detected resume skills.

    Returns:
        list: List of HR questions.
    """
    skill_prompts = {
        "Python": "Tell me about a Python project from your resume and why it was important.",
        "SQL": "Describe a time when you used SQL to solve a real problem.",
        "JavaScript": "Explain how JavaScript helped you build user-facing features.",
        "Java": "Share a Java development experience that taught you something meaningful.",
        "C++": "What is the most challenging C++ problem you've solved?",
        "HTML": "How have you used HTML to build a web page or user interface?",
        "CSS": "Describe a design challenge you solved with CSS styling.",
        "Machine Learning": "Walk me through a machine learning project you worked on.",
        "React": "How did you use React to build an interactive UI?",
        "Django": "Describe a Django application you built and why it mattered.",
        "Flask": "Tell me about a Flask app you have built and what you learned.",
    }

    default_prompts = [
        "Tell me about yourself and your most recent project.",
        "Why are you interested in this role and our company?",
        "What are your strengths and how do they relate to this job?",
        "Describe a situation when you solved a difficult problem.",
        "How do you handle feedback and tough deadlines?",
        "How do you stay motivated during challenging projects?",
        "Describe a time when you learned something new quickly.",
        "How do you approach collaboration with teammates?",
    ]

    questions = []
    for skill in skills:
        skill_key = _normalize_skill(skill)
        if skill_key in skill_prompts:
            questions.append(skill_prompts[skill_key])
            break

    random.shuffle(default_prompts)
    questions.extend(default_prompts[:5])
    return questions[:6]
