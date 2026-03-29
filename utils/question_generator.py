import random

def generate_technical_questions(skills):
    """
    Generate beginner-friendly technical interview questions for given skills.

    Args:
        skills (list): List of skill names (e.g., ['Python', 'SQL'])

    Returns:
        list: List of generated questions (2 per skill)
    """
    # Dictionary mapping each skill to a list of possible questions
    skill_questions = {
        'Python': [
            "What is a list in Python and how do you use it?",
            "Explain the difference between a list and a tuple in Python.",
            "How do you handle exceptions in Python?",
            "What is a dictionary in Python?",
            "How do you define a function in Python?"
        ],
        'SQL': [
            "What is SQL and what is it used for?",
            "How do you retrieve all records from a table in SQL?",
            "Explain the difference between WHERE and HAVING clauses.",
            "What is a primary key in SQL?",
            "How would you update data in a SQL table?"
        ],
        'Java': [
            "What is a class in Java?",
            "How do you write a basic for loop in Java?",
            "What is inheritance in Java?",
            "Explain the concept of method overloading in Java.",
            "How do you declare an array in Java?"
        ],
        'C++': [
            "What is the difference between a pointer and a reference in C++?",
            "How do you write a simple 'Hello World' program in C++?",
            "What is a constructor in C++?",
            "Explain the use of 'namespace' in C++.",
            "How do you declare a function in C++?"
        ],
        'HTML': [
            "What does HTML stand for?",
            "How do you create a hyperlink in HTML?",
            "What is the purpose of the <head> tag in HTML?",
            "What tag is used to insert an image in HTML?",
            "How do you create a table in HTML?"
        ],
        'JavaScript': [
            "How do you declare a variable in JavaScript?",
            "What is the difference between == and === in JavaScript?",
            "How do you write a function in JavaScript?",
            "What is the DOM in JavaScript?",
            "How do you add a comment in JavaScript?"
        ]
    }

    # Aliases for skills (to make user input more flexible)
    skill_aliases = {
        "js": "JavaScript",
        "javascript": "JavaScript",
        "c++": "C++",
        "cpp": "C++",
        "python": "Python",
        "sql": "SQL",
        "java": "Java",
        "html": "HTML",
    }

    questions_list = []

    for skill in skills:
        # Normalize skill name (ignore case and whitespace)
        normalized_skill = skill.strip().lower()
        # Get proper skill key from aliases or use title-case version
        skill_key = skill_aliases.get(normalized_skill, skill.strip().title())
        # Check if questions exist for this skill
        questions = skill_questions.get(skill_key)
        if questions:
            # Randomly select 2 questions
            selected_questions = random.sample(questions, k=2)
            questions_list.extend(selected_questions)

    return questions_list